from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, SupportedLanguage, TurnType
from world_simulation_engine.model import Author, Character, CurrentActivity, Event, Turn, World
from world_simulation_engine.router import memory_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class MemoryRouterTestClient:
    client: TestClient
    character: Character
    second_character: Character
    event: Event


@pytest.fixture
def memory_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Memory API Author")
    world = World(
        id=str(uuid4()),
        name="Memory World",
        description="A world used to create memories",
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
    second_character = character.model_copy(update={"id": str(uuid4()), "name": "Blair"})
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
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
        await database.character.create_character(second_character, world.id)
        await database.turn.create_turn(turn, world.id)
        await database.event.create_event(event, [turn.id])
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(memory_router)

    with TestClient(app) as client:
        yield MemoryRouterTestClient(
            client=client,
            character=character,
            second_character=second_character,
            event=event,
        )


def memory_payload(memory_api):
    return {
        "summary": "Alex remembers the meeting.",
        "keywords": ["Alex", "meeting"],
        "embedding": [0.1, 0.2],
        "event_id": memory_api.event.id,
        "support_type": MemorySupportType.DIRECT,
        "character_links": [
            {
                "character_id": memory_api.character.id,
                "confidence": 0.9,
                "salience": Salience.MEDIUM,
                "behavioural_relevance": "May mention the meeting later.",
                "stance": MemoryStance.REMEMBER,
            }
        ],
    }


def test_create_list_get_update_relationships_and_delete_memory(memory_api):
    client = memory_api.client

    create_response = client.post("/memories", json=memory_payload(memory_api))

    assert create_response.status_code == 200
    memory = create_response.json()
    assert memory["summary"] == "Alex remembers the meeting."
    assert client.get("/memories").json() == [memory]
    assert client.get("/memories", params={"character_id": memory_api.character.id}).json() == [memory]
    assert client.get("/memories", params={"event_id": memory_api.event.id}).json() == [memory]
    assert client.get(f"/memories/{memory['id']}").json() == memory

    update_response = client.patch(
        f"/memories/{memory['id']}",
        json={"summary": "Updated memory"},
    )
    characters_response = client.put(
        f"/memories/{memory['id']}/characters",
        json={
            "character_links": [
                {
                    "character_id": memory_api.second_character.id,
                    "confidence": 0.6,
                    "salience": Salience.LOW,
                    "stance": MemoryStance.DOUBT,
                }
            ]
        },
    )
    event_response = client.put(
        f"/memories/{memory['id']}/event",
        json={
            "event_id": memory_api.event.id,
            "support_type": MemorySupportType.REPORTED,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["summary"] == "Updated memory"
    assert characters_response.status_code == 200
    assert client.get("/memories", params={"character_id": memory_api.character.id}).json() == []
    assert client.get("/memories", params={"character_id": memory_api.second_character.id}).json() == [
        characters_response.json()
    ]
    assert event_response.status_code == 200
    assert client.request(
        "DELETE",
        f"/memories/{memory['id']}/characters",
        json={"character_ids": [memory_api.second_character.id]},
    ).status_code == 400

    delete_response = client.delete(f"/memories/{memory['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/memories/{memory['id']}").status_code == 404


def test_memory_endpoints_return_404_for_missing_resources(memory_api):
    missing_id = str(uuid4())

    assert memory_api.client.get(f"/memories/{missing_id}").status_code == 404
    assert memory_api.client.patch(f"/memories/{missing_id}", json={"summary": "Missing"}).status_code == 404
    assert memory_api.client.delete(f"/memories/{missing_id}").status_code == 404
    assert memory_api.client.post(
        "/memories",
        json={
            **memory_payload(memory_api),
            "event_id": missing_id,
        },
    ).status_code == 404
