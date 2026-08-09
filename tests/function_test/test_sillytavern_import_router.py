from contextlib import asynccontextmanager
from datetime import UTC, datetime
import asyncio
import base64
import io
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase
from PIL import Image, PngImagePlugin

from world_simulation_engine.component.sillytavern_converter import AssembledWorld, ConversionReport
from world_simulation_engine.component.sillytavern_converter.world_reconstructor import WorldReconstructor
from world_simulation_engine.misc.enums import ComponentType, ConnectionType, SupportedLanguage
from world_simulation_engine.model import Author, ConnectionConfig, OllamaChatModelConfig
from world_simulation_engine.router import sillytavern_import_router
from world_simulation_engine.router import sillytavern_import as sillytavern_import_module
from world_simulation_engine.service import DatabaseService, StorageService
from world_simulation_engine.service.media_download_service import MediaDownloadService

_EXTRACT_CARD_PAYLOAD = {
    "name": "Example Character",
    "description": "A fictional resident.",
    "personality": "Playful.",
    "scenario": "A generic test scenario.",
    "first_message": "Hello!",
    "lorebook_entries": [
        {"name": "Stage 1", "keys": ["seal"], "content": "The seal breaks."},
    ],
}


def _synthetic_card_png() -> bytes:
    payload = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            **_EXTRACT_CARD_PAYLOAD,
            "first_mes": _EXTRACT_CARD_PAYLOAD["first_message"],
            "mes_example": "",
            "creator_notes": "",
            "system_prompt": "",
            "post_history_instructions": "",
            "alternate_greetings": [],
            "tags": ["test"],
            "creator": "",
            "character_version": "",
            "extensions": {},
            "character_book": {
                "name": "Example lore",
                "entries": [{
                    "id": 1, "keys": ["seal"], "secondary_keys": [], "comment": "Stage 1",
                    "content": "The seal breaks.", "enabled": True, "insertion_order": 0,
                    "priority": 10, "constant": False, "position": "before_char", "use_regex": False,
                }],
            },
        },
    }
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("ccv3", base64.b64encode(json.dumps(payload).encode()).decode())
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def _synthetic_card_json() -> bytes:
    payload = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            **_EXTRACT_CARD_PAYLOAD,
            "first_mes": _EXTRACT_CARD_PAYLOAD["first_message"],
            "mes_example": "",
            "creator_notes": "",
            "system_prompt": "",
            "post_history_instructions": "",
            "alternate_greetings": [],
            "tags": ["test"],
            "creator": "",
            "character_version": "",
            "extensions": {},
            "character_book": {
                "name": "Example lore",
                "entries": [{
                    "id": 1, "keys": ["seal"], "secondary_keys": [], "comment": "Stage 1",
                    "content": "The seal breaks.", "enabled": True, "insertion_order": 0,
                    "priority": 10, "constant": False, "position": "before_char", "use_regex": False,
                }],
            },
        },
    }
    return json.dumps(payload).encode()


