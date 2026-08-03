from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.component.sillytavern_converter import AssembledWorld, ConversionReport
from world_simulation_engine.component.sillytavern_converter.world_reconstructor import WorldReconstructor
from world_simulation_engine.misc.enums import ComponentType, ConnectionType, SupportedLanguage
from world_simulation_engine.model import Author, ConnectionConfig, OllamaChatModelConfig
from world_simulation_engine.router import sillytavern_import_router
from world_simulation_engine.service import DatabaseService, StorageService

_CARD_PATH = Path("tests/evaluation_test/assets/st-cards/01.png")

_EXTRACT_CARD_PAYLOAD = {
    "name": "Kiki Mora",
    "description": "A streamer.",
    "personality": "Playful.",
    "scenario": "Streaming.",
    "first_message": "Hi chat!",
    "lorebook_entries": [
        {"name": "Stage 1", "keys": ["seal"], "content": "The seal breaks."},
    ],
}


def _canned_assembled_world() -> AssembledWorld:
    now = datetime.now(UTC).isoformat()
    return AssembledWorld(
        world={
            "name": "Kiki Mora", "description": "A streamer's world.",
            "starting_time": now, "language": "en",
        },
        sections={
            "locations": [], "landmarks": [],
            "characters": [{
                "id": "char-1", "user_controlled": False, "name": "Kiki", "age": 21,
                "gender": "female", "appearance": "Plain", "description": "A streamer.",
                "public_state": "Present", "private_state": "Thinking",
                "current_activity": {
                    "name": "idle", "started_at": None, "expected_end": None,
                    "interruptible": True, "constraints": [],
                },
                "speech_style": "playful",
            }],
            "background_characters": [], "items": [], "item_stacks": [], "equipment": [],
            "containers": [],
            "turns": [{
                "id": "turn-1", "sequence": 0, "type": "system_response", "content": "Hi!",
                "start_time": now,
            }],
            "events": [], "memories": [], "intents": [], "entity_relationships": [],
            "entity_variable_sets": [], "chat_configs": [], "embed_configs": [],
            "image_configs": [], "tts_configs": [], "prompts": [], "workflows": [], "media": [],
        },
        report=ConversionReport(),
    )


@pytest.fixture
def sillytavern_import_api(neo4j_container, tmp_path, monkeypatch):
    extract_calls = []

    async def fake_reconstruct_from_card(self, card, *, language):
        extract_calls.append({"card": card, "language": language})
        return _canned_assembled_world()

    monkeypatch.setattr(WorldReconstructor, "reconstruct_from_card", fake_reconstruct_from_card)

    author = Author(id=str(uuid4()), name="ST Import API Author")

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
        storage = StorageService(tmp_path / "storage")
        await storage.initialise()
        app.state.database = database
        app.state.storage = storage

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        yield client, author, extract_calls


