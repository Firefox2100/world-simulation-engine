"""Orchestrates the image-link half of the SillyTavern import: finds candidate URLs
(`ImageLinkExtractor`), decides what's safe to even look at, and either downloads a URL outright
(whitelisted) or leaves it for the user to opt into (everything else). No LLM call anywhere in
this path - a peer of `CardPreprocessor`/`WorldAssembler`, not a `SillyTavernPipelineComponent`.

Runs independently of (and concurrently with) the LLM extraction pipeline - see
`router/sillytavern_import.py`'s `/extract` handler, which `asyncio.gather`s this against
`WorldReconstructor.reconstruct_from_card` rather than wiring it into that LangGraph, since neither
depends on the other's output and the user asked for both to proceed without waiting on each other.
"""

import base64
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import MediaType
from world_simulation_engine.model import ImportedImageMediaFile
from world_simulation_engine.model.silly_tavern import SillyTavernCardV3
from world_simulation_engine.service.media_download_service import MediaDownloadService
from world_simulation_engine.service.storage_service import StagedObject, StorageService

from .image_link_extractor import ImageLinkExtractor


class ImageCandidateRow(BaseModel):
    """A safe-enough-to-consider, but not auto-trusted, image URL - shown to the user with a
    checkbox so they can opt into fetching it (`POST .../images/fetch`)."""

    url: str
    source: str
    probably_image: bool | None = Field(
        description="True: a HEAD request confirmed an image. False is never stored here (those "
                    "are dropped before this row is created). None: HEAD failed/timed out.",
    )


class ImageScanSummary(BaseModel):
    """Always populated, even when every count is zero - the review UI shows this unconditionally
    (not just when there's something to act on) so "the scan found nothing" and "the scan found
    things but they all got filtered" are never indistinguishable to the user."""

    found: int = 0
    auto_downloaded: int = 0
    awaiting_review: int = 0
    dropped_unsafe: int = 0
    dropped_non_image: int = 0
    failed_downloads: int = 0


class ImageExtraction(BaseModel):
    media_rows: list[dict] = Field(
        default_factory=list,
        description="Temporarily staged, `sections['media']`-shaped rows with inline previews.",
    )
    candidates: list[ImageCandidateRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    summary: ImageScanSummary = Field(default_factory=ImageScanSummary)


def build_downloaded_media_row(url: str, staged: StagedObject, content: bytes) -> dict:
    media = ImportedImageMediaFile(
        id=str(uuid4()),
        type=MediaType.PNG,
        title=None,
        hash=staged.digest,
        filename=f"st_import_{uuid4().hex}",
        created_at=datetime.now(timezone.utc),
        source_url=url,
    )
    return {
        **media.model_dump(mode="json"),
        "temporary_id": staged.token,
        "preview_data_uri": f"data:image/png;base64,{base64.b64encode(content).decode('ascii')}",
    }


class ImageExtractor:
    def __init__(
            self, *, media_download_service: MediaDownloadService, storage: StorageService,
            whitelist: list[str],
    ):
        self._media_download_service = media_download_service
        self._storage = storage
        self._whitelist = whitelist

    def _is_whitelisted(self, url: str) -> bool:
        return any(url.startswith(base) for base in self._whitelist)

    async def _classify(self, card: SillyTavernCardV3) -> tuple[list, list[str], dict[str, str], int, list] | None:
        links = ImageLinkExtractor.extract(card)
        if not links.candidates:
            return None

        safe_urls: list[str] = []
        unsafe_count = 0
        seen_urls: set[str] = set()
        source_by_url: dict[str, str] = {}
        for candidate in links.candidates:
            if candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            source_by_url[candidate.url] = candidate.source
            if await self._media_download_service.is_safe_url(candidate.url):
                safe_urls.append(candidate.url)
            else:
                unsafe_count += 1

        review_pool = [url for url in safe_urls if not self._is_whitelisted(url)]
        probes = await self._media_download_service.probe_many(review_pool)
        return links.candidates, safe_urls, source_by_url, unsafe_count, probes

    async def scan(self, card: SillyTavernCardV3) -> ImageExtraction:
        """Discover and probe links for the pre-extraction review UI.  This deliberately does
        not download anything; downloads belong to :meth:`extract`, which runs beside the LLM."""
        classified = await self._classify(card)
        if classified is None:
            return ImageExtraction()
        links, safe_urls, source_by_url, unsafe_count, probes = classified
        candidates = [
            ImageCandidateRow(url=probe.url, source=source_by_url[probe.url], probably_image=probe.probably_image)
            for probe in probes if probe.probably_image is not False
        ]
        summary = ImageScanSummary(
            found=len(links), awaiting_review=len(candidates), dropped_unsafe=unsafe_count,
            dropped_non_image=len(probes) - len(candidates),
        )
        return ImageExtraction(candidates=candidates, summary=summary)

    async def extract(
            self, card: SillyTavernCardV3, *, selected_urls: list[str] | None = None,
    ) -> ImageExtraction:
        classified = await self._classify(card)
        if classified is None:
            return ImageExtraction()
        links, safe_urls, source_by_url, unsafe_count, probes = classified
        selected = set(selected_urls or [])
        whitelisted = [url for url in safe_urls if self._is_whitelisted(url)]
        review_pool = [url for url in safe_urls if not self._is_whitelisted(url)]
        # Only URLs rediscovered in this card and revalidated by the SSRF filter can be selected.
        chosen = [url for url in review_pool if url in selected]

        downloaded = await self._media_download_service.download_many(whitelisted + chosen)
        staged = await asyncio.gather(*(self._storage.stage_bytes(content) for _, content in downloaded))
        media_rows = [
            build_downloaded_media_row(url, temporary, content)
            for (url, content), temporary in zip(downloaded, staged, strict=True)
        ]
        candidates = [
            ImageCandidateRow(url=probe.url, source=source_by_url[probe.url], probably_image=probe.probably_image)
            for probe in probes
            if probe.probably_image is not False and probe.url not in selected
        ]
        dropped_non_image = sum(probe.probably_image is False for probe in probes)

        summary = ImageScanSummary(
            found=len(links),
            auto_downloaded=len(media_rows),
            awaiting_review=len(candidates),
            dropped_unsafe=unsafe_count,
            dropped_non_image=dropped_non_image,
            failed_downloads=len(whitelisted) + len(chosen) - len(downloaded),
        )
        notes = [
            f"Image links: {summary.found} found, {summary.auto_downloaded} downloaded to temporary "
            f"preview storage, {summary.awaiting_review} awaiting review, "
            f"{summary.dropped_unsafe} dropped as unsafe, {summary.dropped_non_image} dropped as "
            f"confirmed non-images, {summary.failed_downloads} selected/whitelisted download(s) failed."
        ]

        return ImageExtraction(media_rows=media_rows, candidates=candidates, notes=notes, summary=summary)
