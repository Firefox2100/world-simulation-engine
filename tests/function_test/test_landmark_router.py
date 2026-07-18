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
from world_simulation_engine.router import landmark_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class LandmarkRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    second_location: Location


@pytest.fixture
def landmark_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Landmark API Author")
    world = World(
        id=str(uuid4()),
        name="Landmark World",
        description="A world used to create landmarks",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Landmark Simulation",
        description="A simulation used to create landmarks",
        current_time=world.starting_time,
    )
    location = Location(id=str(uuid4()), name="Library", description="A quiet library")
    second_location = Location(id=str(uuid4()), name="Lobby", description="A bright lobby")

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
        await database.location.create_location(location, world.id)
        await database.location.create_location(second_location, world.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(landmark_router)

    with TestClient(app) as client:
        yield LandmarkRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            location=location,
            second_location=second_location,
        )


def test_create_list_get_update_move_and_delete_landmark(landmark_api):
    client = landmark_api.client

    create_response = client.post(
        f"/locations/{landmark_api.location.id}/landmarks",
        json={"name": "Front Desk", "description": "A wooden desk"},
    )

    assert create_response.status_code == 200
    landmark = create_response.json()
    assert landmark["name"] == "Front Desk"
    assert client.get("/landmarks", params={"location_id": landmark_api.location.id}).json() == [landmark]
    assert client.get("/landmarks", params={"world_id": landmark_api.world.id}).json() == [landmark]
    assert client.get(f"/landmarks/{landmark['id']}").json() == landmark

    update_response = client.patch(
        f"/landmarks/{landmark['id']}",
        json={"name": "Updated Desk"},
    )
    move_response = client.put(
        f"/landmarks/{landmark['id']}/location",
        json={"location_id": landmark_api.second_location.id},
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Desk"
    assert move_response.status_code == 200
    assert client.get("/landmarks", params={"location_id": landmark_api.location.id}).json() == []
    assert client.get("/landmarks", params={"location_id": landmark_api.second_location.id}).json() == [
        move_response.json()
    ]

    delete_response = client.delete(f"/landmarks/{landmark['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/landmarks/{landmark['id']}").status_code == 404


def test_landmark_endpoints_return_404_for_missing_resources(landmark_api):
    missing_id = str(uuid4())

    assert landmark_api.client.get(f"/landmarks/{missing_id}").status_code == 404
    assert landmark_api.client.patch(f"/landmarks/{missing_id}", json={"name": "Missing"}).status_code == 404
    assert landmark_api.client.delete(f"/landmarks/{missing_id}").status_code == 404
    assert landmark_api.client.post(
        f"/locations/{missing_id}/landmarks",
        json={"name": "Missing", "description": "Missing"},
    ).status_code == 404