def test_extract_sillytavern_card_returns_the_assembled_world_without_persisting(sillytavern_import_api):
    client, _author, extract_calls = sillytavern_import_api

    response = client.post(
        "/worlds/import/sillytavern/extract",
        json={"card": _EXTRACT_CARD_PAYLOAD, "language": SupportedLanguage.ENGLISH.value},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["world"]["name"] == "Kiki Mora"
    assert len(body["sections"]["characters"]) == 1
    assert len(extract_calls) == 1
    assert extract_calls[0]["language"] == SupportedLanguage.ENGLISH
    assert extract_calls[0]["card"].data.name == "Kiki Mora"
    assert extract_calls[0]["card"].data.first_mes == "Hi chat!"
    assert extract_calls[0]["card"].data.character_book.entries[0].content == "The seal breaks."


def test_extract_sillytavern_card_returns_409_when_no_chat_model_is_configured(sillytavern_import_api, monkeypatch):
    client, _author, _extract_calls = sillytavern_import_api

    async def failing_reconstruct(self, card, *, language):
        raise ValueError("No global chat model is configured for st_lorebook_classifier")

    monkeypatch.setattr(WorldReconstructor, "reconstruct_from_card", failing_reconstruct)

    response = client.post(
        "/worlds/import/sillytavern/extract",
        json={"card": _EXTRACT_CARD_PAYLOAD, "language": SupportedLanguage.ENGLISH.value},
    )

    assert response.status_code == 409


def test_commit_sillytavern_world_persists_the_assembled_world(sillytavern_import_api):
    client, author, _extract_calls = sillytavern_import_api
    assembled = _canned_assembled_world()

    response = client.post(
        "/worlds/import/sillytavern/commit",
        json={"world": assembled.world, "sections": assembled.sections, "author_id": author.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kiki Mora"
    assert body["description"] == "A streamer's world."


def test_commit_sillytavern_world_returns_404_for_missing_author(sillytavern_import_api):
    client, _author, _extract_calls = sillytavern_import_api
    assembled = _canned_assembled_world()

    response = client.post(
        "/worlds/import/sillytavern/commit",
        json={"world": assembled.world, "sections": assembled.sections, "author_id": str(uuid4())},
    )

    assert response.status_code == 404


async def test_get_sillytavern_import_status_reports_missing_components(sillytavern_import_api):
    client, _author, _extract_calls = sillytavern_import_api

    response = client.get("/worlds/import/sillytavern/status")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert ComponentType.ST_LOREBOOK_CLASSIFIER.value in body["missing_components"]


async def test_get_sillytavern_import_status_reports_configured_when_all_components_linked(
        sillytavern_import_api, neo4j_container,
):
    client, _author, _extract_calls = sillytavern_import_api

    driver = AsyncGraphDatabase.driver(
        neo4j_container.get_connection_url(), auth=("neo4j", "testpassword"),
    )
    database = DatabaseService(driver)
    connection = ConnectionConfig(
        id=str(uuid4()), type=ConnectionType.OLLAMA, name="Local", base_url="http://localhost:11434",
    )
    chat_config = OllamaChatModelConfig(id=str(uuid4()), name="Local Ollama", model="qwen")
    await database.config.create_connection(connection)
    await database.config.create_chat(chat_config)
    await database.config.link_connection(chat_config.id, connection.id)
    for component in (
            ComponentType.ST_LOREBOOK_CLASSIFIER, ComponentType.ST_CHARACTER_EXTRACTOR,
            ComponentType.ST_LOCATION_EXTRACTOR, ComponentType.ST_WORLD_LORE_EXTRACTOR,
            ComponentType.ST_NARRATIVE_EXTRACTOR, ComponentType.ST_INTENT_EXTRACTOR,
            ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR,
    ):
        await database.config.link_global_chat(chat_config.id, component)
    await driver.close()

    response = client.get("/worlds/import/sillytavern/status")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["missing_components"] == []


@pytest.mark.skipif(not _CARD_PATH.is_file(), reason=f"No sample card found at {_CARD_PATH}")
def test_parse_sillytavern_card_returns_raw_card_fields():
    app = FastAPI()
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        with _CARD_PATH.open("rb") as card_file:
            response = client.post(
                "/worlds/import/sillytavern/parse",
                files={"file": ("01.png", card_file, "image/png")},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kiki Mora"
    assert body["first_mes"]
    assert isinstance(body["lorebook_entries"], list) and len(body["lorebook_entries"]) == 3
    entry = body["lorebook_entries"][0]
    assert set(entry) >= {
        "id", "name", "comment", "keys", "secondary_keys", "content", "enabled",
        "insertion_order", "priority",
    }
    assert body["cover_image_data_uri"].startswith("data:image/png;base64,")


def test_parse_sillytavern_card_returns_400_for_a_non_card_file():
    app = FastAPI()
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        response = client.post(
            "/worlds/import/sillytavern/parse",
            files={"file": ("not-a-card.png", b"not a real png file", "image/png")},
        )

    assert response.status_code == 400
