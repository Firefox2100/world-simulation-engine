from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import ConnectionConfig, WhisperCppSttModelConfig
from world_simulation_engine.router import speech_recognition_router
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.stt_service.stt_result import SttTranscriptionResult
from world_simulation_engine.service.stt_service.whisper_cpp import SttWhisperCpp


@pytest.fixture
def speech_recognition_api(neo4j_container, monkeypatch):
    transcribe_calls = []

    async def fake_transcribe(self, audio, *, filename="audio.wav", content_type=None, language=None):
        transcribe_calls.append({"audio": audio, "filename": filename, "language": language})
        return SttTranscriptionResult(text="hello world", language=language or "en")

    monkeypatch.setattr(SttWhisperCpp, "transcribe", fake_transcribe)

    def make_client(*, configure_stt=True, link_connection=True):
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            driver = AsyncGraphDatabase.driver(
                neo4j_container.get_connection_url(),
                auth=("neo4j", "testpassword"),
            )
            await driver.verify_connectivity()
            await driver.execute_query("MATCH (n) DETACH DELETE n")

            database = DatabaseService(driver)

            if configure_stt:
                connection = ConnectionConfig(
                    id=str(uuid4()), type=ConnectionType.WHISPERCPP, name="Local whisper.cpp",
                    base_url="http://localhost:8080",
                )
                stt_config = WhisperCppSttModelConfig(id=str(uuid4()), language="en")
                await database.config.create_connection(connection)
                await database.config.create_stt(stt_config)
                if link_connection:
                    await database.config.link_connection(stt_config.id, connection.id)

            app.state.database = database

            try:
                yield
            finally:
                await driver.execute_query("MATCH (n) DETACH DELETE n")
                await driver.close()

        app = FastAPI(lifespan=lifespan)
        app.include_router(speech_recognition_router)

        return app

    return make_client, transcribe_calls


def test_transcribe_speech_returns_text(speech_recognition_api):
    make_client, transcribe_calls = speech_recognition_api

    with TestClient(make_client()) as client:
        response = client.post(
            "/speech-recognition/transcribe",
            files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "hello world"
    assert body["language"] == "en"
    assert transcribe_calls == [
        {"audio": b"fake-wav-bytes", "filename": "clip.wav", "language": None},
    ]


def test_transcribe_speech_forwards_language_override(speech_recognition_api):
    make_client, transcribe_calls = speech_recognition_api

    with TestClient(make_client()) as client:
        response = client.post(
            "/speech-recognition/transcribe",
            data={"language": "fr"},
            files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        )

    assert response.status_code == 200
    assert response.json()["language"] == "fr"
    assert transcribe_calls[-1]["language"] == "fr"


def test_transcribe_speech_returns_404_when_no_stt_configured(speech_recognition_api):
    make_client, _ = speech_recognition_api

    with TestClient(make_client(configure_stt=False)) as client:
        response = client.post(
            "/speech-recognition/transcribe",
            files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        )

    assert response.status_code == 404


def test_transcribe_speech_returns_404_when_stt_has_no_connection(speech_recognition_api):
    make_client, _ = speech_recognition_api

    with TestClient(make_client(link_connection=False)) as client:
        response = client.post(
            "/speech-recognition/transcribe",
            files={"file": ("clip.wav", b"fake-wav-bytes", "audio/wav")},
        )

    assert response.status_code == 404
