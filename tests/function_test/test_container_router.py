from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import ContainerState, SupportedLanguage
from world_simulation_engine.model import Author, Character, Container, CurrentActivity, Equipment, Item, ItemStack, \
    Location, Simulation, World
from world_simulation_engine.router import container_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class ContainerRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    holder: Character
    owner: Character
    child_container: Container
    item: Item
    stack: ItemStack
    equipment: Equipment


@pytest.fixture
def container_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Container API Author")
    world = World(
        id=str(uuid4()),
        name="Container World",
        description="A world used to create containers",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Container Simulation",
        description="A simulation used to create containers",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    location = Location(id=str(uuid4()), name="Vault", description="A quiet vault")
    holder = Character(
        id=str(uuid4()),
        name="Holder",
        age=30,
        gender="unknown",
        appearance="A practical coat",
        description="A holder",
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
        description="An owner",
        public_state="Observing",
        private_state="Counting inventory",
        current_activity=CurrentActivity(name="idle"),
    )
    child_container = Container(
        id=str(uuid4()),
        name="Pouch",
        description="A leather pouch",
        state=ContainerState.UNLOCKED,
    )
    item = Item(id=str(uuid4()), name="Key", description="A brass key", unique=True)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="old")
    equipment = Equipment(id=str(uuid4()), name="Dagger", description="A short blade", quality="sharp")

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
        await database.container.create_container(child_container, simulation.id)
        await database.item.create_item(item, world.id)
        await database.item.create_stack(item.id, stack, source_id=simulation.id, holder_id=child_container.id)
        await database.equipment.create_equipment(equipment, simulation.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(container_router)

    with TestClient(app) as client:
        yield ContainerRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            location=location,
            holder=holder,
            owner=owner,
            child_container=child_container,
            item=item,
            stack=stack,
            equipment=equipment,
        )


def container_payload(name: str = "Chest") -> dict:
    return {
        "name": name,
        "description": "A wooden chest",
        "state": ContainerState.LOCKED,
    }


def test_create_list_get_update_and_delete_container(container_api):
    client = container_api.client

    world_create_response = client.post(
        f"/worlds/{container_api.world.id}/containers",
        json=container_payload("World Chest"),
    )
    simulation_create_response = client.post(
        f"/simulations/{container_api.simulation.id}/containers",
        json={
            **container_payload("Simulation Chest"),
            "location_id": container_api.location.id,
            "position": "against the wall",
            "owner_id": container_api.owner.id,
            "held_stack_ids": [container_api.stack.id],
            "held_equipment_ids": [container_api.equipment.id],
            "held_container_ids": [container_api.child_container.id],
            "unlocking_item_ids": [container_api.item.id],
        },
    )

    assert world_create_response.status_code == 200
    assert simulation_create_response.status_code == 200
    world_container = world_create_response.json()
    simulation_container = simulation_create_response.json()

    assert client.get("/containers", params={"world_id": container_api.world.id}).json() == [world_container]
    assert client.get("/containers", params={"simulation_id": container_api.simulation.id}).json() == [
        container_api.child_container.model_dump(mode="json"),
        simulation_container,
    ]
    assert client.get("/containers", params={"location_id": container_api.location.id}).json() == [
        simulation_container
    ]
    assert client.get("/containers", params={"owner_id": container_api.owner.id}).json() == [simulation_container]
    assert client.get(f"/containers/{simulation_container['id']}").json() == simulation_container
    assert client.get(f"/containers/{simulation_container['id']}/equipment").json() == [
        container_api.equipment.model_dump(mode="json")
    ]
    assert client.get(f"/containers/{simulation_container['id']}/containers").json() == [
        container_api.child_container.model_dump(mode="json")
    ]
    assert client.get(f"/containers/{simulation_container['id']}/unlocking-items").json() == [
        container_api.item.model_dump(mode="json")
    ]

    update_response = client.patch(
        f"/containers/{simulation_container['id']}",
        json={
            "state": ContainerState.UNLOCKED,
            "holder_id": container_api.holder.id,
        },
    )

    assert update_response.status_code == 200
    updated_container = update_response.json()
    assert updated_container["id"] == simulation_container["id"]
    assert updated_container["state"] == ContainerState.UNLOCKED
    assert client.get("/containers", params={"holder_id": container_api.holder.id}).json() == [updated_container]
    assert client.get("/containers", params={"location_id": container_api.location.id}).json() == []

    location_response = client.put(
        f"/containers/{simulation_container['id']}/location",
        json={
            "location_id": container_api.location.id,
            "position": "under the arch",
        },
    )
    owner_response = client.put(
        f"/containers/{simulation_container['id']}/owner",
        json={"owner_id": container_api.owner.id},
    )

    assert location_response.status_code == 200
    assert client.get("/containers", params={"location_id": container_api.location.id}).json() == [
        location_response.json()
    ]
    assert owner_response.status_code == 200
    assert client.get("/containers", params={"owner_id": container_api.owner.id}).json() == [owner_response.json()]

    holder_response = client.put(
        f"/containers/{simulation_container['id']}/holder",
        json={"holder_id": container_api.holder.id},
    )

    assert holder_response.status_code == 200
    assert client.get("/containers", params={"holder_id": container_api.holder.id}).json() == [
        holder_response.json()
    ]
    assert client.delete(f"/containers/{simulation_container['id']}/location").status_code == 204
    assert client.delete(f"/containers/{simulation_container['id']}/owner").status_code == 204
    assert client.delete(f"/containers/{simulation_container['id']}/holder").status_code == 204

    assert client.put(
        f"/containers/{simulation_container['id']}/stacks",
        json={"stack_ids": [container_api.stack.id]},
    ).status_code == 200
    assert client.put(
        f"/containers/{simulation_container['id']}/equipment",
        json={"equipment_ids": [container_api.equipment.id]},
    ).status_code == 200
    assert client.put(
        f"/containers/{simulation_container['id']}/containers",
        json={"container_ids": [container_api.child_container.id]},
    ).status_code == 200
    assert client.put(
        f"/containers/{simulation_container['id']}/unlocking-items",
        json={"item_ids": [container_api.item.id]},
    ).status_code == 200

    assert client.request(
        "DELETE",
        f"/containers/{simulation_container['id']}/stacks",
        json={"stack_ids": [container_api.stack.id]},
    ).status_code == 204
    assert client.request(
        "DELETE",
        f"/containers/{simulation_container['id']}/equipment",
        json={"equipment_ids": [container_api.equipment.id]},
    ).status_code == 204
    assert client.request(
        "DELETE",
        f"/containers/{simulation_container['id']}/containers",
        json={"container_ids": [container_api.child_container.id]},
    ).status_code == 204
    assert client.request(
        "DELETE",
        f"/containers/{simulation_container['id']}/unlocking-items",
        json={"item_ids": [container_api.item.id]},
    ).status_code == 204
    assert client.get(f"/containers/{simulation_container['id']}/equipment").json() == []
    assert client.get(f"/containers/{simulation_container['id']}/containers").json() == []
    assert client.get(f"/containers/{simulation_container['id']}/unlocking-items").json() == []

    delete_response = client.delete(f"/containers/{simulation_container['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/containers/{simulation_container['id']}").status_code == 404


