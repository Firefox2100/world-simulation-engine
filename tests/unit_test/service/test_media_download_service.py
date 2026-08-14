import io
import os

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

import httpx
import pytest
from PIL import Image

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.service.media_download_service import MediaDownloadService
from world_simulation_engine.service.storage_service import StorageService

_PUBLIC_IP = "93.184.216.34"
_PRIVATE_IP = "127.0.0.1"


def _png_bytes(size=(2, 2)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _resolver(address: str):
    async def resolve(hostname, port):
        return [address]
    return resolve


def _failing_resolver():
    async def resolve(hostname, port):
        raise OSError("DNS resolution failed")
    return resolve


class FakeStorage:
    def __init__(self):
        self.saved: list[bytes] = []

    async def save_bytes(self, content: bytes, *, expected_digest=None):
        self.saved.append(content)
        from world_simulation_engine.service.storage_service import StoredObject
        import hashlib
        return StoredObject(digest=hashlib.sha256(content).hexdigest(), size=len(content))


# -- is_safe_url --------------------------------------------------------------------------------

async def test_is_safe_url_accepts_https_resolving_to_a_public_address():
    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP))
    assert await service.is_safe_url("https://images.example.com/a.png") is True


@pytest.mark.parametrize("url", [
    "ftp://images.example.com/a.png",
    "file:///etc/passwd",
    "javascript:alert(1)",
])
async def test_is_safe_url_rejects_non_http_schemes(url):
    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP))
    assert await service.is_safe_url(url) is False


async def test_is_safe_url_rejects_embedded_credentials():
    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP))
    assert await service.is_safe_url("https://user:pass@images.example.com/a.png") is False


@pytest.mark.parametrize("address", [
    "127.0.0.1",       # loopback
    "10.0.0.5",         # private
    "169.254.169.254",  # link-local / cloud metadata endpoint
    "::1",               # IPv6 loopback
])
async def test_is_safe_url_rejects_urls_resolving_to_unsafe_addresses(address):
    service = MediaDownloadService(resolver=_resolver(address))
    assert await service.is_safe_url("http://internal.example.com/a.png") is False


async def test_is_safe_url_rejects_when_dns_resolution_fails():
    service = MediaDownloadService(resolver=_failing_resolver())
    assert await service.is_safe_url("http://nowhere.example.com/a.png") is False


# -- probe ---------------------------------------------------------------------------------------

async def test_probe_confirms_an_image_on_a_successful_head():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/jpeg"})

    service = MediaDownloadService(transport=httpx.MockTransport(handler))
    result = await service.probe("https://images.example.com/a.jpg")
    assert result.probably_image is True


async def test_probe_confirms_a_non_image_on_a_successful_head():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"})

    service = MediaDownloadService(transport=httpx.MockTransport(handler))
    result = await service.probe("https://images.example.com/a.html")
    assert result.probably_image is False


async def test_probe_is_unknown_when_the_head_request_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    service = MediaDownloadService(transport=httpx.MockTransport(handler))
    result = await service.probe("https://images.example.com/a.jpg")
    assert result.probably_image is None


# -- fetch_and_store -------------------------------------------------------------------------

async def test_fetch_and_store_downloads_validates_and_normalises_a_real_image(tmp_path):
    png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=png)

    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    result = await service.fetch_and_store("https://images.example.com/a.png", storage=storage)

    assert result is not None
    assert result.url == "https://images.example.com/a.png"
    assert storage.saved == [result.content]
    # normalised through Pillow - still a valid PNG
    Image.open(io.BytesIO(result.content)).verify()


async def test_fetch_and_store_returns_none_when_the_url_is_unsafe():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must never make a network call for an unsafe URL")

    service = MediaDownloadService(resolver=_resolver(_PRIVATE_IP), transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    result = await service.fetch_and_store("http://internal.example.com/a.png", storage=storage)

    assert result is None
    assert storage.saved == []


async def test_fetch_and_store_rejects_a_non_image_content_type():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    result = await service.fetch_and_store("https://images.example.com/a.png", storage=storage)

    assert result is None
    assert storage.saved == []


async def test_download_raw_preserves_png_metadata_bytes():
    raw = b"\x89PNG\r\n\x1a\nmetadata-that-must-not-be-normalised"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=raw)

    service = MediaDownloadService(
        resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler),
    )

    assert await service.download_raw("https://cards.example.com/card.png") == raw


async def test_download_raw_rejects_private_urls_before_fetching():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must never fetch a private URL")

    service = MediaDownloadService(
        resolver=_resolver(_PRIVATE_IP), transport=httpx.MockTransport(handler),
    )

    assert await service.download_raw("http://internal.example.com/card.json") is None


async def test_fetch_and_store_rejects_a_body_over_the_content_length_cap():
    original_max = CONFIG.sillytavern_image_download_max_bytes
    CONFIG.sillytavern_image_download_max_bytes = 10
    try:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, headers={"content-type": "image/png", "content-length": "1000"}, content=_png_bytes(),
            )

        service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler))
        storage = FakeStorage()

        result = await service.fetch_and_store("https://images.example.com/a.png", storage=storage)

        assert result is None
        assert storage.saved == []
    finally:
        CONFIG.sillytavern_image_download_max_bytes = original_max


async def test_fetch_and_store_rejects_bytes_that_are_not_actually_an_image():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"not a real png")

    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    result = await service.fetch_and_store("https://images.example.com/a.png", storage=storage)

    assert result is None
    assert storage.saved == []


async def test_fetch_and_store_follows_a_redirect_to_a_safe_target():
    png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://images.example.com/redirect.png":
            return httpx.Response(302, headers={"location": "https://images.example.com/final.png"})
        return httpx.Response(200, headers={"content-type": "image/png"}, content=png)

    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    result = await service.fetch_and_store("https://images.example.com/redirect.png", storage=storage)

    assert result is not None
    assert result.url == "https://images.example.com/redirect.png"  # original url is preserved
    assert storage.saved == [result.content]


async def test_fetch_and_store_rejects_a_redirect_to_an_unsafe_target():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://internal.example.com/secret.png"})

    async def resolve(hostname, port):
        # the *original* host resolves safely; only the redirect target should get rejected
        return [_PRIVATE_IP] if hostname == "internal.example.com" else [_PUBLIC_IP]

    service = MediaDownloadService(resolver=resolve, transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    result = await service.fetch_and_store("https://images.example.com/redirect.png", storage=storage)

    assert result is None
    assert storage.saved == []


async def test_fetch_and_store_many_isolates_one_failure_from_the_rest():
    png = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if "bad" in str(request.url):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"nope")
        return httpx.Response(200, headers={"content-type": "image/png"}, content=png)

    service = MediaDownloadService(resolver=_resolver(_PUBLIC_IP), transport=httpx.MockTransport(handler))
    storage = FakeStorage()

    results = await service.fetch_and_store_many(
        ["https://images.example.com/good1.png", "https://images.example.com/bad.png",
         "https://images.example.com/good2.png"],
        storage=storage,
    )

    assert {r.url for r in results} == {
        "https://images.example.com/good1.png", "https://images.example.com/good2.png",
    }
