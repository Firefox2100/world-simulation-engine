import asyncio
import base64
import json
import time
from contextlib import suppress
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from world_simulation_engine.component.sillytavern_converter import AssembledWorld, ConversionReport, \
    DataExtractor, ImageCandidateRow, ImageExtraction, ImageExtractor, ImageScanSummary, WorldReconstructor, \
    build_downloaded_media_row
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage
from world_simulation_engine.misc.logging import log_event
from world_simulation_engine.model import World
from world_simulation_engine.model.silly_tavern import (
    SillyTavernCardV3, SillyTavernCardV3Asset, SillyTavernCardV3BookEntry, SillyTavernCardV3Data,
    SillyTavernCardV3LoreBook,
)
from world_simulation_engine.service import AuthorNotFoundError, WorldImportError, \
    WorldImportService
from .utils import db_dep, media_download_dep, storage_dep

sillytavern_import_router = APIRouter(
    tags=["SillyTavern Import"],
)

# Every ComponentType this pipeline's stages resolve a chat model for (§6/§6.1 of
# SILLYTAVERN_IMPORT_PLAN.md) - "correctly configured" for the review UI's start button means all
# of these, since a single unconfigured stage fails the whole run partway through.
_REQUIRED_COMPONENTS = (
    ComponentType.ST_LOREBOOK_CLASSIFIER,
    ComponentType.ST_CHARACTER_EXTRACTOR,
    ComponentType.ST_LOCATION_EXTRACTOR,
    ComponentType.ST_WORLD_LORE_EXTRACTOR,
    ComponentType.ST_NARRATIVE_EXTRACTOR,
    ComponentType.ST_INTENT_EXTRACTOR,
    ComponentType.ST_VARIABLE_SCHEMA_EXTRACTOR,
    ComponentType.ST_ITEM_EXTRACTOR,
    ComponentType.ST_EQUIPMENT_EXTRACTOR,
)
_SSE_KEEPALIVE_SECONDS = 45


class ParsedLorebookEntry(BaseModel):
    id: int | None = None
    name: str | None = None
    comment: str | None = None
    keys: list[str] = Field(default_factory=list)
    secondary_keys: list[str] = Field(default_factory=list)
    content: str
    enabled: bool
    insertion_order: int
    priority: int | None = None


class ParsedSillyTavernCard(BaseModel):
    """Raw card fields for the import review UI - deliberately not run through
    `CardPreprocessor`/any extraction stage, since this is what the user reviews and edits before
    the real pipeline (`WorldReconstructor`) ever runs on it."""

    name: str
    description: str
    personality: str
    scenario: str
    first_mes: str
    alternate_greetings: list[str] = Field(default_factory=list)
    mes_example: str = ""
    creator_notes: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    tags: list[str] = Field(default_factory=list)
    lorebook_entries: list[ParsedLorebookEntry] = Field(default_factory=list)
    cover_image_data_uri: str | None = None
    assets: list[SillyTavernCardV3Asset] = Field(
        default_factory=list,
        description="Round-tripped verbatim, not user-editable - carried through to /extract so "
                    "the image-link scan can see V3 asset URIs.",
    )
    extensions: dict = Field(
        default_factory=dict,
        description="Round-tripped verbatim, not user-editable - carried through to /extract so "
                    "the image-link scan can see script/extension content.",
    )
    image_candidates: list[ImageCandidateRow] = Field(default_factory=list)
    image_scan: ImageScanSummary = Field(default_factory=ImageScanSummary)


class SillyTavernImportStatus(BaseModel):
    configured: bool = Field(
        description="True when every extraction stage has a global chat model configured - the "
                    "review page's start button is only enabled once this is true.",
    )
    missing_components: list[ComponentType] = Field(default_factory=list)


class SillyTavernExtractLorebookEntry(BaseModel):
    """One world book entry the user chose to keep enabled - already filtered client-side, so
    every entry present here is meant to be processed."""

    name: str | None = None
    keys: list[str] = Field(default_factory=list)
    content: str


