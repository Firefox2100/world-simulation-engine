import os

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

import httpx
import pytest

from world_simulation_engine.service.tts_service.alltalk_v2 import TtsAllTalkV2


def make_driver(handler, **kwargs) -> TtsAllTalkV2:
    driver = TtsAllTalkV2(base_url="http://alltalk.test", **kwargs)
    driver._client = httpx.AsyncClient(base_url="http://alltalk.test", transport=httpx.MockTransport(handler))
    return driver


async def test_generate_file_builds_form_payload_and_downloads_audio():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/tts-generate":
            return httpx.Response(
                200,
                json={
                    "status": "generate-success",
                    "output_file_path": "/outputs/clip_123.wav",
                    "output_file_url": "/audio/clip_123.wav",
                    "output_cache_url": "/audiocache/clip_123.wav",
                },
            )
        if request.url.path == "/audio/clip_123.wav":
            return httpx.Response(200, content=b"RIFF-fake-wav-bytes", headers={"content-type": "audio/wav"})
        return httpx.Response(404)

    driver = make_driver(
        handler,
        language="en",
        narrator_enabled=False,
        speed=1.0,
        temperature=0.75,
        repetition_penalty=10.0,
    )

    result = await driver.generate_file(
        "Hello there.",
        character_voice="female_01.wav",
        output_file_name="clip",
        rvc_character_voice="voices/female.pth",
        rvc_character_pitch=2,
    )

    assert result.audio == b"RIFF-fake-wav-bytes"
    assert result.content_type == "audio/wav"
    assert result.source_url == "http://alltalk.test/audio/clip_123.wav"
    assert result.cache_url == "http://alltalk.test/audiocache/clip_123.wav"

    generate_request = next(r for r in requests if r.url.path == "/api/tts-generate")
    assert generate_request.method == "POST"
    form = dict(httpx.QueryParams(generate_request.content.decode()))
    assert form["text_input"] == "Hello there."
    assert form["character_voice_gen"] == "female_01.wav"
    assert form["language"] == "en"
    assert form["output_file_name"] == "clip"
    assert form["rvccharacter_voice_gen"] == "voices/female.pth"
    assert form["rvccharacter_pitch"] == "2"
    assert form["narrator_enabled"] == "false"
    assert form["speed"] == "1.0"
    assert form["temperature"] == "0.75"
    assert form["repetition_penalty"] == "10.0"


async def test_generate_file_without_character_voice_omits_it_from_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tts-generate":
            captured["form"] = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(
                200,
                json={
                    "status": "generate-success",
                    "output_file_path": "/outputs/clip.wav",
                    "output_file_url": "/audio/clip.wav",
                    "output_cache_url": None,
                },
            )
        return httpx.Response(200, content=b"bytes")

    driver = make_driver(handler, language="en")

    result = await driver.generate_file("Hi")

    assert "character_voice_gen" not in captured["form"]
    assert captured["form"]["language"] == "en"
    assert result.cache_url is None


async def test_generate_file_overrides_configured_language_per_call():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tts-generate":
            captured["form"] = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(
                200,
                json={
                    "status": "generate-success",
                    "output_file_path": "/outputs/clip.wav",
                    "output_file_url": "/audio/clip.wav",
                    "output_cache_url": None,
                },
            )
        return httpx.Response(200, content=b"bytes")

    driver = make_driver(handler, language="en")

    await driver.generate_file("Hi", character_voice="male_02.wav", language="fr")

    assert captured["form"]["character_voice_gen"] == "male_02.wav"
    assert captured["form"]["language"] == "fr"


async def test_generate_file_raises_on_generation_failure_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "generate-failure", "detail": "engine not loaded"})

    driver = make_driver(handler)

    with pytest.raises(RuntimeError, match="generation failed"):
        await driver.generate_file("Hello", character_voice="female_01.wav")


async def test_generate_file_raises_when_output_url_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "generate-success"})

    driver = make_driver(handler)

    with pytest.raises(RuntimeError, match="output_file_url"):
        await driver.generate_file("Hello", character_voice="female_01.wav")


async def test_generate_stream_uses_get_with_query_params():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"streamed-audio-bytes", headers={"content-type": "audio/wav"})

    driver = make_driver(handler, language="en")

    chunks = [
        chunk async for chunk in driver.generate_stream(
            "Hi there", character_voice="female_01.wav", output_file_name="stream_clip",
        )
    ]

    assert b"".join(chunks) == b"streamed-audio-bytes"
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.path == "/api/tts-generate-streaming"
    params = dict(httpx.QueryParams(request.url.query.decode()))
    assert params == {
        "text": "Hi there",
        "voice": "female_01.wav",
        "language": "en",
        "output_file": "stream_clip",
    }


async def test_generate_stream_requires_character_voice_and_language():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"unused")

    driver_without_language = make_driver(handler)
    with pytest.raises(ValueError, match="character voice"):
        async for _ in driver_without_language.generate_stream("Hi"):
            pass

    driver_with_language = make_driver(handler, language="en")
    with pytest.raises(ValueError, match="character voice"):
        async for _ in driver_with_language.generate_stream("Hi"):
            pass

    with pytest.raises(ValueError, match="language"):
        async for _ in driver_without_language.generate_stream("Hi", character_voice="female_01.wav"):
            pass
