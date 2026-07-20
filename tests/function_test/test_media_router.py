from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import ContainerState, SupportedLanguage
from world_simulation_engine.model import Author, BackgroundCharacter, Character, Container, CurrentActivity, Equipment, \
    Item, ItemStack, Landmark, Location, Simulation, World
from world_simulation_engine.router import media_router
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.storage_service import StorageService


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xf8"
    b"\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


@dataclass(frozen=True)
class MediaRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    character: Character
    background_character: BackgroundCharacter
    location: Location
    landmark: Landmark
    item: Item
    stack: ItemStack
    equipment: Equipment
    container: Container
    storage: StorageService


@pytest.fixture
def media_api(neo4j_container, tmp_path):
    author = Author(
        id=str(uuid4()),
        name="Media API Author",
    )
    world = World(
        id=str(uuid4()),
        name="Media World",
        description="A world with media",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Media Simulation",
        description="A simulation with media",
        current_time=world.starting_time,
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
        current_activity=CurrentActivity(name="observing"),
    )
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )
    location = Location(
        id=str(uuid4()),
        name="Market",
        description="A busy market",
    )
    landmark = Landmark(
        id=str(uuid4()),
        name="Fountain",
        description="A stone fountain",
    )
    item = Item(
        id=str(uuid4()),
        name="Book",
        description="A book in English",
        unique=False,
    )
    stack = ItemStack(
        id=str(uuid4()),
        quantity=3,
        quality="new",
    )
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.LOCKED,
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
        storage = StorageService(tmp_path / "storage")
        await storage.initialise()
        await database.world.create_author(author)
        await database.world.create_world(world, author.id)
        await database.simulation.create_simulation(simulation, world.id)
        await database.location.create_location(location, source_id=world.id)
        await database.location.create_landmark(landmark, location.id)
        await database.character.create_character(character, source_id=world.id)
        await database.character.create_background_character(background_character, source_id=world.id)
        await database.item.create_item(item, source_id=world.id)
        await database.item.create_stack(item.id, stack, source_id=world.id, location_id=location.id)
        await database.equipment.create_equipment(equipment, source_id=world.id, location_id=location.id)
        await database.container.create_container(container, source_id=world.id, location_id=location.id)
        app.state.database = database
        app.state.storage = storage

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(media_router)

    with TestClient(app) as client:
        yield MediaRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
            character=character,
            background_character=background_character,
            location=location,
            landmark=landmark,
            item=item,
            stack=stack,
            equipment=equipment,
            container=container,
            storage=app.state.storage,
        )


def _upload_media(client: TestClient, filename: str = "cover.png"):
    media_filename = "cover-image" if filename == "cover.png" else filename.rsplit(".", 1)[0]
    return client.post(
        "/media",
        data={
            "type": "image/png",
            "title": "Cover Image",
            "filename": media_filename,
        },
        files={
            "file": (filename, PNG_BYTES, "image/png"),
        },
    )


def test_upload_fetch_and_select_cover_images(media_api):
    client = media_api.client

    upload_response = _upload_media(client)

    assert upload_response.status_code == 200
    media = upload_response.json()
    second_media = _upload_media(client, filename="second.png").json()
    assert media["id"]
    assert media["type"] == "image/png"
    assert media["title"] == "Cover Image"
    assert media["filename"] == "cover-image"
    assert len(media["hash"]) == 64
    assert client.get("/media").json() == [media, second_media]
    assert client.get("/media", params={"type": "image/png"}).json() == [media, second_media]
    assert client.get("/media", params={"limit": 1}).json() == [media]
    assert client.get("/media", params={"limit": 1, "skip": 1}).json() == [second_media]
    assert client.get("/media", params={"world_id": media_api.world.id}).json() == []
    assert client.get("/media", params={"simulation_id": media_api.simulation.id}).json() == []

    fetch_response = client.get(f"/media/{media['id']}")

    assert fetch_response.status_code == 200
    assert fetch_response.headers["content-type"].startswith("image/png")
    assert fetch_response.content == PNG_BYTES

    world_cover_response = client.post(
        f"/worlds/{media_api.world.id}/cover-image",
        json={"media_id": media["id"]},
    )
    simulation_cover_response = client.post(
        f"/simulations/{media_api.simulation.id}/cover-image",
        json={"media_id": media["id"]},
    )

    assert world_cover_response.status_code == 200
    assert world_cover_response.json() == media
    assert simulation_cover_response.status_code == 200
    assert simulation_cover_response.json() == media
    assert client.get("/media", params={"world_id": media_api.world.id}).json() == [media]
    assert client.get("/media", params={"simulation_id": media_api.simulation.id}).json() == [media]
    assert client.get(
        "/media",
        params={
            "world_id": media_api.world.id,
            "simulation_id": media_api.simulation.id,
        },
    ).json() == [media]
    assert client.get(
        "/media",
        params={
            "world_id": media_api.world.id,
            "type": "image/png",
            "limit": 1,
            "skip": 0,
        },
    ).json() == [media]

    get_world_cover_response = client.get(f"/worlds/{media_api.world.id}/cover-image")
    get_simulation_cover_response = client.get(f"/simulations/{media_api.simulation.id}/cover-image")

    assert get_world_cover_response.status_code == 200
    assert get_world_cover_response.content == PNG_BYTES
    assert get_simulation_cover_response.status_code == 200
    assert get_simulation_cover_response.content == PNG_BYTES