class SillyTavernExtractCard(BaseModel):
    """The user-edited card fields submitted for extraction - same shape as `ParsedSillyTavernCard`
    minus what editing already resolved: exactly one opening (`first_message`, whichever the user
    selected from `first_mes`/`alternate_greetings`), and only the lorebook entries the user left
    enabled."""

    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_message: str = ""
    mes_example: str = ""
    creator_notes: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    tags: list[str] = Field(default_factory=list)
    lorebook_entries: list[SillyTavernExtractLorebookEntry] = Field(default_factory=list)
    assets: list[SillyTavernCardV3Asset] = Field(
        default_factory=list,
        description="Round-tripped verbatim from /parse - see ParsedSillyTavernCard.assets.",
    )
    extensions: dict = Field(
        default_factory=dict,
        description="Round-tripped verbatim from /parse - see ParsedSillyTavernCard.extensions.",
    )


class SillyTavernExtractRequest(BaseModel):
    card: SillyTavernExtractCard
    selected_image_urls: list[str] = Field(default_factory=list)
    language: SupportedLanguage = Field(
        description="Same meaning as every other stage's language parameter.",
    )


class SillyTavernExtractResponse(BaseModel):
    """Superset of `AssembledWorld` - the LLM extraction pipeline's result plus the image-link
    pipeline's result, merged once both finish (they run concurrently, see `extract_sillytavern_card`).
    `sections["media"]` already contains the auto-downloaded (whitelisted) images, ready to import
    as-is; `image_candidates` are the ones that need the user to opt in via `/images/fetch`."""

    world: dict
    sections: dict[str, list]
    report: ConversionReport
    image_candidates: list[ImageCandidateRow] = Field(default_factory=list)
    image_scan: ImageScanSummary = Field(
        default_factory=ImageScanSummary,
        description="Always present, even when every count is zero, so the review UI can show "
                    "what the image-link scan actually found rather than going silent.",
    )


class SillyTavernImageFetchRequest(BaseModel):
    urls: list[str] = Field(description="Candidate URLs the user checked for download.")


class SillyTavernImageFetchResponse(BaseModel):
    media_rows: list[dict] = Field(
        description="`sections['media']`-shaped rows, ready to merge into the reviewed world.",
    )


class SillyTavernCommitRequest(BaseModel):
    world: dict = Field(description="`AssembledWorld.world`, possibly edited by the user.")
    sections: dict[str, list] = Field(
        description="`AssembledWorld.sections`, possibly edited by the user.",
    )
    author_id: str


def _build_synthetic_card(card: SillyTavernExtractCard) -> SillyTavernCardV3:
    """Rebuilds a `SillyTavernCardV3` from the edited review fields so `CardPreprocessor` (macro
    normalization, `mes_example` splitting) can run unchanged - the same code path a raw upload
    goes through, just fed synthetic data instead of a real parsed file. `use_regex`/`constant`
    aren't tracked through the review UI (nothing downstream reads them), so both default False."""
    entries = [
        SillyTavernCardV3BookEntry(
            keys=entry.keys,
            content=entry.content,
            enabled=True,
            insertion_order=index,
            name=entry.name,
            use_regex=False,
            constant=False,
        )
        for index, entry in enumerate(card.lorebook_entries)
    ]
    return SillyTavernCardV3(
        spec="chara_card_v3",
        spec_version="3.0",
        data=SillyTavernCardV3Data(
            name=card.name,
            description=card.description,
            personality=card.personality,
            scenario=card.scenario,
            first_mes=card.first_message,
            mes_example=card.mes_example,
            creator_notes=card.creator_notes,
            system_prompt=card.system_prompt,
            post_history_instructions=card.post_history_instructions,
            tags=card.tags,
            character_book=SillyTavernCardV3LoreBook(entries=entries),
            assets=card.assets or None,
            extensions=card.extensions,
        ),
    )


