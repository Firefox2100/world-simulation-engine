import os

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

import httpx
import pytest

from world_simulation_engine.service.stt_service.whisper_cpp import SttWhisperCpp


def make_driver(handler, **kwargs) -> SttWhisperCpp:
    driver = SttWhisperCpp(base_url="http://whisper.test", **kwargs)
    driver._client = httpx.AsyncClient(base_url="http://whisper.test", transport=httpx.MockTransport(handler))
    return driver


async def test_transcribe_builds_form_payload_and_returns_text():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"text": "  Hello there.  "})

    driver = make_driver(
        handler,
        language="en",
        translate=True,
        temperature=0.0,
        temperature_inc=0.2,
        initial_prompt="World Simulation Engine",
        carry_initial_prompt=True,
    )

    result = await driver.transcribe(b"fake-wav-bytes", filename="clip.wav", content_type="audio/wav")

    assert result.text == "Hello there."
    assert result.language == "en"

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/inference"

    body = request.content.decode()
    assert 'name="file"; filename="clip.wav"' in body
    assert 'name="language"' in body and "\r\n\r\nen\r\n" in body
    assert 'name="translate"' in body and "\r\n\r\ntrue\r\n" in body
    assert 'name="temperature"' in body and "\r\n\r\n0.0\r\n" in body
    assert 'name="temperature_inc"' in body and "\r\n\r\n0.2\r\n" in body
    assert 'name="prompt"' in body and "\r\n\r\nWorld Simulation Engine\r\n" in body
    assert 'name="carry_initial_prompt"' in body and "\r\n\r\ntrue\r\n" in body
    assert 'name="response_format"' in body and "\r\n\r\njson\r\n" in body


async def test_transcribe_language_override_takes_precedence_over_config():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"text": "bonjour"})

    driver = make_driver(handler, language="en")

    result = await driver.transcribe(b"fake-wav-bytes", language="fr")

    assert result.text == "bonjour"
    assert result.language == "fr"
    assert 'name="language"' in captured["body"] and "\r\n\r\nfr\r\n" in captured["body"]


async def test_transcribe_omits_unset_optional_fields():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"text": "ok"})

    driver = make_driver(handler)

    await driver.transcribe(b"fake-wav-bytes")

    assert 'name="language"' not in captured["body"]
    assert 'name="translate"' not in captured["body"]
    assert 'name="prompt"' not in captured["body"]


async def test_transcribe_raises_when_response_has_no_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    driver = make_driver(handler)

    with pytest.raises(RuntimeError, match="did not include transcribed text"):
        await driver.transcribe(b"fake-wav-bytes")


async def test_transcribe_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    driver = make_driver(handler)

    with pytest.raises(httpx.HTTPStatusError):
        await driver.transcribe(b"fake-wav-bytes")