def test_container_endpoints_return_404_for_missing_resources(container_api):
    client = container_api.client
    missing_container_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())
    missing_location_id = str(uuid4())

    assert client.get(f"/containers/{missing_container_id}").status_code == 404
    assert client.patch(f"/containers/{missing_container_id}", json={"state": ContainerState.OPEN}).status_code == 404
    assert client.delete(f"/containers/{missing_container_id}").status_code == 404
    assert client.put(
        f"/containers/{missing_container_id}/location",
        json={"location_id": container_api.location.id},
    ).status_code == 404
    assert client.put(
        f"/containers/{missing_container_id}/owner",
        json={"owner_id": container_api.owner.id},
    ).status_code == 404
    assert client.put(
        f"/containers/{missing_container_id}/holder",
        json={"holder_id": container_api.holder.id},
    ).status_code == 404
    assert client.delete(f"/containers/{missing_container_id}/location").status_code == 404
    assert client.delete(f"/containers/{missing_container_id}/owner").status_code == 404
    assert client.delete(f"/containers/{missing_container_id}/holder").status_code == 404
    assert client.put(f"/containers/{missing_container_id}/stacks", json={"stack_ids": []}).status_code == 404
    assert client.request(
        "DELETE",
        f"/containers/{missing_container_id}/stacks",
        json={"stack_ids": []},
    ).status_code == 404
    assert client.post(f"/worlds/{missing_world_id}/containers", json=container_payload()).status_code == 404
    assert client.post(f"/simulations/{missing_simulation_id}/containers", json=container_payload()).status_code == 404
    assert client.post(
        f"/simulations/{container_api.simulation.id}/containers",
        json={
            **container_payload(),
            "location_id": missing_location_id,
        },
    ).status_code == 404


def test_container_cannot_be_placed_and_held_at_the_same_time(container_api):
    response = container_api.client.post(
        f"/simulations/{container_api.simulation.id}/containers",
        json={
            **container_payload(),
            "location_id": container_api.location.id,
            "holder_id": container_api.holder.id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Container cannot be placed in a location and held at the same time"
