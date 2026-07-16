from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, Character, CurrentActivity, Location, Simulation, World
from world_simulation_engine.router import equipment_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class EquipmentRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    holder: Character
    owner: Character


@pytest.fixture
def equipment_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Equipment API Author")
    world = World(
        id=str(uuid4()),
        name="Equipment World",
        description="A world used to create equipment",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Equipment Simulation",
        description="A simulation used to create equipment",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    location = Location(id=str(uuid4()), name="Cave", description="A dark cave")
    holder = Character(
        id=str(uuid4()),
        name="Explorer",
        age=30,
        gender="unknown",
        appearance="Travel clothes",
        description="An explorer",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="idle"),
    )
    owner = Character(
        id=str(uuid4()),
        name="Collector",
        age=40,
        gender="unknown",
        appearance="A formal coat",
        description="A collector",
        public_state="Watching",
        private_state="Assessing",
        current_activity=CurrentActivity(name="idle"),
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
        await database.location.create_location(location, simulation.id)
        await database.character.create_character(holder, simulation.id)
        await database.character.create_character(owner, simulation.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(equipment_router)

    with TestClient(app) as client:
        yield EquipmentRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            location=location,
            holder=holder,
            owner=owner,
        )


def equipment_payload(name: str = "Lantern") -> dict:
    return {
        "name": name,
        "description": "A brass lantern",
        "quality": "worn",
    }


def test_create_list_get_update_and_delete_equipment(equipment_api):
    client = equipment_api.client

    world_create_response = client.post(
        f"/worlds/{equipment_api.world.id}/equipment",
        json=equipment_payload("Helmet"),
    )
    simulation_create_response = client.post(
        f"/simulations/{equipment_api.simulation.id}/equipment",
        json={
            **equipment_payload("Lantern"),
            "location_id": equipment_api.location.id,
            "position": "near the entrance",
            "owner_id": equipment_api.owner.id,
        },
    )

    assert world_create_response.status_code == 200
    assert simulation_create_response.status_code == 200
    world_equipment = world_create_response.json()
    simulation_equipment = simulation_create_response.json()

    list_response = client.get("/equipment")
    world_filter_response = client.get("/equipment", params={"world_id": equipment_api.world.id})
    simulation_filter_response = client.get("/equipment", params={"simulation_id": equipment_api.simulation.id})
    location_filter_response = client.get("/equipment", params={"location_id": equipment_api.location.id})
    owner_filter_response = client.get("/equipment", params={"owner_id": equipment_api.owner.id})

    assert list_response.status_code == 200
    assert {
        equipment["id"]
        for equipment in list_response.json()
    } == {
        world_equipment["id"],
        simulation_equipment["id"],
    }
    assert world_filter_response.json() == [world_equipment]
    assert simulation_filter_response.json() == [simulation_equipment]
    assert location_filter_response.json() == [simulation_equipment]
    assert owner_filter_response.json() == [simulation_equipment]

    get_response = client.get(f"/equipment/{simulation_equipment['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == simulation_equipment

    update_response = client.patch(
        f"/equipment/{simulation_equipment['id']}",
        json={
            "quality": "polished",
            "holder_id": equipment_api.holder.id,
            "equipped": True,
            "equipped_position": "left hand",
        },
    )

    assert update_response.status_code == 200
    updated_equipment = update_response.json()
    assert updated_equipment["id"] == simulation_equipment["id"]
    assert updated_equipment["quality"] == "polished"
    assert client.get("/equipment", params={"holder_id": equipment_api.holder.id}).json() == [updated_equipment]
    assert client.get("/equipment", params={"location_id": equipment_api.location.id}).json() == []

    delete_response = client.delete(f"/equipment/{simulation_equipment['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/equipment/{simulation_equipment['id']}").status_code == 404


def test_equipment_endpoints_return_404_for_missing_resources(equipment_api):
    client = equipment_api.client
    missing_equipment_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())
    missing_location_id = str(uuid4())
    missing_holder_id = str(uuid4())

    assert client.get(f"/equipment/{missing_equipment_id}").status_code == 404
    assert client.patch(f"/equipment/{missing_equipment_id}", json={"quality": "missing"}).status_code == 404
    assert client.delete(f"/equipment/{missing_equipment_id}").status_code == 404
    assert client.post(f"/worlds/{missing_world_id}/equipment", json=equipment_payload()).status_code == 404
    assert client.post(f"/simulations/{missing_simulation_id}/equipment", json=equipment_payload()).status_code == 404
    assert client.post(
        f"/simulations/{equipment_api.simulation.id}/equipment",
        json={
            **equipment_payload(),
            "location_id": missing_location_id,
        },
    ).status_code == 404
    assert client.post(
        f"/simulations/{equipment_api.simulation.id}/equipment",
        json={
            **equipment_payload(),
            "holder_id": missing_holder_id,
        },
    ).status_code == 404


def test_equipment_cannot_be_placed_and_held_at_the_same_time(equipment_api):
    response = equipment_api.client.post(
        f"/simulations/{equipment_api.simulation.id}/equipment",
        json={
            **equipment_payload(),
            "location_id": equipment_api.location.id,
            "holder_id": equipment_api.holder.id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Equipment cannot be placed in a location and held at the same time"
