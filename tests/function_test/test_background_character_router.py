from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, Landmark, Location, Simulation, World
from world_simulation_engine.router import background_character_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class BackgroundCharacterRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    landmark: Landmark


@pytest.fixture
def background_character_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Background API Author")
    world = World(
        id=str(uuid4()),
        name="Background World",
        description="A world used to create background characters",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Background Simulation",
        description="A simulation used to create background characters",
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
    app.include_router(background_character_router)

    with TestClient(app) as client:
        yield BackgroundCharacterRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            location=location,
            landmark=landmark,
        )


def background_character_payload(name: str = "Shopkeeper") -> dict:
    return {
        "name": name,
        "description": "A busy shopkeeper",
    }


def test_create_list_get_update_and_delete_background_character(background_character_api):
    client = background_character_api.client

    world_create_response = client.post(
        f"/worlds/{background_character_api.world.id}/background-characters",
        json=background_character_payload("Villager"),
    )
    simulation_create_response = client.post(
        f"/simulations/{background_character_api.simulation.id}/background-characters",
        json={
            **background_character_payload("Shopkeeper"),
            "location_id": background_character_api.location.id,
            "position": "behind the counter",
            "landmark_id": background_character_api.landmark.id,
        },
    )

    assert world_create_response.status_code == 200
    assert simulation_create_response.status_code == 200
    world_character = world_create_response.json()
    simulation_character = simulation_create_response.json()

    list_response = client.get("/background-characters")
    world_filter_response = client.get(
        "/background-characters",
        params={"world_id": background_character_api.world.id},
    )
    simulation_filter_response = client.get(
        "/background-characters",
        params={"simulation_id": background_character_api.simulation.id},
    )
    location_filter_response = client.get(
        "/background-characters",
        params={"location_id": background_character_api.location.id},
    )

    assert list_response.status_code == 200
    assert {
        character["id"]
        for character in list_response.json()
    } == {
        world_character["id"],
        simulation_character["id"],
    }
    assert world_filter_response.json() == [world_character]
    assert simulation_filter_response.json() == [simulation_character]
    assert location_filter_response.json() == [simulation_character]

    get_response = client.get(f"/background-characters/{simulation_character['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == simulation_character

    update_response = client.patch(
        f"/background-characters/{simulation_character['id']}",
        json={
            "name": "Updated Shopkeeper",
            "description": "Still busy",
            "location_id": background_character_api.location.id,
            "position": "beside the counter",
        },
    )

    assert update_response.status_code == 200
    updated_character = update_response.json()
    assert updated_character["id"] == simulation_character["id"]
    assert updated_character["name"] == "Updated Shopkeeper"

    delete_response = client.delete(f"/background-characters/{simulation_character['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/background-characters/{simulation_character['id']}").status_code == 404


def test_background_character_endpoints_return_404_for_missing_resources(background_character_api):
    client = background_character_api.client
    missing_character_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())
    missing_location_id = str(uuid4())
    missing_landmark_id = str(uuid4())

    assert client.get(f"/background-characters/{missing_character_id}").status_code == 404
    assert client.patch(
        f"/background-characters/{missing_character_id}",
        json={"name": "Missing"},
    ).status_code == 404
    assert client.delete(f"/background-characters/{missing_character_id}").status_code == 404
    assert client.post(
        f"/worlds/{missing_world_id}/background-characters",
        json=background_character_payload(),
    ).status_code == 404
    assert client.post(
        f"/simulations/{missing_simulation_id}/background-characters",
        json=background_character_payload(),
    ).status_code == 404
    assert client.post(
        f"/simulations/{background_character_api.simulation.id}/background-characters",
        json={
            **background_character_payload(),
            "location_id": missing_location_id,
        },
    ).status_code == 404
    assert client.post(
        f"/simulations/{background_character_api.simulation.id}/background-characters",
        json={
            **background_character_payload(),
            "landmark_id": missing_landmark_id,
        },
    ).status_code == 404
