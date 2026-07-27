import os
from unittest.mock import AsyncMock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import AllTalkPiperModelConfig, AllTalkXttsModelConfig, ConnectionConfig, \
    OllamaChatModelConfig
from world_simulation_engine.service.tts_service.tts_result import TtsFileResult
from world_simulation_engine.service.tts_service.tts_service import TtsService

import pytest


def make_service(config_cls=AllTalkXttsModelConfig, **model_kwargs) -> TtsService:
    return TtsService(
        model_config=config_cls(id="tts_1", **model_kwargs),
        connection_config=ConnectionConfig(
            id="connection_1",
            type=ConnectionType.ALLTALK,
            name="Local AllTalk",
            base_url="http://127.0.0.1:7851",
        ),
    )


async def test_generate_file_delegates_to_driver():
    service = make_service(language="en", temperature=0.75)
    expected = TtsFileResult(audio=b"wav-bytes", source_url="http://127.0.0.1:7851/audio/x.wav")
    service.driver.generate_file = AsyncMock(return_value=expected)

    result = await service.generate_file("Hello there")

    assert result is expected
    service.driver.generate_file.assert_awaited_once_with(
        "Hello there", character_voice=None, rvc_character_voice=None, rvc_character_pitch=None,
    )


async def test_generate_file_forwards_voice_and_rvc_overrides():
    service = make_service()
    service.driver.generate_file = AsyncMock(return_value=TtsFileResult(audio=b"x"))

    await service.generate_file(
        "Hello there", voice="male_02.wav", rvc_voice="voices/male.pth", rvc_pitch=-2,
    )

    service.driver.generate_file.assert_awaited_once_with(
        "Hello there",
        character_voice="male_02.wav",
        rvc_character_voice="voices/male.pth",
        rvc_character_pitch=-2,
    )


async def test_generate_stream_delegates_to_driver():
    service = make_service()

    async def fake_stream(text, *, character_voice=None):
        assert text == "Hello there"
        assert character_voice is None
        yield b"chunk-1"
        yield b"chunk-2"

    service.driver.generate_stream = fake_stream

    chunks = [chunk async for chunk in service.generate_stream("Hello there")]

    assert chunks == [b"chunk-1", b"chunk-2"]


async def test_driver_dispatches_per_engine_config():
    xtts_service = make_service(config_cls=AllTalkXttsModelConfig, language="en")
    piper_service = make_service(config_cls=AllTalkPiperModelConfig, speed=1.1)

    from world_simulation_engine.service.tts_service.alltalk_v2 import TtsAllTalkV2

    assert isinstance(xtts_service.driver, TtsAllTalkV2)
    assert isinstance(piper_service.driver, TtsAllTalkV2)
    # pylint: disable=protected-access
    assert xtts_service.driver._temperature is None
    assert xtts_service.driver._language == "en"
    assert piper_service.driver._speed == 1.1


def test_driver_property_rejects_mismatched_config_and_connection():
    service = TtsService(
        model_config=OllamaChatModelConfig(
            id="chat_1", name="Chat", model="llama3.1", temperature=0.5, context_window=4096,
        ),
        connection_config=ConnectionConfig(id="connection_1", type=ConnectionType.ALLTALK, name="Local AllTalk"),
    )

    with pytest.raises(ValueError, match="Model config class mismatch"):
        _ = service.driver


def test_driver_property_rejects_unsupported_provider():
    service = TtsService(
        model_config=AllTalkXttsModelConfig(id="tts_1"),
        connection_config=ConnectionConfig(id="connection_1", type=ConnectionType.OLLAMA, name="Ollama"),
    )

    with pytest.raises(ValueError, match="Unsupported provider"):
        _ = service.driver