@sillytavern_import_router.post(
    "/worlds/import/sillytavern/parse", response_model=ParsedSillyTavernCard,
)
async def parse_sillytavern_card(
        request: Request, file: UploadFile = File(...),
):
    """Parses a card and returns its raw fields for the import review UI, without running any
    extraction stage or touching the database - the user reviews/edits this first (left side),
    then `/extract` (right side) feeds the edited result into the real pipeline."""
    content = await file.read()
    await file.close()

    try:
        extracted = DataExtractor().extract(content)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    data = extracted.card.data
    book_entries = data.character_book.entries if data.character_book else []
    # The production app supplies these shared services. Keeping parse usable on a bare FastAPI
    # router is useful for offline/card-format consumers; in that case the scan is simply empty.
    if all(hasattr(request.app.state, name) for name in ("database", "storage", "media_download_service")):
        image_scan = await ImageExtractor(
            media_download_service=request.app.state.media_download_service,
            storage=request.app.state.storage,
            whitelist=await request.app.state.database.config.get_image_url_whitelist(),
        ).scan(extracted.card)
    else:
        image_scan = ImageExtraction()

    return ParsedSillyTavernCard(
        name=data.name,
        description=data.description,
        personality=data.personality,
        scenario=data.scenario,
        first_mes=data.first_mes,
        alternate_greetings=data.alternate_greetings,
        mes_example=data.mes_example,
        creator_notes=data.creator_notes,
        system_prompt=data.system_prompt,
        post_history_instructions=data.post_history_instructions,
        tags=data.tags,
        lorebook_entries=[
            ParsedLorebookEntry(
                id=entry.id,
                name=entry.name,
                comment=entry.comment,
                keys=entry.keys,
                secondary_keys=entry.secondary_keys or [],
                content=entry.content,
                enabled=entry.enabled,
                insertion_order=entry.insertion_order,
                priority=entry.priority,
            )
            for entry in book_entries
        ],
        cover_image_data_uri=(
            f"data:image/png;base64,{base64.b64encode(extracted.image).decode('ascii')}"
        ),
        assets=data.assets or [],
        extensions=data.extensions or {},
        image_candidates=image_scan.candidates,
        image_scan=image_scan.summary,
    )


@sillytavern_import_router.get(
    "/worlds/import/sillytavern/status", response_model=SillyTavernImportStatus,
)
async def get_sillytavern_import_status(db: db_dep):
    """Whether the review page's language selector/start button should be enabled."""
    missing = [
        component for component in _REQUIRED_COMPONENTS
        if await db.config.get_global_chat(component) is None
    ]
    return SillyTavernImportStatus(configured=not missing, missing_components=missing)


