from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, SupportedLanguage, TurnType, \
    TtsGenerationMode
from world_simulation_engine.model import AllTalkXttsModelConfig, Author, Character, CharacterTtsConfig, \
    ConnectionConfig, CurrentActivity, PresentationBlockType, PresentationCompletion, Simulation, Turn, \
    TurnPresentationBlock, TurnPresentationRendering, World
from world_simulation_engine.router import config_router, turn_router
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.storage_service import StorageService
from world_simulation_engine.service.tts_service.alltalk_v2 import TtsAllTalkV2
from world_simulation_engine.service.tts_service.tts_result import TtsFileResult


@dataclass(frozen=True)
class TtsGenerationTestClient:
    client: TestClient
    world: World
    simulation: Simulation
    character: Character
    narration_block_id: str
    speech_block_id: str


@pytest.fixture
def tts_generation_api(neo4j_container, tmp_path, monkeypatch):
    author = Author(id=str(uuid4()), name="TTS Generation Author")
    world = World(
        id=str(uuid4()),
        name="TTS World",
        description="A world used to generate TTS audio",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="TTS Simulation",
        description="A simulation used to generate TTS audio",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    character = Character(
        id=str(uuid4()),
        name="Alice",
        age=30,
        gender="female",
        appearance="calm",
        description="A test character",
        public_state="idle",
        private_state="idle",
        current_activity=CurrentActivity(name="idle"),
    )
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    turn = Turn(id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="narration", start_time=now)
    narration_block = TurnPresentationBlock(
        id=str(uuid4()), turn_id=turn.id, sequence=0, type=PresentationBlockType.NARRATION,
        text="The room fell silent.", completion=PresentationCompletion.COMPLETE, created_at=now, updated_at=now,
    )
    speech_block = TurnPresentationBlock(
        id=str(uuid4()), turn_id=turn.id, sequence=1, type=PresentationBlockType.SPEECH,
        text="Hello there.", speaker_id=character.id, speaker_name=character.name,
        completion=PresentationCompletion.COMPLETE, created_at=now, updated_at=now,
    )

    generate_calls = []

    async def fake_generate_file(self, text, *, character_voice=None, language=None, output_file_name=None,
                                 rvc_character_voice=None, rvc_character_pitch=None):
        generate_calls.append({"text": text, "character_voice": character_voice})
        return TtsFileResult(audio=b"RIFF-fake-wav-bytes", content_type="audio/wav")

    monkeypatch.setattr(TtsAllTalkV2, "generate_file", fake_generate_file)

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
        await database.character.create_character(character, simulation.id)
        await database.turn.create_turn(turn, source_id=simulation.id)
        await database.turn_presentation.replace_rendering(
            TurnPresentationRendering(turn_id=turn.id, blocks=[narration_block, speech_block]),
        )

        connection = ConnectionConfig(
            id=str(uuid4()), type=ConnectionType.ALLTALK, name="Local AllTalk", base_url="http://localhost:7851",
        )
        backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en", narrator_voice="male_01.wav")
        await database.config.create_connection(connection)
        await database.config.create_tts(backend)
        await database.config.link_connection(backend.id, connection.id)
        await database.config.link_tts(simulation.id, backend.id, ComponentType.NARRATOR_TTS)
        await database.character_tts_config.set_character_tts_config(
            character.id, CharacterTtsConfig(character_voice="female_01.wav"),
        )

        app.state.database = database
        app.state.storage = storage
        app.state.generate_calls = generate_calls

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(config_router)
    app.include_router(turn_router)

    with TestClient(app) as client:
        yield TtsGenerationTestClient(
            client=client,
            world=world,
            simulation=simulation,
            character=character,
            narration_block_id=narration_block.id,
            speech_block_id=speech_block.id,
        ), app


def test_generate_narration_block_voice_uses_narrator_voice(tts_generation_api):
    client, app = tts_generation_api

    response = client.client.post(f"/turn-presentations/blocks/{client.narration_block_id}/voice")

    assert response.status_code == 200
    body = response.json()
    assert body["presentation_block_id"] == client.narration_block_id
    assert body["character_id"] is None
    assert body["voice_reference"] == "male_01.wav"
    assert body["text"] == "The room fell silent."
    assert app.state.generate_calls == [{"text": "The room fell silent.", "character_voice": "male_01.wav"}]


def test_generate_speech_block_voice_uses_character_voice(tts_generation_api):
    client, app = tts_generation_api

    response = client.client.post(f"/turn-presentations/blocks/{client.speech_block_id}/voice")

    assert response.status_code == 200
    body = response.json()
    assert body["character_id"] == client.character.id
    assert body["voice_reference"] == "female_01.wav"
    assert app.state.generate_calls == [{"text": "Hello there.", "character_voice": "female_01.wav"}]


def test_generate_block_voice_is_idempotent(tts_generation_api):
    client, app = tts_generation_api

    first = client.client.post(f"/turn-presentations/blocks/{client.narration_block_id}/voice")
    second = client.client.post(f"/turn-presentations/blocks/{client.narration_block_id}/voice")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(app.state.generate_calls) == 1


def test_generate_block_voice_returns_404_for_missing_block(tts_generation_api):
    client, _ = tts_generation_api

    response = client.client.post(f"/turn-presentations/blocks/{uuid4()}/voice")

    assert response.status_code == 404


def test_tts_generation_config_defaults_to_manual_and_can_be_set_to_auto(tts_generation_api):
    client, _ = tts_generation_api

    default_response = client.client.get(f"/simulations/{client.simulation.id}/tts-generation-config")
    assert default_response.status_code == 200
    assert default_response.json()["mode"] == TtsGenerationMode.MANUAL
    assert default_response.json()["autoplay_in_browser"] is False

    update_response = client.client.put(
        f"/simulations/{client.simulation.id}/tts-generation-config",
        json={"mode": "auto", "autoplay_in_browser": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["mode"] == TtsGenerationMode.AUTO
    assert update_response.json()["autoplay_in_browser"] is True

    get_response = client.client.get(f"/simulations/{client.simulation.id}/tts-generation-config")
    assert get_response.json()["mode"] == TtsGenerationMode.AUTO
    assert get_response.json()["autoplay_in_browser"] is True
    assert get_response.json()["id"] == update_response.json()["id"]
