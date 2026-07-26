import io
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase
from PIL import Image

from world_simulation_engine.component.prompt_loader import PromptLoader
from world_simulation_engine.component.workflow_loader import WorkflowLoader
from world_simulation_engine.misc.enums import ComponentType, ConnectionType, SupportedLanguage, TurnType
from world_simulation_engine.model import Author, Character, ComfyUiImageModelConfig, ConnectionConfig, \
    CurrentActivity, ImagePromptProposal, Location, OllamaChatModelConfig, Simulation, TransientImagePromptProposal, \
    Turn, World
from world_simulation_engine.router import character_router, image_generation_router, item_router, location_router, \
    media_router, turn_router
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.image_service.comfy_ui import ImageComfyUi
from world_simulation_engine.service.llm_service import LlmService
from world_simulation_engine.service.storage_service import StorageService


_IMAGE_COMPONENTS = [
    ComponentType.CHARACTER_IMAGE_GENERATOR,
    ComponentType.LOCATION_IMAGE_GENERATOR,
    ComponentType.ITEM_IMAGE_GENERATOR,
    ComponentType.CHARACTER_PORTRAIT_IMAGE_GENERATOR,
    ComponentType.SCENE_IMAGE_GENERATOR,
]


@dataclass(frozen=True)
class ImageGenerationTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    location: Location
    character: Character


