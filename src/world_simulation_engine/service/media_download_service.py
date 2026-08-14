"""Generic, SSRF-hardened outbound media fetcher.

Not tied to SillyTavern or any other caller: given an arbitrary, untrusted URL, this decides
whether it's safe to touch at all (`is_safe_url`), whether it's worth downloading without asking
a human first (`probe`), and - if so - fetches it carefully (`fetch_and_store`): bounded size,
bounded time, every redirect hop re-validated against the same safety check as the original URL,
and the body run through `StorageService.FormatNormaliser.normalise_image` (Pillow parses the
actual bytes, strips anything but pixel data, and re-encodes as PNG) before it ever touches disk.
Domain-specific policy - which URLs to even consider, what a "trusted" URL looks like - belongs to
the caller (see `component/sillytavern_converter/image_extractor.py`), not here.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.logging import log_event

from .storage_service import FormatNormaliser, StorageService, StoredObject

Resolver = Callable[[str, int], Awaitable[list[str]]]

_ALLOWED_SCHEMES = {"http", "https"}

# Any of these being true on a resolved address means "don't let this system reach it" - covers
# loopback (127.0.0.1/::1), RFC1918/ULA private ranges, link-local (including the
# 169.254.169.254 cloud metadata endpoint), multicast, and other IANA-reserved ranges.
_UNSAFE_ADDRESS_ATTRS = (
    "is_private", "is_loopback", "is_link_local", "is_multicast", "is_reserved", "is_unspecified",
)


@dataclass(frozen=True, slots=True)
class ImageProbeResult:
    url: str
    # True: HEAD confirmed an image. False: HEAD confirmed a non-image (caller should drop this
    # candidate entirely). None: HEAD failed/timed out/errored - unknown, not confirmed either way.
    probably_image: bool | None


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    url: str
    stored: StoredObject
    content: bytes  # the normalised PNG bytes, so callers can build an inline preview without a
    # round-trip back through StorageService


def _is_unsafe_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True  # can't even parse it as an IP - don't trust it
    return any(getattr(parsed, attr) for attr in _UNSAFE_ADDRESS_ATTRS)


async def _default_resolve(hostname: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.run_in_executor(
        None, lambda: socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM),
    )
    return [info[4][0] for info in infos]


class MediaDownloadService:
    def __init__(
            self, *, resolver: Resolver = _default_resolve,
            transport: httpx.BaseTransport | None = None,
    ):
        self._resolver = resolver
        # Injectable so tests can swap in an `httpx.MockTransport` and never touch the network -
        # `None` means httpx's own default (real) transport.
        self._transport = transport
        self._download_semaphore = asyncio.Semaphore(CONFIG.sillytavern_image_download_max_concurrency)
        self._probe_semaphore = asyncio.Semaphore(CONFIG.sillytavern_image_download_max_concurrency)

    async def is_safe_url(self, url: str) -> bool:
        try:
            parts = urlsplit(url)
        except ValueError:
            return False

        if parts.scheme not in _ALLOWED_SCHEMES:
            return False
        if parts.username or parts.password:
            return False
        hostname = parts.hostname
        if not hostname:
            return False

        try:
            port = parts.port or (443 if parts.scheme == "https" else 80)
        except ValueError:
            return False

        try:
            addresses = await self._resolver(hostname, port)
        except (OSError, socket.gaierror):
            return False
        if not addresses:
            return False

        return not any(_is_unsafe_address(address) for address in addresses)

    async def probe(self, url: str) -> ImageProbeResult:
        async with self._probe_semaphore:
            try:
                async with httpx.AsyncClient(follow_redirects=False, transport=self._transport) as client:
                    response = await client.head(
                        url, timeout=CONFIG.sillytavern_image_download_head_timeout,
                    )
            except httpx.HTTPError:
                return ImageProbeResult(url=url, probably_image=None)

        if response.status_code >= 300:
            return ImageProbeResult(url=url, probably_image=None)

        content_type = response.headers.get("content-type", "")
        return ImageProbeResult(url=url, probably_image=content_type.startswith("image/"))

    async def probe_many(self, urls: list[str]) -> list[ImageProbeResult]:
        return list(await asyncio.gather(*(self.probe(url) for url in urls)))

    async def _fetch_hop(self, url: str) -> tuple[str, bytes | str | None]:
        """One HTTP hop, redirects never auto-followed. Returns ("ok", body),
        ("redirect", absolute_location_url), or ("reject", None)."""
        timeout = httpx.Timeout(
            connect=CONFIG.sillytavern_image_download_connect_timeout,
            read=CONFIG.sillytavern_image_download_read_timeout,
            write=CONFIG.sillytavern_image_download_read_timeout,
            pool=CONFIG.sillytavern_image_download_connect_timeout,
        )
        max_bytes = CONFIG.sillytavern_image_download_max_bytes

        async with httpx.AsyncClient(
                follow_redirects=False, timeout=timeout, transport=self._transport,
        ) as client:
            async with client.stream("GET", url) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        return "reject", None
                    return "redirect", str(response.url.join(location))
                if response.status_code >= 300:
                    return "reject", None

                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    return "reject", None

                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        if int(content_length) > max_bytes:
                            return "reject", None
                    except ValueError:
                        pass

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        return "reject", None
                    chunks.append(chunk)
                return "ok", b"".join(chunks)

    async def _fetch_raw_hop(self, url: str) -> tuple[str, bytes | str | None]:
        """Fetch one bounded HTTP hop without transforming the response body.

        SillyTavern PNG cards store their JSON in PNG text chunks, so the normal image download
        path cannot be used for them: its security normalisation intentionally strips metadata.
        """
        timeout = httpx.Timeout(
            connect=CONFIG.sillytavern_image_download_connect_timeout,
            read=CONFIG.sillytavern_image_download_read_timeout,
            write=CONFIG.sillytavern_image_download_read_timeout,
            pool=CONFIG.sillytavern_image_download_connect_timeout,
        )
        max_bytes = CONFIG.sillytavern_image_download_max_bytes

        async with httpx.AsyncClient(
                follow_redirects=False, timeout=timeout, transport=self._transport,
        ) as client:
            async with client.stream("GET", url) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        return "reject", None
                    return "redirect", str(response.url.join(location))
                if response.status_code >= 300:
                    return "reject", None

                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        if int(content_length) > max_bytes:
                            return "reject", None
                    except ValueError:
                        pass

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        return "reject", None
                    chunks.append(chunk)
                return "ok", b"".join(chunks)

    async def download_raw(self, url: str) -> bytes | None:
        """Download untrusted bytes with the same SSRF, redirect, size, and timeout guards."""
        async with self._download_semaphore:
            current_url = url
            for _ in range(CONFIG.sillytavern_image_download_max_redirects + 1):
                if not await self.is_safe_url(current_url):
                    return None
                try:
                    outcome, payload = await self._fetch_raw_hop(current_url)
                except httpx.HTTPError:
                    return None
                if outcome == "redirect":
                    current_url = payload
                    continue
                return payload if outcome == "ok" else None
        return None

    async def download(self, url: str) -> bytes | None:
        """Download and normalize an image, but do not publish it to permanent storage."""
        async with self._download_semaphore:
            current_url = url
            for _ in range(CONFIG.sillytavern_image_download_max_redirects + 1):
                if not await self.is_safe_url(current_url):
                    return None

                try:
                    outcome, payload = await self._fetch_hop(current_url)
                except httpx.HTTPError:
                    return None

                if outcome == "redirect":
                    current_url = payload
                    continue
                if outcome != "ok":
                    return None

                try:
                    png_bytes = FormatNormaliser.normalise_image(payload)
                except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
                    return None

                return png_bytes

        return None  # exceeded max redirect hops without resolving

    async def download_many(self, urls: list[str]) -> list[tuple[str, bytes]]:
        async def _safe_download(url: str) -> tuple[str, bytes] | None:
            try:
                content = await self.download(url)
                return (url, content) if content is not None else None
            except Exception as exc:  # noqa: BLE001 - one bad URL must never abort the batch
                log_event(
                    "image_download_failed", url=url, error_type=type(exc).__name__, error=str(exc),
                )
                return None

        results = await asyncio.gather(*(_safe_download(url) for url in urls))
        return [result for result in results if result is not None]

    async def fetch_and_store(self, url: str, *, storage: StorageService) -> DownloadedImage | None:
        content = await self.download(url)
        if content is None:
            return None
        stored = await storage.save_bytes(content)
        return DownloadedImage(url=url, stored=stored, content=content)

    async def fetch_and_store_many(
            self, urls: list[str], *, storage: StorageService,
    ) -> list[DownloadedImage]:
        async def _safe_fetch(url: str) -> DownloadedImage | None:
            try:
                return await self.fetch_and_store(url, storage=storage)
            except Exception as exc:  # noqa: BLE001 - one bad URL must never abort the batch
                log_event(
                    "image_download_failed", url=url, error_type=type(exc).__name__, error=str(exc),
                )
                return None

        results = await asyncio.gather(*(_safe_fetch(url) for url in urls))
        return [result for result in results if result is not None]
