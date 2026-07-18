from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, Character, CurrentActivity, Landmark, Location, Simulation, World
from world_simulation_engine.router import character_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class CharacterRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    landmark: Landmark


@pytest.fixture
def character_api(neo4j_container):
    author = Author(
        id=str(uuid4()),
        name="Character API Author",
        url="https://example.com/authors/character-api",
    )
    world = World(
        id=str(uuid4()),
        name="Character World",
        description="A world used to create characters",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/character",
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Character Simulation",
        description="A simulation used to create characters",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    location = Location(id=str(uuid4()), name="Market", description="A market")
    landmark = Landmark(id=str(uuid4()), name="Counter", description="A shop counter")

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
        await database.location.create_location(location, simulation.id)
        await database.location.create_landmark(landmark, location.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(character_router)

    with TestClient(app) as client:
        yield CharacterRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            location=location,
            landmark=landmark,
        )


def character_payload(name: str = "Alex") -> dict:
    return {
        "user_controlled": False,
        "name": name,
        "age": 30,
        "gender": "non-binary",
        "appearance": "Short hair and a practical coat",
        "description": "A test character",
        "public_state": "Waiting",
        "private_state": "Planning",
        "current_activity": {
            "name": "observing",
            "started_at": "2026-01-01T09:00:00Z",
            "expected_end": "2026-01-01T10:00:00Z",
            "interruptible": True,
            "constraints": ["quiet"],
        },
    }


def test_create_list_get_update_and_delete_character(character_api):
    client = character_api.client

    world_create_response = client.post(
        f"/worlds/{character_api.world.id}/characters",
        json=character_payload("Alex"),
    )
    simulation_create_response = client.post(
        f"/simulations/{character_api.simulation.id}/characters",
        json=character_payload("Blair"),
    )

    assert world_create_response.status_code == 200
    assert simulation_create_response.status_code == 200
    world_character = world_create_response.json()
    simulation_character = simulation_create_response.json()
    assert world_character["id"]
    assert simulation_character["id"]
    assert world_character["name"] == "Alex"
    assert simulation_character["name"] == "Blair"

    list_response = client.get("/characters")
    world_filter_response = client.get("/characters", params={"world_id": character_api.world.id})
    simulation_filter_response = client.get(
        "/characters",
        params={"simulation_id": character_api.simulation.id},
    )

    assert list_response.status_code == 200
    assert {
        character["id"]
        for character in list_response.json()
    } == {
        world_character["id"],
        simulation_character["id"],
    }
    assert world_filter_response.status_code == 200
    assert world_filter_response.json() == [world_character]
    assert simulation_filter_response.status_code == 200
    assert simulation_filter_response.json() == [simulation_character]

    get_response = client.get(f"/characters/{world_character['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == world_character

    update_response = client.patch(
        f"/characters/{world_character['id']}",
        json={
            "name": "Updated Alex",
            "age": 31,
            "current_activity": {
                "name": "walking",
                "started_at": "2026-01-01T11:00:00Z",
                "interruptible": True,
                "constraints": [],
            },
        },
    )

    assert update_response.status_code == 200
    updated_character = update_response.json()
    assert updated_character["id"] == world_character["id"]
    assert updated_character["name"] == "Updated Alex"
    assert updated_character["age"] == 31
    assert updated_character["current_activity"]["name"] == "walking"

    location_response = client.put(
        f"/characters/{world_character['id']}/location",
        json={
            "location_id": character_api.location.id,
            "position": "near the counter",
        },
    )
    landmark_response = client.put(
        f"/characters/{world_character['id']}/landmark",
        json={"landmark_id": character_api.landmark.id},
    )

    assert location_response.status_code == 200
    assert client.get("/characters", params={"location_id": character_api.location.id}).json() == [
        location_response.json()
    ]
    assert landmark_response.status_code == 200
    assert client.delete(f"/characters/{world_character['id']}/location").status_code == 204
    assert client.delete(f"/characters/{world_character['id']}/landmark").status_code == 204
    assert client.get("/characters", params={"location_id": character_api.location.id}).json() == []

    delete_response = client.delete(f"/characters/{world_character['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/characters/{world_character['id']}").status_code == 404


def test_character_endpoints_return_404_for_missing_resources(character_api):
    client = character_api.client
    missing_character_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())

    get_response = client.get(f"/characters/{missing_character_id}")
    update_response = client.patch(
        f"/characters/{missing_character_id}",
        json={"name": "Missing Character"},
    )
    delete_response = client.delete(f"/characters/{missing_character_id}")
    set_location_response = client.put(
        f"/characters/{missing_character_id}/location",
        json={"location_id": character_api.location.id},
    )
    set_landmark_response = client.put(
        f"/characters/{missing_character_id}/landmark",
        json={"landmark_id": character_api.landmark.id},
    )
    world_create_response = client.post(
        f"/worlds/{missing_world_id}/characters",
        json=character_payload(),
    )
    simulation_create_response = client.post(
        f"/simulations/{missing_simulation_id}/characters",
        json=character_payload(),
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Character {missing_character_id} not found"
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == f"Character {missing_character_id} not found"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == f"Character {missing_character_id} not found"
    assert set_location_response.status_code == 404
    assert set_landmark_response.status_code == 404
    assert client.delete(f"/characters/{missing_character_id}/location").status_code == 404
    assert client.delete(f"/characters/{missing_character_id}/landmark").status_code == 404
    assert world_create_response.status_code == 404
    assert world_create_response.json()["detail"] == f"World {missing_world_id} not found"
    assert simulation_create_response.status_code == 404
    assert simulation_create_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
