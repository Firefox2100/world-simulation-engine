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
from world_simulation_engine.router import item_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class ItemRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    holder: Character
    owner: Character


@pytest.fixture
def item_api(neo4j_container):
    author = Author(
        id=str(uuid4()),
        name="Item API Author",
        url="https://example.com/authors/item-api",
    )
    world = World(
        id=str(uuid4()),
        name="Item World",
        description="A world used to create items",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/item",
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Item Simulation",
        description="A simulation used to create item stacks",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    location = Location(
        id=str(uuid4()),
        name="Store Room",
        description="A room for stack placement",
    )
    holder = Character(
        id=str(uuid4()),
        name="Holder",
        age=30,
        gender="unknown",
        appearance="A practical coat",
        description="A stack holder",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="idle"),
    )
    owner = Character(
        id=str(uuid4()),
        name="Owner",
        age=31,
        gender="unknown",
        appearance="A neat jacket",
        description="A stack owner",
        public_state="Observing",
        private_state="Counting inventory",
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
    app.include_router(item_router)

    with TestClient(app) as client:
        yield ItemRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            location=location,
            holder=holder,
            owner=owner,
        )


def item_payload(name: str = "Book in English") -> dict:
    return {
        "name": name,
        "description": "A conceptual item type",
        "unique": False,
    }


