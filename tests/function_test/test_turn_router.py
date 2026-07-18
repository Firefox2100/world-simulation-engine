from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage, TurnType
from world_simulation_engine.model import Author, Simulation, Turn, World
from world_simulation_engine.router import turn_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class TurnRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    turns: list[Turn]


@pytest.fixture
def turn_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Turn API Author")
    world = World(
        id=str(uuid4()),
        name="Turn World",
        description="A world used to read turns",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Turn Simulation",
        description="A simulation used to read turns",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    turns = [
        Turn(
            id=str(uuid4()),
            sequence=sequence,
            type=TurnType.USER_INPUT,
            content=f"Turn {sequence}",
            start_time=datetime(2026, 1, 1, 12, sequence, tzinfo=UTC),
        )
        for sequence in range(5)
    ]

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
        await database.simulation.create_simulation(simulation, world.id)
        previous_turn_id = None
        for turn in turns:
            await database.turn.create_turn(
                turn,
                simulation.id,
                previous_turn_id=previous_turn_id,
            )
            previous_turn_id = turn.id
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(turn_router)

    with TestClient(app) as client:
        yield TurnRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            turns=turns,
        )


def test_list_turns_returns_latest_turns_in_reverse_sequence(turn_api):
    response = turn_api.client.get(
        "/turns",
        params={
            "simulation_id": turn_api.simulation.id,
            "limit": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        turn_api.turns[4].model_dump(mode="json"),
        turn_api.turns[3].model_dump(mode="json"),
        turn_api.turns[2].model_dump(mode="json"),
    ]


def test_list_turns_can_skip_latest_turns(turn_api):
    response = turn_api.client.get(
        "/turns",
        params={
            "simulation_id": turn_api.simulation.id,
            "limit": 2,
            "skip": 1,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        turn_api.turns[3].model_dump(mode="json"),
        turn_api.turns[2].model_dump(mode="json"),
    ]


def test_get_turns_by_id_and_sequence(turn_api):
    turn = turn_api.turns[4]

    id_response = turn_api.client.get(f"/turns/{turn.id}")
    sequence_response = turn_api.client.get(
        f"/simulations/{turn_api.simulation.id}/turns/{turn.sequence}"
    )

    assert id_response.status_code == 200
    assert id_response.json() == turn.model_dump(mode="json")
    assert sequence_response.status_code == 200
    assert sequence_response.json() == turn.model_dump(mode="json")


def test_create_world_turn_validates_sequence(turn_api):
    client = turn_api.client

    first_response = client.post(
        f"/worlds/{turn_api.world.id}/turns",
        json={
            "sequence": 1,
            "type": TurnType.SYSTEM_RESPONSE,
            "content": "Opening world turn",
            "start_time": "2026-01-01T12:00:00Z",
        },
    )
    bad_sequence_response = client.post(
        f"/worlds/{turn_api.world.id}/turns",
        json={
            "sequence": 3,
            "type": TurnType.USER_INPUT,
            "content": "Skipped sequence",
            "start_time": "2026-01-01T12:01:00Z",
        },
    )
    second_response = client.post(
        f"/worlds/{turn_api.world.id}/turns",
        json={
            "sequence": 2,
            "type": TurnType.USER_INPUT,
            "content": "Second world turn",
            "start_time": "2026-01-01T12:01:00Z",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["sequence"] == 1
    assert bad_sequence_response.status_code == 400
    assert bad_sequence_response.json()["detail"] == "Turn sequence must be 2"
    assert second_response.status_code == 200
    assert second_response.json()["sequence"] == 2


def test_turn_endpoints_return_404_for_missing_resources(turn_api):
    missing_simulation_id = str(uuid4())
    missing_turn_id = str(uuid4())

    list_response = turn_api.client.get("/turns", params={"simulation_id": missing_simulation_id})
    get_response = turn_api.client.get(f"/turns/{missing_turn_id}")
    sequence_response = turn_api.client.get(f"/simulations/{turn_api.simulation.id}/turns/42")
    missing_simulation_sequence_response = turn_api.client.get(
        f"/simulations/{missing_simulation_id}/turns/0"
    )

    assert list_response.status_code == 404
    assert list_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Turn {missing_turn_id} not found"
    assert sequence_response.status_code == 404
    assert sequence_response.json()["detail"] == f"Turn 42 not found in simulation {turn_api.simulation.id}"
    assert missing_simulation_sequence_response.status_code == 404
    assert missing_simulation_sequence_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"


def test_turn_router_is_read_only(turn_api):
    turn = turn_api.turns[0]

    assert turn_api.client.post("/turns", json=turn.model_dump(mode="json")).status_code == 405
    assert turn_api.client.patch(f"/turns/{turn.id}", json={"content": "Updated"}).status_code == 405
    assert turn_api.client.delete(f"/turns/{turn.id}").status_code == 405