@sillytavern_import_router.post(
    "/worlds/import/sillytavern/extract",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def extract_sillytavern_card(
        db: db_dep, storage: storage_dep, media_download_service: media_download_dep,
        request: SillyTavernExtractRequest,
):
    """Runs the full extraction pipeline (stages 1-3) on the user-edited card and returns the
    assembled result *without persisting it* - the review page shows this for further editing, and
    a separate `/commit` call actually writes it to the database once the user is done.

    Concurrently (`asyncio.gather`, neither waits on the other) also scans the card for image
    links, downloads the ones from a whitelisted source outright, and returns the rest as
    `image_candidates` for the user to opt into via `/images/fetch` - see `ImageExtractor`."""
    request_id = uuid4().hex
    started = time.monotonic()
    log_event(
        "sillytavern_extraction_started", request_id=request_id,
        selected_image_count=len(request.selected_image_urls),
    )
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue(maxsize=8)

    async def emit(event: str, data: object) -> None:
        await queue.put((event, data))

    async def run_extraction() -> None:
        reconstruction_task = None
        image_task = None
        try:
            synthetic_card = _build_synthetic_card(request.card)
            whitelist = await db.config.get_image_url_whitelist()
            image_extractor = ImageExtractor(
                media_download_service=media_download_service, storage=storage, whitelist=whitelist,
            )
            reconstruction_task = asyncio.create_task(
                WorldReconstructor(database=db).reconstruct_from_card(
                    synthetic_card, language=request.language,
                ),
            )
            async def extract_images():
                result = await image_extractor.extract(
                    synthetic_card, selected_urls=request.selected_image_urls,
                )
                await emit("section_start", {"name": "media", "total": len(result.media_rows)})
                for row in result.media_rows:
                    await emit("section_item", {"name": "media", "row": row})
                return result

            image_task = asyncio.create_task(extract_images())
            assembled, image_result = await asyncio.gather(reconstruction_task, image_task)

            for note in image_result.notes:
                assembled.report.note(note)
            world = {
                **assembled.world,
                "media_ids": [row["id"] for row in image_result.media_rows],
            }
            await emit("world", world)
            for section_name, rows in assembled.sections.items():
                if section_name == "media":
                    continue  # emitted by the concurrent image branch above
                await emit("section_start", {"name": section_name, "total": len(rows)})
                for row in rows:
                    await emit("section_item", {"name": section_name, "row": row})
            await emit("report", assembled.report.model_dump(mode="json"))
            for candidate in image_result.candidates:
                await emit("image_candidate", candidate.model_dump(mode="json"))
            await emit("image_scan", image_result.summary.model_dump(mode="json"))
            await emit("complete", {"request_id": request_id})
            log_event(
                "sillytavern_extraction_completed", request_id=request_id,
                duration_seconds=round(time.monotonic() - started, 3),
                preview_count=len(image_result.media_rows),
            )
        except ValueError as exc:
            log_event(
                "sillytavern_extraction_rejected", request_id=request_id,
                duration_seconds=round(time.monotonic() - started, 3),
                error_type=type(exc).__name__, error=str(exc),
            )
            await emit("error", {"detail": str(exc), "request_id": request_id})
        except Exception as exc:
            log_event(
                "sillytavern_extraction_failed", request_id=request_id,
                duration_seconds=round(time.monotonic() - started, 3),
                error_type=type(exc).__name__, error=str(exc),
            )
            await emit("error", {
                "detail": f"Extraction failed on the server (reference {request_id}).",
                "request_id": request_id,
            })
        finally:
            pending = [task for task in (reconstruction_task, image_task) if task is not None]
            for task in pending:
                if not task.done():
                    task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            await emit("stream_end", None)

    def encode_event(event: str, data: object) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
        return f"event: {event}\ndata: {payload}\n\n"

    async def event_stream():
        worker = asyncio.create_task(run_extraction())
        try:
            yield encode_event("started", {"request_id": request_id})
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                except TimeoutError:
                    # SSE comments are ignored by clients but count as traffic through proxies.
                    yield ": keep-alive\n\n"
                    continue
                if event == "stream_end":
                    break
                yield encode_event(event, data)
        finally:
            if not worker.done():
                worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@sillytavern_import_router.post(
    "/worlds/import/sillytavern/images/fetch", response_model=SillyTavernImageFetchResponse,
)
async def fetch_sillytavern_images(
        storage: storage_dep, media_download_service: media_download_dep,
        request: SillyTavernImageFetchRequest,
):
    """Downloads the candidate image URLs the user checked on the review page. Re-runs the SSRF
    filter server-side regardless of what the client sent (`MediaDownloadService.fetch_and_store`
    always does) - client-side selection is never trusted as a safety boundary."""
    downloaded = await media_download_service.download_many(request.urls)
    staged = await asyncio.gather(*(storage.stage_bytes(content) for _, content in downloaded))
    return SillyTavernImageFetchResponse(
        media_rows=[
            build_downloaded_media_row(url, temporary, content)
            for (url, content), temporary in zip(downloaded, staged, strict=True)
        ],
    )


@sillytavern_import_router.post("/worlds/import/sillytavern/commit", response_model=World)
async def commit_sillytavern_world(
        db: db_dep, storage: storage_dep, request: SillyTavernCommitRequest,
):
    """Persists a (possibly user-edited) `AssembledWorld` - the one place this pipeline actually
    writes to the database. The cover image isn't handled here: the original card's PNG is already
    available to the frontend from `/parse`, so it's uploaded via the existing generic
    `POST /worlds/{id}/cover-image` flow once this call returns the new world's id, rather than
    duplicating that upload/media-creation logic in this endpoint too."""
    try:
        sections = {**request.sections}
        media_rows = []
        for row in sections.get("media", []):
            cleaned = dict(row)
            temporary_id = cleaned.pop("temporary_id", None)
            cleaned.pop("preview_data_uri", None)
            if temporary_id:
                await storage.promote_staged(temporary_id, expected_digest=cleaned["hash"])
            media_rows.append(cleaned)
        sections["media"] = media_rows
        return await WorldImportService(database=db, storage=storage).import_assembled_sections(
            request.world, sections, request.author_id,
        )
    except AuthorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {exc} not found",
        ) from exc
    except (WorldImportError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
