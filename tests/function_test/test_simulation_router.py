from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, BackgroundCharacter, Character, CurrentActivity, Equipment, \
    Landmark, Location, World
from world_simulation_engine.router import background_character_router, character_router, equipment_router, \
    location_router, simulation_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class SimulationRouterTestClient:
    client: TestClient
    author: Author
    other_author: Author
    world: World
    other_world: World
    world_character: Character
    background_character: BackgroundCharacter
    equipment: Equipment
    city: Location
    market: Location
    landmark: Landmark


@pytest.fixture
def simulation_api(neo4j_container):
    author = Author(
        id=str(uuid4()),
        name="Simulation API Author",
        url="https://example.com/authors/simulation-api",
    )
    other_author = Author(
        id=str(uuid4()),
        name="Other Simulation API Author",
        url="https://example.com/authors/other-simulation-api",
    )
    world = World(
        id=str(uuid4()),
        name="Simulation World",
        description="A world used to create simulations",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/simulation",
        language=SupportedLanguage.ENGLISH,
    )
    other_world = World(
        id=str(uuid4()),
        name="Other Simulation World",
        description="Another world used to create simulations",
        starting_time=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/other-simulation",
        language=SupportedLanguage.CHINESE,
    )
    world_character = Character(
        id=str(uuid4()),
        user_controlled=True,
        name="Alex",
        age=30,
        gender="non-binary",
        appearance="Short hair and a practical coat",
        description="A test character",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="observing"),
    )
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    city = Location(
        id=str(uuid4()),
        name="City",
        description="A city",
    )
    market = Location(
        id=str(uuid4()),
        name="Market",
        description="A market",
    )
    landmark = Landmark(
        id=str(uuid4()),
        name="Fountain",
        description="A fountain",
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
        await database.world.create_author(other_author)
        await database.world.create_world(world, author.id)
        await database.world.create_world(other_world, other_author.id)
        await database.location.create_location(city, source_id=world.id)
        await database.location.create_location(market, source_id=world.id, contained_in=city.id)
        await database.location.create_landmark(landmark, market.id)
        await database.character.create_character(world_character, world.id)
        await database.character.move_to_location(world_character.id, market.id, position="near the stalls")
        await database.character.anchor_to_landmark(world_character.id, landmark.id)
        await database.character.create_background_character(
            background_character,
            world.id,
            location_id=market.id,
            position="behind the counter",
            landmark_id=landmark.id,
        )
        await database.equipment.create_equipment(equipment, world.id)
        await database.equipment.change_owner(equipment.id, world_character.id)
        await database.equipment.change_hold_state(
            equipment.id,
            world_character.id,
            equipped=True,
            equipped_position="left hand",
        )
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(background_character_router)
    app.include_router(simulation_router)
    app.include_router(character_router)
    app.include_router(equipment_router)
    app.include_router(location_router)

    with TestClient(app) as client:
        yield SimulationRouterTestClient(
            client=client,
            author=author,
            other_author=other_author,
            world=world,
            other_world=other_world,
            world_character=world_character,
            background_character=background_character,
            equipment=equipment,
            city=city,
            market=market,
            landmark=landmark,
        )


def test_create_list_get_update_and_delete_simulation(simulation_api):
    client = simulation_api.client

    create_response = client.post(f"/worlds/{simulation_api.world.id}/simulations")

    assert create_response.status_code == 200
    created_simulation = create_response.json()
    assert created_simulation["id"]
    assert created_simulation["name"] == simulation_api.world.name
    assert created_simulation["description"] == simulation_api.world.description
    assert created_simulation["current_time"] == "2026-01-01T12:00:00Z"

    copied_characters_response = client.get(
        "/characters",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_locations_response = client.get(
        "/locations",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_background_characters_response = client.get(
        "/background-characters",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_equipment_response = client.get(
        "/equipment",
        params={"simulation_id": created_simulation["id"]},
    )

    assert copied_characters_response.status_code == 200
    assert len(copied_characters_response.json()) == 1
    copied_character = copied_characters_response.json()[0]
    assert copied_character["id"] != simulation_api.world_character.id
    assert copied_character == {
        **simulation_api.world_character.model_dump(mode="json"),
        "id": copied_character["id"],
    }
    assert copied_locations_response.status_code == 200
    assert {
        location["name"]
        for location in copied_locations_response.json()
    } == {
        simulation_api.city.name,
        simulation_api.market.name,
    }
    assert all(
        location["id"] not in {simulation_api.city.id, simulation_api.market.id}
        for location in copied_locations_response.json()
    )
    copied_market = next(
        location
        for location in copied_locations_response.json()
        if location["name"] == simulation_api.market.name
    )
    assert copied_background_characters_response.status_code == 200
    assert len(copied_background_characters_response.json()) == 1
    copied_background_character = copied_background_characters_response.json()[0]
    assert copied_background_character["id"] != simulation_api.background_character.id
    assert copied_background_character == {
        **simulation_api.background_character.model_dump(mode="json"),
        "id": copied_background_character["id"],
    }
    assert client.get(
        "/background-characters",
        params={"location_id": copied_market["id"]},
    ).json() == [copied_background_character]
    assert copied_equipment_response.status_code == 200
    assert len(copied_equipment_response.json()) == 1
    copied_equipment = copied_equipment_response.json()[0]
    assert copied_equipment["id"] != simulation_api.equipment.id
    assert copied_equipment == {
        **simulation_api.equipment.model_dump(mode="json"),
        "id": copied_equipment["id"],
    }
    assert client.get(
        "/equipment",
        params={"holder_id": copied_character["id"]},
    ).json() == [copied_equipment]

    other_create_response = client.post(f"/worlds/{simulation_api.other_world.id}/simulations")
    other_simulation = other_create_response.json()

    assert other_create_response.status_code == 200

    list_response = client.get("/simulations")

    assert list_response.status_code == 200
    assert {
        simulation["id"]
        for simulation in list_response.json()
    } == {
        created_simulation["id"],
        other_simulation["id"],
    }

    author_filter_response = client.get("/simulations", params={"author_id": simulation_api.author.id})
    world_filter_response = client.get("/simulations", params={"world_id": simulation_api.world.id})
    combined_filter_response = client.get(
        "/simulations",
        params={
            "author_id": simulation_api.author.id,
            "world_id": simulation_api.other_world.id,
        },
    )

    assert author_filter_response.status_code == 200
    assert author_filter_response.json() == [created_simulation]
    assert world_filter_response.status_code == 200
    assert world_filter_response.json() == [created_simulation]
    assert combined_filter_response.status_code == 200
    assert combined_filter_response.json() == []

    get_response = client.get(f"/simulations/{created_simulation['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_simulation

    update_response = client.patch(
        f"/simulations/{created_simulation['id']}",
        json={
            "name": "Updated Simulation",
            "description": "Updated through the simulation API",
            "current_time": "2026-03-01T12:00:00Z",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": created_simulation["id"],
        "name": "Updated Simulation",
        "description": "Updated through the simulation API",
        "current_time": "2026-03-01T12:00:00Z",
    }

    delete_response = client.delete(f"/simulations/{created_simulation['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/simulations/{created_simulation['id']}").status_code == 404


def test_simulation_endpoints_return_404_for_missing_resources(simulation_api):
    client = simulation_api.client
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())

    create_response = client.post(f"/worlds/{missing_world_id}/simulations")
    get_response = client.get(f"/simulations/{missing_simulation_id}")
    update_response = client.patch(
        f"/simulations/{missing_simulation_id}",
        json={"name": "Missing Simulation"},
    )
    delete_response = client.delete(f"/simulations/{missing_simulation_id}")

    assert create_response.status_code == 404
    assert create_response.json()["detail"] == f"World {missing_world_id} not found"
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
