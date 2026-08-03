import base64

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError

from world_simulation_engine.component.sillytavern_converter import AssembledWorld, DataExtractor, \
    WorldReconstructor
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage
from world_simulation_engine.model import World
from world_simulation_engine.model.silly_tavern import (
    SillyTavernCardV3, SillyTavernCardV3BookEntry, SillyTavernCardV3Data, SillyTavernCardV3LoreBook,
)
from world_simulation_engine.service import AuthorNotFoundError, WorldImportError, \
    WorldImportService
from .utils import db_dep, storage_dep

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
)


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


class SillyTavernExtractRequest(BaseModel):
    card: SillyTavernExtractCard
    language: SupportedLanguage = Field(
        description="Same meaning as every other stage's language parameter.",
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
        ),
    )


@sillytavern_import_router.post(
    "/worlds/import/sillytavern/parse", response_model=ParsedSillyTavernCard,
)
async def parse_sillytavern_card(file: UploadFile = File(...)):
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


@sillytavern_import_router.post("/worlds/import/sillytavern/extract", response_model=AssembledWorld)
async def extract_sillytavern_card(db: db_dep, request: SillyTavernExtractRequest):
    """Runs the full extraction pipeline (stages 1-3) on the user-edited card and returns the
    assembled result *without persisting it* - the review page shows this for further editing, and
    a separate `/commit` call actually writes it to the database once the user is done."""
    synthetic_card = _build_synthetic_card(request.card)
    try:
        return await WorldReconstructor(database=db).reconstruct_from_card(
            synthetic_card, language=request.language,
        )
    except ValueError as exc:
        # Most likely an unconfigured global chat model (see /status) - surfaced mid-run, not
        # something the client can fix by editing the card, so 409 rather than 400.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


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
        return await WorldImportService(database=db, storage=storage).import_assembled_sections(
            request.world, request.sections, request.author_id,
        )
    except AuthorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {exc} not found",
        ) from exc
    except WorldImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
