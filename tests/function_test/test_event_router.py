from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import EventInvolvement, SupportedLanguage, TurnType
from world_simulation_engine.model import Author, Character, CurrentActivity, Turn, World
from world_simulation_engine.router import event_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class EventRouterTestClient:
    client: TestClient
    character: Character
    turn: Turn
    second_turn: Turn


@pytest.fixture
def event_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Event API Author")
    world = World(
        id=str(uuid4()),
        name="Event World",
        description="A world used to create events",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    character = Character(
        id=str(uuid4()),
        name="Alex",
        age=30,
        gender="non-binary",
        appearance="A practical coat",
        description="A test character",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="idle"),
    )
    turn = Turn(
        id=str(uuid4()),
        sequence=0,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    second_turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="Hi",
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        driver = AsyncGraphDatabase.driver(
            neo4j_container.get_connection_url(),
            auth=("neo4j", "testpassword"),
        )
        await driver.verify_connectivity()
        await driver.execute_query("MATCH (n) DETACH DELETE n")

        database = DatabaseService(driver)
        await database.world.create_author(author)
        await database.world.create_world(world, author.id)
        await database.character.create_character(character, world.id)
        await database.turn.create_turn(turn, world.id)
        await database.turn.create_turn(second_turn, world.id, previous_turn_id=turn.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(event_router)

    with TestClient(app) as client:
        yield EventRouterTestClient(
            client=client,
            character=character,
            turn=turn,
            second_turn=second_turn,
        )


def test_create_list_get_update_and_delete_event(event_api):
    client = event_api.client

    create_response = client.post(
        "/events",
        json={
            "name": "Greeting",
            "summary": "A greeting exchange",
            "turn_ids": [event_api.turn.id],
            "involved_characters": [
                {
                    "character_id": event_api.character.id,
                    "involvement": EventInvolvement.PARTICIPATE,
                }
            ],
        },
    )

    assert create_response.status_code == 200
    event = create_response.json()
    assert event["name"] == "Greeting"

    list_response = client.get("/events")
    character_filter_response = client.get("/events", params={"character_id": event_api.character.id})
    turn_filter_response = client.get("/events", params={"turn_id": event_api.turn.id})

    assert list_response.json() == [event]
    assert character_filter_response.json() == [event]
    assert turn_filter_response.json() == [event]
    assert client.get(f"/events/{event['id']}").json() == event

    update_response = client.patch(
        f"/events/{event['id']}",
        json={
            "name": "Updated greeting",
            "summary": "An updated greeting exchange",
            "turn_ids": [event_api.second_turn.id],
        },
    )

    assert update_response.status_code == 200
    updated_event = update_response.json()
    assert updated_event["id"] == event["id"]
    assert updated_event["name"] == "Updated greeting"
    assert client.get("/events", params={"turn_id": event_api.second_turn.id}).json() == [updated_event]

    delete_response = client.delete(f"/events/{event['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/events/{event['id']}").status_code == 404


def test_event_endpoints_return_404_for_missing_resources(event_api):
    client = event_api.client
    missing_event_id = str(uuid4())
    missing_turn_id = str(uuid4())
    missing_character_id = str(uuid4())

    assert client.get(f"/events/{missing_event_id}").status_code == 404
    assert client.patch(f"/events/{missing_event_id}", json={"name": "Missing"}).status_code == 404
    assert client.delete(f"/events/{missing_event_id}").status_code == 404
    assert client.post(
        "/events",
        json={
            "name": "Missing turn",
            "summary": "Missing turn",
            "turn_ids": [missing_turn_id],
        },
    ).status_code == 404
    assert client.post(
        "/events",
        json={
            "name": "Missing character",
            "summary": "Missing character",
            "turn_ids": [event_api.turn.id],
            "involved_characters": [
                {
                    "character_id": missing_character_id,
                    "involvement": EventInvolvement.WITNESS,
                }
            ],
        },
    ).status_code == 404


def test_event_creation_requires_turn(event_api):
    response = event_api.client.post(
        "/events",
        json={
            "name": "No turn",
            "summary": "No turn",
            "turn_ids": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Event must be attached to at least one turn"