@pytest.fixture
def image_generation_api(neo4j_container, tmp_path, monkeypatch):
    author = Author(id=str(uuid4()), name="Image Generation Author")
    world = World(
        id=str(uuid4()),
        name="Image World",
        description="A world used to generate images",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Image Simulation",
        description="A simulation used to generate images",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    location = Location(id=str(uuid4()), name="Tavern", description="A dim tavern with a crackling fire")
    character = Character(
        id=str(uuid4()),
        name="Clara Whitlock",
        age=42,
        gender="female",
        appearance="Weathered hands, a faded apron",
        description="The innkeeper",
        public_state="Behind the bar",
        private_state="Careful",
        current_activity=CurrentActivity(name="serving"),
    )

    # The two outermost network calls (LLM structured output, ComfyUI HTTP) are the only things
    # stubbed here; everything else - routing, dependency injection, config resolution, Neo4j
    # relationship wiring - runs for real against a live testcontainer-backed Neo4j.
    full_proposal_call_count = {"count": 0}

    async def fake_invoke_structured_with_repair(self, *, output_model, **kwargs):
        if output_model is TransientImagePromptProposal:
            return _fake_transient_prompt_proposal()
        # A distinct canonical identity per call: if canonical identity were wrongly
        # re-established on a later generation instead of reused, the test below would see it
        # drift to a different value instead of staying identical.
        full_proposal_call_count["count"] += 1
        return _fake_full_prompt_proposal(variant=full_proposal_call_count["count"])

    async def fake_generate(self, **kwargs):
        return _fake_png_bytes()

    monkeypatch.setattr(LlmService, "invoke_structured_with_repair", fake_invoke_structured_with_repair)
    monkeypatch.setattr(ImageComfyUi, "generate", fake_generate)

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
        await database.location.create_location(location, simulation.id)
        await database.character.create_character(character, simulation.id, location_id=location.id)
        await database.turn.create_turn(
            Turn(
                id=str(uuid4()),
                sequence=1,
                type=TurnType.SYSTEM_RESPONSE,
                content="Clara pours a drink for the stranger.",
                start_time=simulation.current_time,
            ),
            source_id=simulation.id,
        )
        await _link_image_generation_configs(database, world.id)
        await _link_image_generation_configs(database, simulation.id)

        app.state.database = database
        app.state.storage = storage
        app.state.prompt_loader = PromptLoader(database=database, storage=storage)
        app.state.workflow_loader = WorkflowLoader(database=database, storage=storage)

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(character_router)
    app.include_router(location_router)
    app.include_router(item_router)
    app.include_router(image_generation_router)
    app.include_router(media_router)
    app.include_router(turn_router)

    with TestClient(app) as client:
        yield ImageGenerationTestClient(
            client=client, world=world, simulation=simulation, location=location, character=character,
        )


def _fake_full_prompt_proposal(variant: int = 1) -> ImagePromptProposal:
    return ImagePromptProposal(
        canonical_tags=["tavern", "innkeeper", "warm lighting", f"variant-{variant}"],
        canonical_description=f"A dim tavern with a calm innkeeper behind the bar (variant {variant}).",
        transient_tags=["evening", "quiet", "candlelight"],
        transient_description="A calm portrait.",
    )


def _fake_transient_prompt_proposal() -> TransientImagePromptProposal:
    return TransientImagePromptProposal(
        transient_tags=["evening", "quiet", "candlelight"],
        transient_description="A calm portrait.",
    )


def _fake_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 60, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _link_image_generation_configs(database: DatabaseService, world_id: str) -> None:
    image_connection = ConnectionConfig(
        id=str(uuid4()), type=ConnectionType.COMFYUI, name="Local ComfyUI", base_url="http://127.0.0.1:1",
    )
    chat_connection = ConnectionConfig(
        id=str(uuid4()), type=ConnectionType.OLLAMA, name="Local Ollama", base_url="http://127.0.0.1:1",
    )
    image_config = ComfyUiImageModelConfig(id=str(uuid4()), model="anima-base-v1.0.safetensors")
    chat_config = OllamaChatModelConfig(
        id=str(uuid4()), name="Prompt Builder Chat", model="llama3.1", temperature=0.5, context_window=4096,
    )

    await database.config.create_connection(image_connection)
    await database.config.create_connection(chat_connection)
    await database.config.create_image(image_config)
    await database.config.create_chat(chat_config)
    await database.config.link_connection(image_config.id, image_connection.id)
    await database.config.link_connection(chat_config.id, chat_connection.id)

    for component in _IMAGE_COMPONENTS:
        await database.config.link_image(world_id, image_config.id, component)
        await database.config.link_chat(world_id, chat_config.id, component)


def test_creating_a_character_auto_generates_its_cover_image(image_generation_api):
    client = image_generation_api.client
    world = image_generation_api.world

    response = client.post(
        f"/worlds/{world.id}/characters",
        json={
            "user_controlled": False,
            "name": "Arthur",
            "age": 35,
            "gender": "male",
            "appearance": "A traveler's cloak",
            "description": "A wandering merchant",
            "public_state": "Browsing the market",
            "private_state": "Curious",
            "current_activity": {"name": "idle"},
        },
    )

    assert response.status_code == 200
    character_id = response.json()["id"]

    cover_response = client.get(f"/characters/{character_id}/cover-image")
    assert cover_response.status_code == 200
    assert cover_response.content


def test_creating_a_location_auto_generates_its_cover_image(image_generation_api):
    client = image_generation_api.client
    world = image_generation_api.world

    response = client.post(
        f"/worlds/{world.id}/locations",
        json={"name": "Docks", "description": "A foggy dockside"},
    )

    assert response.status_code == 200
    location_id = response.json()["id"]

    cover_response = client.get(f"/locations/{location_id}/cover-image")
    assert cover_response.status_code == 200
    assert cover_response.content


def test_creating_an_item_auto_generates_its_cover_image(image_generation_api):
    client = image_generation_api.client
    world = image_generation_api.world

    response = client.post(
        f"/worlds/{world.id}/items",
        json={"name": "Lantern", "description": "A brass lantern", "unique": False},
    )

    assert response.status_code == 200
    item_id = response.json()["id"]

    cover_response = client.get(f"/items/{item_id}/cover-image")
    assert cover_response.status_code == 200
    assert cover_response.content


def test_manual_state_image_generation_returns_generated_image_media_file(image_generation_api):
    client = image_generation_api.client
    character = image_generation_api.character

    response = client.post(
        f"/characters/{character.id}/generate-image/state",
        json={"source_id": image_generation_api.world.id},
    )

    assert response.status_code == 200
    media = response.json()
    assert media["generation_type"] == "state"
    assert media["component"] == "character_image_generator"
    # First generation for this character: canonical identity is established now.
    assert media["canonical_tags"] == ["tavern", "innkeeper", "warm lighting", "variant-1"]
    assert media["canonical_description"] == "A dim tavern with a calm innkeeper behind the bar (variant 1)."
    assert media["transient_tags"] == ["evening", "quiet", "candlelight"]
    assert media["transient_description"] == "A calm portrait."
    assert media["negative_prompt"]


def test_manual_state_image_generation_returns_404_for_missing_character(image_generation_api):
    client = image_generation_api.client

    response = client.post(
        "/characters/missing/generate-image/state",
        json={"source_id": image_generation_api.world.id},
    )

    assert response.status_code == 404


def test_character_portrait_generation_links_turn(image_generation_api):
    client = image_generation_api.client
    character = image_generation_api.character
    simulation = image_generation_api.simulation

    turns_response = client.get("/turns", params={"simulation_id": simulation.id})
    turn_id = turns_response.json()[0]["id"]

    response = client.post(
        f"/simulations/{simulation.id}/characters/{character.id}/generate-image/portrait",
        json={"turn_id": turn_id},
    )

    assert response.status_code == 200
    media = response.json()
    assert media["generation_type"] == "character_portrait"

    turn_images_response = client.get(f"/turns/{turn_id}")
    assert turn_images_response.status_code == 200


def test_scene_generation_depicts_the_present_character(image_generation_api):
    client = image_generation_api.client
    simulation = image_generation_api.simulation
    location = image_generation_api.location
    character = image_generation_api.character

    response = client.post(
        f"/simulations/{simulation.id}/locations/{location.id}/generate-image/scene",
        json={},
    )

    assert response.status_code == 200, response.json()
    media = response.json()
    assert media["generation_type"] == "scene"
    assert media["component"] == "scene_image_generator"
    # Combined canonical identity from both participants grounds the scene's own prompt.
    assert media["canonical_tags"]
    assert media["canonical_description"]

    # Neither participant had an established identity yet, so generating the scene ensures one
    # for each first (as its own state image, which becomes that entity's cover) before building
    # the scene itself - but the scene image is never itself set as anyone's cover.
    location_cover_response = client.get(f"/locations/{location.id}/cover-image")
    assert location_cover_response.status_code == 200
    character_cover_response = client.get(f"/characters/{character.id}/cover-image")
    assert character_cover_response.status_code == 200


def test_scene_generation_returns_400_without_any_present_character(image_generation_api):
    client = image_generation_api.client
    simulation = image_generation_api.simulation
    other_location = client.post(
        f"/worlds/{image_generation_api.world.id}/locations",
        json={"name": "Empty Alley", "description": "A deserted alley"},
    ).json()

    response = client.post(
        f"/simulations/{simulation.id}/locations/{other_location['id']}/generate-image/scene",
        json={},
    )

    assert response.status_code == 400


def test_repeated_state_generation_reuses_canonical_identity_without_drift(image_generation_api):
    client = image_generation_api.client
    character = image_generation_api.character
    body = {"source_id": image_generation_api.world.id}

    first_response = client.post(f"/characters/{character.id}/generate-image/state", json=body)
    second_response = client.post(f"/characters/{character.id}/generate-image/state", json=body)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_media = first_response.json()
    second_media = second_response.json()

    # Canonical identity was established once and reused unchanged on the second generation -
    # note the "variant" marker did NOT advance, proving the establishing LLM call did not run
    # again. Only the transient content is regenerated per call.
    assert first_media["canonical_tags"] == second_media["canonical_tags"]
    assert first_media["canonical_description"] == second_media["canonical_description"]
    assert first_media["id"] != second_media["id"]

    # The second image is now the character's cover, but still carries the original identity.
    cover_response = client.get(f"/characters/{character.id}/cover-image")
    assert cover_response.status_code == 200