def test_create_list_get_update_and_delete_item(item_api):
    client = item_api.client

    world_create_response = client.post(
        f"/worlds/{item_api.world.id}/items",
        json=item_payload("Book in English"),
    )
    simulation_create_response = client.post(
        f"/simulations/{item_api.simulation.id}/items",
        json=item_payload("Simulation Ledger"),
    )

    assert world_create_response.status_code == 200
    assert simulation_create_response.status_code == 200
    world_item = world_create_response.json()
    simulation_item = simulation_create_response.json()
    assert world_item["name"] == "Book in English"
    assert simulation_item["name"] == "Simulation Ledger"

    list_response = client.get("/items")
    world_filter_response = client.get("/items", params={"world_id": item_api.world.id})
    simulation_filter_response = client.get("/items", params={"simulation_id": item_api.simulation.id})

    assert list_response.status_code == 200
    assert {
        item["id"]
        for item in list_response.json()
    } == {
        world_item["id"],
        simulation_item["id"],
    }
    assert world_filter_response.status_code == 200
    assert world_filter_response.json() == [world_item]
    assert simulation_filter_response.status_code == 200
    assert simulation_filter_response.json() == [simulation_item]

    get_response = client.get(f"/items/{world_item['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == world_item

    update_response = client.patch(
        f"/items/{world_item['id']}",
        json={"name": "Updated Book", "unique": True},
    )

    assert update_response.status_code == 200
    updated_item = update_response.json()
    assert updated_item["id"] == world_item["id"]
    assert updated_item["name"] == "Updated Book"
    assert updated_item["unique"] is True

    delete_response = client.delete(f"/items/{world_item['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/items/{world_item['id']}").status_code == 404


def test_create_list_get_update_and_delete_stack(item_api):
    client = item_api.client

    item_response = client.post(
        f"/worlds/{item_api.world.id}/items",
        json=item_payload(),
    )
    assert item_response.status_code == 200
    item = item_response.json()

    create_response = client.post(
        f"/simulations/{item_api.simulation.id}/items/{item['id']}/stacks",
        json={
            "quantity": 3,
            "quality": "well kept",
            "location_id": item_api.location.id,
            "position": "on the second shelf",
            "owner_id": item_api.owner.id,
        },
    )

    assert create_response.status_code == 200
    stack = create_response.json()
    assert stack["id"]
    assert stack["quantity"] == 3
    assert stack["quality"] == "well kept"

    list_response = client.get("/stacks")
    simulation_filter_response = client.get("/stacks", params={"simulation_id": item_api.simulation.id})
    item_filter_response = client.get("/stacks", params={"item_id": item["id"]})
    owner_filter_response = client.get("/stacks", params={"owner_id": item_api.owner.id})
    location_filter_response = client.get("/stacks", params={"location_id": item_api.location.id})

    assert list_response.status_code == 200
    assert stack in list_response.json()
    assert simulation_filter_response.status_code == 200
    assert simulation_filter_response.json() == [stack]
    assert item_filter_response.status_code == 200
    assert item_filter_response.json() == [stack]
    assert owner_filter_response.status_code == 200
    assert owner_filter_response.json() == [stack]
    assert location_filter_response.status_code == 200
    assert location_filter_response.json() == [stack]

    get_response = client.get(f"/stacks/{stack['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == stack

    update_response = client.patch(
        f"/stacks/{stack['id']}",
        json={
            "quantity": 2,
            "quality": "annotated",
            "holder_id": item_api.holder.id,
        },
    )

    assert update_response.status_code == 200
    updated_stack = update_response.json()
    assert updated_stack["id"] == stack["id"]
    assert updated_stack["quantity"] == 2
    assert updated_stack["quality"] == "annotated"
    assert client.get("/stacks", params={"holder_id": item_api.holder.id}).json() == [updated_stack]
    assert client.get("/stacks", params={"location_id": item_api.location.id}).json() == []

    location_response = client.put(
        f"/stacks/{stack['id']}/location",
        json={
            "location_id": item_api.location.id,
            "position": "on the counter",
        },
    )
    owner_response = client.put(
        f"/stacks/{stack['id']}/owner",
        json={"owner_id": item_api.owner.id},
    )

    assert location_response.status_code == 200
    located_stack = location_response.json()
    assert client.get("/stacks", params={"location_id": item_api.location.id}).json() == [located_stack]
    assert client.get("/stacks", params={"holder_id": item_api.holder.id}).json() == []
    assert owner_response.status_code == 200
    assert client.get("/stacks", params={"owner_id": item_api.owner.id}).json() == [owner_response.json()]

    holder_response = client.put(
        f"/stacks/{stack['id']}/holder",
        json={"holder_id": item_api.holder.id},
    )

    assert holder_response.status_code == 200
    held_stack = holder_response.json()
    assert client.get("/stacks", params={"holder_id": item_api.holder.id}).json() == [held_stack]
    assert client.delete(f"/stacks/{stack['id']}/owner").status_code == 204
    assert client.get("/stacks", params={"owner_id": item_api.owner.id}).json() == []

    delete_response = client.delete(f"/stacks/{stack['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/stacks/{stack['id']}").status_code == 404


def test_item_endpoints_return_404_for_missing_resources(item_api):
    client = item_api.client
    missing_item_id = str(uuid4())
    missing_stack_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())
    missing_location_id = str(uuid4())

    get_item_response = client.get(f"/items/{missing_item_id}")
    update_item_response = client.patch(f"/items/{missing_item_id}", json={"name": "Missing"})
    delete_item_response = client.delete(f"/items/{missing_item_id}")
    world_create_response = client.post(f"/worlds/{missing_world_id}/items", json=item_payload())
    simulation_create_response = client.post(f"/simulations/{missing_simulation_id}/items", json=item_payload())
    get_stack_response = client.get(f"/stacks/{missing_stack_id}")
    update_stack_response = client.patch(f"/stacks/{missing_stack_id}", json={"quantity": 1})
    delete_stack_response = client.delete(f"/stacks/{missing_stack_id}")

    assert get_item_response.status_code == 404
    assert get_item_response.json()["detail"] == f"Item {missing_item_id} not found"
    assert update_item_response.status_code == 404
    assert update_item_response.json()["detail"] == f"Item {missing_item_id} not found"
    assert delete_item_response.status_code == 404
    assert delete_item_response.json()["detail"] == f"Item {missing_item_id} not found"
    assert world_create_response.status_code == 404
    assert world_create_response.json()["detail"] == f"World {missing_world_id} not found"
    assert simulation_create_response.status_code == 404
    assert simulation_create_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert get_stack_response.status_code == 404
    assert get_stack_response.json()["detail"] == f"Stack {missing_stack_id} not found"
    assert update_stack_response.status_code == 404
    assert update_stack_response.json()["detail"] == f"Stack {missing_stack_id} not found"
    assert delete_stack_response.status_code == 404
    assert delete_stack_response.json()["detail"] == f"Stack {missing_stack_id} not found"
    assert client.put(
        f"/stacks/{missing_stack_id}/location",
        json={"location_id": item_api.location.id},
    ).status_code == 404
    assert client.put(
        f"/stacks/{missing_stack_id}/holder",
        json={"holder_id": item_api.holder.id},
    ).status_code == 404
    assert client.put(
        f"/stacks/{missing_stack_id}/owner",
        json={"owner_id": item_api.owner.id},
    ).status_code == 404
    assert client.delete(f"/stacks/{missing_stack_id}/owner").status_code == 404

    item_response = client.post(f"/worlds/{item_api.world.id}/items", json=item_payload())
    assert item_response.status_code == 200
    item = item_response.json()

    missing_location_response = client.post(
        f"/simulations/{item_api.simulation.id}/items/{item['id']}/stacks",
        json={
            "quantity": 1,
            "location_id": missing_location_id,
        },
    )
    missing_holder_response = client.post(
        f"/simulations/{item_api.simulation.id}/items/{item['id']}/stacks",
        json={
            "quantity": 1,
            "holder_id": str(uuid4()),
        },
    )

    assert missing_location_response.status_code == 404
    assert missing_location_response.json()["detail"] == f"Location {missing_location_id} not found"
    assert missing_holder_response.status_code == 404
    assert missing_holder_response.json()["detail"].startswith("Holder ")


def test_stack_cannot_be_placed_and_held_at_the_same_time(item_api):
    client = item_api.client
    item_response = client.post(f"/worlds/{item_api.world.id}/items", json=item_payload())
    assert item_response.status_code == 200
    item = item_response.json()

    response = client.post(
        f"/simulations/{item_api.simulation.id}/items/{item['id']}/stacks",
        json={
            "quantity": 1,
            "location_id": item_api.location.id,
            "holder_id": item_api.holder.id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Stack cannot be placed in a location and held at the same time"


def test_stack_must_be_connected_when_created(item_api):
    client = item_api.client
    item_response = client.post(f"/worlds/{item_api.world.id}/items", json=item_payload())
    assert item_response.status_code == 200
    item = item_response.json()

    response = client.post(
        f"/simulations/{item_api.simulation.id}/items/{item['id']}/stacks",
        json={
            "quantity": 1,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Stack must be placed in a location or held by another entity"