def test_upload_and_attach_generic_media(media_api):
    client = media_api.client
    world_upload_response = client.post(
        f"/worlds/{media_api.world.id}/media",
        data={
            "title": "World image",
            "filename": "world-image",
        },
        files={
            "file": ("world.png", PNG_BYTES, "image/png"),
        },
    )
    existing_media = _upload_media(client, filename="character.png").json()
    attach_response = client.post(
        f"/characters/{media_api.character.id}/media-connections",
        json={"media_id": existing_media["id"]},
    )
    duplicate_attach_response = client.post(
        f"/characters/{media_api.character.id}/media-connections",
        json={"media_id": existing_media["id"]},
    )
    character_media_response = client.get(f"/characters/{media_api.character.id}/media")
    delete_response = client.delete(f"/characters/{media_api.character.id}/media/{existing_media['id']}")
    character_media_after_delete_response = client.get(f"/characters/{media_api.character.id}/media")

    assert world_upload_response.status_code == 200
    world_media = world_upload_response.json()
    assert world_media["type"] == "image/png"
    assert world_media["title"] == "World image"
    assert world_media["filename"] == "world-image"
    assert client.get(f"/worlds/{media_api.world.id}/media").json() == [world_media]
    assert client.get("/media", params={"world_id": media_api.world.id}).json() == [world_media]
    assert attach_response.status_code == 200
    assert attach_response.json() == existing_media
    assert duplicate_attach_response.status_code == 200
    assert character_media_response.json() == [existing_media]
    assert delete_response.status_code == 204
    assert character_media_after_delete_response.json() == []
    assert client.get(f"/media/{existing_media['id']}").status_code == 200


def test_concrete_entities_can_select_and_remove_cover_images(media_api):
    client = media_api.client
    media = _upload_media(client).json()
    cover_targets = [
        f"/worlds/{media_api.world.id}/cover-image",
        f"/simulations/{media_api.simulation.id}/cover-image",
        f"/characters/{media_api.character.id}/cover-image",
        f"/background-characters/{media_api.background_character.id}/cover-image",
        f"/locations/{media_api.location.id}/cover-image",
        f"/landmarks/{media_api.landmark.id}/cover-image",
        f"/items/{media_api.item.id}/cover-image",
        f"/stacks/{media_api.stack.id}/cover-image",
        f"/equipment/{media_api.equipment.id}/cover-image",
        f"/containers/{media_api.container.id}/cover-image",
    ]

    for cover_target in cover_targets:
        set_response = client.post(cover_target, json={"media_id": media["id"]})
        get_response = client.get(cover_target)
        delete_response = client.delete(cover_target)
        missing_cover_response = client.get(cover_target)
        media_response = client.get(f"/media/{media['id']}")

        assert set_response.status_code == 200
        assert set_response.json() == media
        assert get_response.status_code == 200
        assert get_response.content == PNG_BYTES
        assert delete_response.status_code == 204
        assert delete_response.content == b""
        assert missing_cover_response.status_code == 404
        assert media_response.status_code == 200


