from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, Location, Simulation, World
from world_simulation_engine.router import location_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class LocationRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation


@pytest.fixture
def location_api(neo4j_container):
    author = Author(
        id=str(uuid4()),
        name="Location API Author",
        url="https://example.com/authors/location-api",
    )
    world = World(
        id=str(uuid4()),
        name="Location World",
        description="A world used to create locations",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/location",
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Location Simulation",
        description="A simulation used to create locations",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
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
        await database.simulation.create_simulation(simulation, world.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(location_router)

    with TestClient(app) as client:
        yield LocationRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
        )


def test_create_list_get_update_and_delete_location(location_api):
    client = location_api.client

    world_create_response = client.post(
        f"/worlds/{location_api.world.id}/locations",
        json={"name": "City", "description": "A city"},
    )
    simulation_create_response = client.post(
        f"/simulations/{location_api.simulation.id}/locations",
        json={"name": "Harbor", "description": "A harbor"},
    )

    assert world_create_response.status_code == 200
    assert simulation_create_response.status_code == 200
    world_location = world_create_response.json()
    simulation_location = simulation_create_response.json()

    sub_location_response = client.post(
        f"/locations/{world_location['id']}/locations",
        json={"name": "Market", "description": "A market"},
    )

    assert sub_location_response.status_code == 200
    sub_location = sub_location_response.json()

    list_response = client.get("/locations")
    world_filter_response = client.get("/locations", params={"world_id": location_api.world.id})
    simulation_filter_response = client.get("/locations", params={"simulation_id": location_api.simulation.id})
    region_filter_response = client.get("/locations", params={"region_id": world_location["id"]})

    assert list_response.status_code == 200
    assert {
        location["id"]
        for location in list_response.json()
    } == {
        world_location["id"],
        simulation_location["id"],
        sub_location["id"],
    }
    assert world_filter_response.status_code == 200
    assert {
        location["id"]
        for location in world_filter_response.json()
    } == {
        world_location["id"],
        sub_location["id"],
    }
    assert simulation_filter_response.status_code == 200
    assert simulation_filter_response.json() == [simulation_location]
    assert region_filter_response.status_code == 200
    assert region_filter_response.json() == [sub_location]

    get_response = client.get(f"/locations/{world_location['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == world_location

    update_response = client.patch(
        f"/locations/{world_location['id']}",
        json={"name": "Updated City", "description": "An updated city"},
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": world_location["id"],
        "name": "Updated City",
        "description": "An updated city",
    }

    delete_response = client.delete(f"/locations/{world_location['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/locations/{world_location['id']}").status_code == 404


def test_location_endpoints_return_404_for_missing_resources(location_api):
    client = location_api.client
    missing_location_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())

    get_response = client.get(f"/locations/{missing_location_id}")
    update_response = client.patch(
        f"/locations/{missing_location_id}",
        json={"name": "Missing Location"},
    )
    delete_response = client.delete(f"/locations/{missing_location_id}")
    world_create_response = client.post(
        f"/worlds/{missing_world_id}/locations",
        json={"name": "Missing World Location", "description": "Missing world"},
    )
    simulation_create_response = client.post(
        f"/simulations/{missing_simulation_id}/locations",
        json={"name": "Missing Simulation Location", "description": "Missing simulation"},
    )
    sub_location_response = client.post(
        f"/locations/{missing_location_id}/locations",
        json={"name": "Missing Parent Location", "description": "Missing parent"},
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Location {missing_location_id} not found"
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == f"Location {missing_location_id} not found"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == f"Location {missing_location_id} not found"
    assert world_create_response.status_code == 404
    assert world_create_response.json()["detail"] == f"World {missing_world_id} not found"
    assert simulation_create_response.status_code == 404
    assert simulation_create_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert sub_location_response.status_code == 404
    assert sub_location_response.json()["detail"] == f"Location {missing_location_id} not found"
