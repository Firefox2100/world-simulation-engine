"""Stage 2 (item branch, conditional) of the SillyTavern import pipeline: turn lorebook entries
classified as `LorebookItemBucket.ITEM` into candidate `Item`/`ItemStack` rows (§4/§7).

Deliberately narrow in scope for this first pass: sourced only from dedicated item-describing
lorebook entries, one LLM call per entry - mirrors `VariableSchemaExtractor`'s structure (a flat
list of hint-carrying candidates, cross-reference resolution deferred to stage 3) rather than
`LocationExtractor`'s two-path design. There is intentionally no prose-fallback synthesis over
`first_message`/character bios here: most item mentions live inline in a character's own bio text,
which stage 1 already routes to `character_bio`, not a dedicated item entry - catching those too
would mean either a second synthesis pass (real scope/risk, deferred) or teaching stage 1 to
double-classify bio-embedded item mentions (a stage-1 prompt change, also deferred). This stage
only ever produces something for cards that have explicit item/inventory lorebook content.

`holder_hint`/`location_hint` are free text, exactly like `VariableFieldCandidate.owner_hint` -
resolved to a real character/location provisional id by `WorldAssembler` (`_item_and_stack_rows`),
which also enforces the one hard constraint `WorldImportService._import_item_stacks` cannot safely
violate: every stack it emits must resolve to a holder *or* a location, never neither (Neo4j-level
constraint on `ItemStack` - see SILLYTAVERN_IMPORT_PLAN.md §5/§7), so an item whose placement never
resolves is dropped entirely (as a low-confidence report note) rather than imported unplaced.
"""

import functools

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .lorebook_classifier import LorebookClassification
from .pipeline_component import SillyTavernPipelineComponent

_MAX_ITEMS_PER_SOURCE = 20


class ItemFieldCandidate(BaseModel):
    """One inferred item - field shape mirrors `Item`/`ItemStack` combined, since a local model
    describes one concrete item-in-a-place holistically rather than architecting a separate
    template/instance split itself (the same reasoning `VariableFieldCandidate` documents)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    unique: bool = False
    quantity: int = Field(1, ge=1)
    quality: str | None = None
    holder_hint: str | None = Field(
        default=None,
        description="Best-effort name of the character who owns/carries this item, copied from "
                    "context - 'self' for the card's own protagonist, another character's name if "
                    "clearly theirs, or null if not stated.",
    )
    location_hint: str | None = Field(
        default=None,
        description="Best-effort name of the place this item can be found, copied from context - "
                    "only when holder_hint doesn't already apply, otherwise null.",
    )


class ItemCandidates(BaseModel):
    """Structured output for one source (one item-bucket lorebook entry)."""

    model_config = ConfigDict(extra="forbid")

    items: list[ItemFieldCandidate] = Field(default_factory=list, max_length=_MAX_ITEMS_PER_SOURCE)


class ExtractedItem(BaseModel):
    name: str
    description: str
    unique: bool
    quantity: int
    quality: str | None = None
    holder_hint: str | None = None
    location_hint: str | None = None
    source_item_ids: list[str] = Field(default_factory=list)


class ItemExtraction(BaseModel):
    items: list[ExtractedItem] = Field(default_factory=list)


class ItemExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_ITEM_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_source(
            self, *, label: str, content: str, language: SupportedLanguage,
    ) -> ItemCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_item_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=ItemCandidates,
            messages=prompt,
            data={"label": label, "content": content},
            repair_instruction=(
                "Return a single ItemCandidates JSON object only, with at most "
                f"{_MAX_ITEMS_PER_SOURCE} entries. Only include an item you can clearly name and "
                "describe - an empty list is correct if nothing in the content is a real, "
                "concrete physical item."
            ),
            run_name="item_extractor.extract_source",
        )

    @staticmethod
    def _collect_sources(
            card: PreprocessedCard, classification: LorebookClassification,
    ) -> list[tuple[str, str, str]]:
        content_by_id = content_by_item_id(card)
        return [
            (classified.item_id, classified.item_id, content_by_id[classified.item_id])
            for classified in classification.by_bucket(LorebookItemBucket.ITEM)
            if classified.item_id in content_by_id
        ]

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            *,
            language: SupportedLanguage,
    ) -> ItemExtraction:
        sources = self._collect_sources(card, classification)
        if not sources:
            return ItemExtraction()

        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(
                    self._extract_source, label=label, content=content, language=language,
                )
                for _, label, content in sources
            ],
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="item_extractor.extract",
        )
        items = [
            ExtractedItem(source_item_ids=[item_id], **candidate.model_dump())
            for (item_id, _, _), batch in zip(sources, results)
            for candidate in batch.items
        ]
        return ItemExtraction(items=items)