def test_cover_image_replaces_previous_media(media_api):
    client = media_api.client
    first_media = _upload_media(client, filename="first.png").json()
    second_media_response = client.post(
        "/media",
        data={
            "type": "image/png",
            "title": "Second Cover",
            "filename": "second-cover",
        },
        files={
            "file": ("second.png", PNG_BYTES + b"1", "image/png"),
        },
    )
    second_media = second_media_response.json()

    assert second_media_response.status_code == 200
    assert first_media["id"] != second_media["id"]
    assert first_media["hash"] != second_media["hash"]

    first_cover_response = client.post(
        f"/worlds/{media_api.world.id}/cover-image",
        json={"media_id": first_media["id"]},
    )
    second_cover_response = client.post(
        f"/worlds/{media_api.world.id}/cover-image",
        json={"media_id": second_media["id"]},
    )

    assert first_cover_response.status_code == 200
    assert second_cover_response.status_code == 200
    assert second_cover_response.json() == second_media
    assert client.get(f"/worlds/{media_api.world.id}/cover-image").content == PNG_BYTES + b"1"
    assert client.get(f"/worlds/{media_api.world.id}/media").json() == [first_media, second_media]


def test_delete_media_removes_file_only_when_hash_is_unreferenced(media_api):
    client = media_api.client
    first_media = _upload_media(client, filename="first.png").json()
    second_media = _upload_media(client, filename="second.png").json()

    assert first_media["id"] != second_media["id"]
    assert first_media["hash"] == second_media["hash"]
    assert media_api.storage.path_for(first_media["hash"]).exists()

    first_delete_response = client.delete(f"/media/{first_media['id']}")
    assert first_delete_response.status_code == 204
    assert media_api.storage.path_for(first_media["hash"]).exists()

    second_fetch_response = client.get(f"/media/{second_media['id']}")
    second_delete_response = client.delete(f"/media/{second_media['id']}")
    missing_media_response = client.get(f"/media/{second_media['id']}")

    assert second_fetch_response.status_code == 200
    assert second_fetch_response.content == PNG_BYTES
    assert second_delete_response.status_code == 204
    assert not media_api.storage.path_for(first_media["hash"]).exists()
    assert missing_media_response.status_code == 404


def test_media_endpoints_return_404_for_missing_resources(media_api):
    client = media_api.client
    missing_media_id = str(uuid4())
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())
    media = _upload_media(client).json()

    fetch_response = client.get(f"/media/{missing_media_id}")
    missing_world_set_response = client.post(
        f"/worlds/{missing_world_id}/cover-image",
        json={"media_id": media["id"]},
    )
    missing_media_set_response = client.post(
        f"/worlds/{media_api.world.id}/cover-image",
        json={"media_id": missing_media_id},
    )
    missing_world_get_response = client.get(f"/worlds/{missing_world_id}/cover-image")
    missing_cover_get_response = client.get(f"/simulations/{missing_simulation_id}/cover-image")
    missing_media_delete_response = client.delete(f"/media/{missing_media_id}")
    missing_world_delete_cover_response = client.delete(f"/worlds/{missing_world_id}/cover-image")

    assert fetch_response.status_code == 404
    assert fetch_response.json()["detail"] == f"Media {missing_media_id} not found"
    assert missing_world_set_response.status_code == 404
    assert missing_world_set_response.json()["detail"] == f"World {missing_world_id} not found"
    assert missing_media_set_response.status_code == 404
    assert missing_media_set_response.json()["detail"] == f"Media {missing_media_id} not found"
    assert missing_world_get_response.status_code == 404
    assert missing_world_get_response.json()["detail"] == f"World {missing_world_id} not found"
    assert missing_cover_get_response.status_code == 404
    assert missing_cover_get_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert missing_media_delete_response.status_code == 404
    assert missing_media_delete_response.json()["detail"] == f"Media {missing_media_id} not found"
    assert missing_world_delete_cover_response.status_code == 404
    assert missing_world_delete_cover_response.json()["detail"] == f"World {missing_world_id} not found"


def test_media_listing_rejects_invalid_pagination(media_api):
    client = media_api.client

    assert client.get("/media", params={"limit": 0}).status_code == 422
    assert client.get("/media", params={"skip": -1}).status_code == 422
    assert client.get("/media", params={"type": "text/plain"}).status_code == 422