def _sse_events(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.text.split("\n\n"):
        if not block or block.startswith(":"):
            continue
        event = next(line[6:].strip() for line in block.splitlines() if line.startswith("event:"))
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        events.append((event, json.loads(data)))
    return events


def _assembled_from_sse(response) -> dict:
    result = {"sections": {}, "image_candidates": []}
    for event, data in _sse_events(response):
        if event == "world":
            result["world"] = data
        elif event == "section_start":
            result["sections"][data["name"]] = []
        elif event == "section_item":
            result["sections"].setdefault(data["name"], []).append(data["row"])
        elif event == "report":
            result["report"] = data
        elif event == "image_candidate":
            result["image_candidates"].append(data)
        elif event == "image_scan":
            result["image_scan"] = data
    return result


def _canned_assembled_world() -> AssembledWorld:
    now = datetime.now(UTC).isoformat()
    return AssembledWorld(
        world={
            "name": "Example Character", "description": "A fictional resident's world.",
            "starting_time": now, "language": "en",
        },
        sections={
            "locations": [], "landmarks": [],
            "characters": [{
                "id": "char-1", "user_controlled": False, "name": "Example", "age": 21,
                "gender": "female", "appearance": "Plain", "description": "A fictional resident.",
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
        app.state.media_download_service = MediaDownloadService()

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
    assert response.headers["content-type"].startswith("text/event-stream")
    body = _assembled_from_sse(response)
    assert body["world"]["name"] == "Example Character"
    assert len(body["sections"]["characters"]) == 1
    section_starts = [data for event, data in _sse_events(response) if event == "section_start"]
    assert {"name": "characters", "total": 1} in section_starts
    assert len(extract_calls) == 1
    assert extract_calls[0]["language"] == SupportedLanguage.ENGLISH
    assert extract_calls[0]["card"].data.name == "Example Character"
    assert extract_calls[0]["card"].data.first_mes == "Hello!"
    assert extract_calls[0]["card"].data.character_book.entries[0].content == "The seal breaks."


def test_extract_sillytavern_card_returns_empty_image_candidates_when_no_links_are_present(sillytavern_import_api):
    client, _author, _extract_calls = sillytavern_import_api

    response = client.post(
        "/worlds/import/sillytavern/extract",
        json={"card": _EXTRACT_CARD_PAYLOAD, "language": SupportedLanguage.ENGLISH.value},
    )

    assert response.status_code == 200
    body = _assembled_from_sse(response)
    assert body["image_candidates"] == []
    assert body["sections"]["media"] == []
    assert body["world"]["media_ids"] == []
    assert body["image_scan"] == {
        "found": 0, "auto_downloaded": 0, "awaiting_review": 0,
        "dropped_unsafe": 0, "dropped_non_image": 0, "failed_downloads": 0,
    }


def test_extract_sillytavern_card_drops_unsafe_image_links_without_any_network_call(
        sillytavern_import_api, monkeypatch,
):
    client, _author, _extract_calls = sillytavern_import_api

    async def always_unsafe(self, url):
        return False

    monkeypatch.setattr(MediaDownloadService, "is_safe_url", always_unsafe)

    payload = dict(_EXTRACT_CARD_PAYLOAD)
    payload["first_message"] = "See http://internal.example.com/secret.png"

    response = client.post(
        "/worlds/import/sillytavern/extract",
        json={"card": payload, "language": SupportedLanguage.ENGLISH.value},
    )

    assert response.status_code == 200
    body = _assembled_from_sse(response)
    assert body["image_candidates"] == []
    assert body["sections"]["media"] == []


def test_extract_sillytavern_card_streams_error_when_no_chat_model_is_configured(sillytavern_import_api, monkeypatch):
    client, _author, _extract_calls = sillytavern_import_api

    async def failing_reconstruct(self, card, *, language):
        raise ValueError("No global chat model is configured for st_lorebook_classifier")

    monkeypatch.setattr(WorldReconstructor, "reconstruct_from_card", failing_reconstruct)

    response = client.post(
        "/worlds/import/sillytavern/extract",
        json={"card": _EXTRACT_CARD_PAYLOAD, "language": SupportedLanguage.ENGLISH.value},
    )

    assert response.status_code == 200
    errors = [data for event, data in _sse_events(response) if event == "error"]
    assert errors[0]["detail"] == "No global chat model is configured for st_lorebook_classifier"


def test_extract_sillytavern_card_sends_keepalive_while_work_is_pending(sillytavern_import_api, monkeypatch):
    client, _author, _extract_calls = sillytavern_import_api

    async def slow_reconstruct(self, card, *, language):
        await asyncio.sleep(0.05)
        return _canned_assembled_world()

    monkeypatch.setattr(WorldReconstructor, "reconstruct_from_card", slow_reconstruct)
    monkeypatch.setattr(sillytavern_import_module, "_SSE_KEEPALIVE_SECONDS", 0.01)

    response = client.post(
        "/worlds/import/sillytavern/extract",
        json={"card": _EXTRACT_CARD_PAYLOAD, "language": SupportedLanguage.ENGLISH.value},
    )

    assert ": keep-alive\n\n" in response.text
    assert any(event == "complete" for event, _data in _sse_events(response))


def test_commit_sillytavern_world_persists_the_assembled_world(sillytavern_import_api):
    client, author, _extract_calls = sillytavern_import_api
    assembled = _canned_assembled_world()

    response = client.post(
        "/worlds/import/sillytavern/commit",
        json={"world": assembled.world, "sections": assembled.sections, "author_id": author.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Example Character"
    assert body["description"] == "A fictional resident's world."


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
            ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR, ComponentType.ST_ITEM_EXTRACTOR,
            ComponentType.ST_EQUIPMENT_EXTRACTOR,
            ComponentType.ST_OPENING_TURN_EXTRACTOR, ComponentType.ST_SPATIAL_STATE_EXTRACTOR,
            ComponentType.ST_PRIVATE_KNOWLEDGE_EXTRACTOR,
            ComponentType.ST_OPENING_NARRATIVE_EXTRACTOR,
    ):
        await database.config.link_global_chat(chat_config.id, component)
    await driver.close()

    response = client.get("/worlds/import/sillytavern/status")

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["missing_components"] == []


def test_parse_sillytavern_card_returns_raw_card_fields():
    app = FastAPI()
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        response = client.post(
            "/worlds/import/sillytavern/parse",
            files={"file": ("example.png", _synthetic_card_png(), "image/png")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Example Character"
    assert body["first_mes"]
    assert isinstance(body["lorebook_entries"], list) and len(body["lorebook_entries"]) == 1
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


def test_parse_sillytavern_card_accepts_a_plain_json_export_with_no_cover_image():
    app = FastAPI()
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        response = client.post(
            "/worlds/import/sillytavern/parse",
            files={"file": ("example.json", _synthetic_card_json(), "application/json")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Example Character"
    assert body["first_mes"]
    assert isinstance(body["lorebook_entries"], list) and len(body["lorebook_entries"]) == 1
    assert body["cover_image_data_uri"] is None


def test_parse_sillytavern_card_returns_400_for_unparsable_json():
    app = FastAPI()
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        response = client.post(
            "/worlds/import/sillytavern/parse",
            files={"file": ("broken.json", b"{not valid json", "application/json")},
        )

    assert response.status_code == 400


def test_parse_sillytavern_card_returns_400_for_json_missing_a_supported_spec():
    app = FastAPI()
    app.include_router(sillytavern_import_router)

    with TestClient(app) as client:
        response = client.post(
            "/worlds/import/sillytavern/parse",
            files={"file": ("legacy.json", json.dumps({"name": "No spec here"}).encode(), "application/json")},
        )

    assert response.status_code == 400
