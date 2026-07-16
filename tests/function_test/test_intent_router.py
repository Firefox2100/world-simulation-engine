from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType, SupportedLanguage, TurnType
from world_simulation_engine.model import Author, Character, CurrentActivity, Event, Turn, World
from world_simulation_engine.router import intent_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class IntentRouterTestClient:
    client: TestClient
    character: Character
    event: Event


@pytest.fixture
def intent_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Intent API Author")
    world = World(
        id=str(uuid4()),
        name="Intent World",
        description="A world used to create intents",
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
        content="A meeting happened",
        start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Meeting",
        summary="A meeting happened",
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
        await database.event.create_event(event, [turn.id])
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(intent_router)

    with TestClient(app) as client:
        yield IntentRouterTestClient(
            client=client,
            character=character,
            event=event,
        )


def intent_payload(name: str = "Buy coffee") -> dict:
    return {
        "type": IntentType.QUEST,
        "name": name,
        "description": f"{name} description",
        "keywords": name.lower().split(),
        "embedding": [0.1, 0.2],
        "priority": 0.8,
        "urgency": 0.7,
        "status": IntentStatus.ACTIVE,
        "desired_state": f"{name} done",
        "success_conditions": [f"{name} succeeds"],
        "failure_conditions": [f"{name} fails"],
        "maintenance_conditions": [f"{name} maintained"],
        "deadline": "2026-01-02T09:00:00Z",
        "horizon": IntentHorizon.SHORT,
        "constraints": [f"{name} constraint"],
        "current_plan": [f"{name} plan"],
        "next_action_biases": [f"{name} next"],
        "blockers": [f"{name} blocker"],
        "open_threads": [f"{name} thread"],
    }


def test_create_list_get_update_and_delete_intent(intent_api):
    client = intent_api.client

    create_response = client.post(
        f"/characters/{intent_api.character.id}/intents",
        json={
            **intent_payload(),
            "created_by_event_id": intent_api.event.id,
        },
    )

    assert create_response.status_code == 200
    intent = create_response.json()
    assert intent["name"] == "Buy coffee"

    list_response = client.get("/intents")
    character_filter_response = client.get("/intents", params={"character_id": intent_api.character.id})
    event_filter_response = client.get("/intents", params={"event_id": intent_api.event.id})

    assert list_response.json() == [intent]
    assert character_filter_response.json() == [intent]
    assert event_filter_response.json() == [intent]
    assert client.get(f"/intents/{intent['id']}").json() == intent

    update_response = client.patch(
        f"/intents/{intent['id']}",
        json={
            "status": IntentStatus.PAUSED,
            "priority": 0.9,
            "current_plan": ["wait"],
            "contributing_event_ids": [intent_api.event.id],
        },
    )

    assert update_response.status_code == 200
    updated_intent = update_response.json()
    assert updated_intent["id"] == intent["id"]
    assert updated_intent["status"] == IntentStatus.PAUSED
    assert updated_intent["priority"] == 0.9
    assert client.get("/intents", params={"event_id": intent_api.event.id}).json() == [updated_intent]

    delete_response = client.delete(f"/intents/{intent['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/intents/{intent['id']}").status_code == 404


def test_intent_endpoints_return_404_for_missing_resources(intent_api):
    client = intent_api.client
    missing_character_id = str(uuid4())
    missing_intent_id = str(uuid4())
    missing_event_id = str(uuid4())

    assert client.get(f"/intents/{missing_intent_id}").status_code == 404
    assert client.patch(f"/intents/{missing_intent_id}", json={"status": IntentStatus.PAUSED}).status_code == 404
    assert client.delete(f"/intents/{missing_intent_id}").status_code == 404
    assert client.post(
        f"/characters/{missing_character_id}/intents",
        json=intent_payload(),
    ).status_code == 404
    assert client.post(
        f"/characters/{intent_api.character.id}/intents",
        json={
            **intent_payload(),
            "created_by_event_id": missing_event_id,
        },
    ).status_code == 404
