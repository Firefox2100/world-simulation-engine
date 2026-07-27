import os
from unittest.mock import AsyncMock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import ConnectionConfig, OllamaChatModelConfig, WhisperCppSttModelConfig
from world_simulation_engine.service.stt_service.stt_result import SttTranscriptionResult
from world_simulation_engine.service.stt_service.stt_service import SttService

import pytest


def make_service(**model_kwargs) -> SttService:
    return SttService(
        model_config=WhisperCppSttModelConfig(id="stt_1", **model_kwargs),
        connection_config=ConnectionConfig(
            id="connection_1",
            type=ConnectionType.WHISPERCPP,
            name="Local whisper.cpp",
            base_url="http://127.0.0.1:8080",
        ),
    )


async def test_transcribe_delegates_to_driver():
    service = make_service(language="en")
    expected = SttTranscriptionResult(text="hello there", language="en")
    service.driver.transcribe = AsyncMock(return_value=expected)

    result = await service.transcribe(b"fake-wav-bytes")

    assert result is expected
    service.driver.transcribe.assert_awaited_once_with(
        b"fake-wav-bytes", filename="audio.wav", content_type=None, language=None,
    )


async def test_transcribe_forwards_filename_content_type_and_language():
    service = make_service()
    service.driver.transcribe = AsyncMock(return_value=SttTranscriptionResult(text="x"))

    await service.transcribe(
        b"fake-wav-bytes", filename="clip.wav", content_type="audio/wav", language="fr",
    )

    service.driver.transcribe.assert_awaited_once_with(
        b"fake-wav-bytes", filename="clip.wav", content_type="audio/wav", language="fr",
    )


def test_driver_dispatches_whisper_cpp_config():
    service = make_service(language="en", translate=True)

    from world_simulation_engine.service.stt_service.whisper_cpp import SttWhisperCpp

    assert isinstance(service.driver, SttWhisperCpp)
    # pylint: disable=protected-access
    assert service.driver._language == "en"
    assert service.driver._translate is True


def test_driver_property_rejects_mismatched_config_and_connection():
    service = SttService(
        model_config=OllamaChatModelConfig(
            id="chat_1", name="Chat", model="llama3.1", temperature=0.5, context_window=4096,
        ),
        connection_config=ConnectionConfig(id="connection_1", type=ConnectionType.WHISPERCPP, name="whisper.cpp"),
    )

    with pytest.raises(ValueError, match="Model config class mismatch"):
        _ = service.driver


def test_driver_property_rejects_unsupported_provider():
    service = SttService(
        model_config=WhisperCppSttModelConfig(id="stt_1"),
        connection_config=ConnectionConfig(id="connection_1", type=ConnectionType.OLLAMA, name="Ollama"),
    )

    with pytest.raises(ValueError, match="Unsupported provider"):
        _ = service.driver
