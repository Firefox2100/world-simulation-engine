"""Stage 2 (location branch) of the SillyTavern import pipeline: turn classified card content
into candidate `Location`s.

Two independent paths, chosen by what stage 1 actually found (see SILLYTAVERN_IMPORT_PLAN.md §5):

- Cards with `location`-bucket lorebook items: one structured-output LLM call per item, extracting
  name/description/best-guess
  containing-location name, then deterministically stitching parent references into a tree by
  exact name match within this batch - never fabricating a level the content doesn't itself imply.
- Cards with none: a single bounded fallback call over `scenario`/`first_message` prose,
  synthesizing a minimal (<=2) flat location
  set - or nothing at all, if that prose gives no location cues either.

Each extracted location mints its own provisional id (`ExtractedLocation.id`/`parent_id`), same
idiom as `CharacterExtractor` - `WorldAssembler` remaps these the way `WorldImportService` already
remaps archive-supplied ids.
"""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .classifiable_items import classifiable_items, content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .lorebook_classifier import LorebookClassification
from .pipeline_component import SillyTavernPipelineComponent

_MAX_SYNTHESIZED_LOCATIONS = 2


class LocationCandidate(BaseModel):
    """Structured output for one location-item extraction call."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parent_name: str | None = Field(
        default=None,
        description="Exact-spelling name of the location this one is contained in, copied "
                    "verbatim from the supplied content, only if the content itself implies "
                    "nesting - null if this is a top-level location or nesting isn't clear.",
    )


class SynthesizedLocations(BaseModel):
    """Structured output for the no-location-items fallback call."""

    model_config = ConfigDict(extra="forbid")

    locations: list[LocationCandidate] = Field(
        default_factory=list, max_length=_MAX_SYNTHESIZED_LOCATIONS,
    )


class ExtractedLocation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    parent_id: str | None = None
    source_item_ids: list[str] = Field(default_factory=list)


class LocationExtraction(BaseModel):
    locations: list[ExtractedLocation] = Field(default_factory=list)


def _stitch_parents(candidates: list[tuple[LocationCandidate, str]]) -> list[ExtractedLocation]:
    """Deterministically link candidates by exact (whitespace-normalized) parent_name match within
    this same batch - a parent_name that doesn't match anything extracted here is dropped rather
    than guessed at, per §3.7's "don't fabricate a hierarchy the text doesn't imply"."""
    extracted = [
        ExtractedLocation(
            name=candidate.name, description=candidate.description, source_item_ids=[item_id],
        )
        for candidate, item_id in candidates
    ]
    id_by_name = {location.name.strip(): location.id for location in extracted}
    for (candidate, _), location in zip(candidates, extracted):
        parent_name = (candidate.parent_name or "").strip()
        if parent_name and parent_name in id_by_name and id_by_name[parent_name] != location.id:
            location.parent_id = id_by_name[parent_name]
    return extracted


class LocationExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_LOCATION_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_item(
            self, *, card_name: str, label: str, content: str, language: SupportedLanguage,
    ) -> LocationCandidate:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_location_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=LocationCandidate,
            messages=prompt,
            data={"card_name": card_name, "label": label, "content": content},
            repair_instruction=(
                "Return a single LocationCandidate JSON object only. name and description must "
                "both be non-empty. parent_name must be null unless the content itself clearly "
                "implies this location is contained inside another one, in which case copy that "
                "other location's name exactly as written."
            ),
            run_name="location_extractor.extract_item",
        )

    async def _synthesize_from_prose(
            self, *, card: PreprocessedCard, language: SupportedLanguage,
    ) -> SynthesizedLocations:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_location_synthesizer",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=SynthesizedLocations,
            messages=prompt,
            data={
                "card_name": card.name, "scenario": card.scenario, "first_message": card.first_message,
            },
            repair_instruction=(
                f"Return a single SynthesizedLocations JSON object only, with at most "
                f"{_MAX_SYNTHESIZED_LOCATIONS} entries. Only include a location if the scenario or "
                "opening message clearly implies one exists - an empty list is correct when "
                "neither gives any real location cue."
            ),
            run_name="location_extractor.synthesize_from_prose",
        )

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            *,
            language: SupportedLanguage,
    ) -> LocationExtraction:
        content_by_id = content_by_item_id(card)
        label_by_id = {item.item_id: item.label for item in classifiable_items(card)}
        location_items = [
            (
                classified.item_id,
                label_by_id.get(classified.item_id, classified.item_id),
                content_by_id[classified.item_id],
            )
            for classified in classification.by_bucket(LorebookItemBucket.LOCATION)
            if classified.item_id in content_by_id
        ]

        if location_items:
            candidates = await run_fan_out(
                self._fan_out_graph,
                [
                    functools.partial(
                        self._extract_item,
                        card_name=card.name, label=label, content=content, language=language,
                    )
                    for _, label, content in location_items
                ],
                max_concurrency=CONFIG.sillytavern_import_max_concurrency,
                run_name="location_extractor.extract",
            )
            item_ids = [item_id for item_id, _, _ in location_items]
            return LocationExtraction(locations=_stitch_parents(list(zip(candidates, item_ids))))

        if not card.scenario.strip() and not card.first_message.strip():
            return LocationExtraction(locations=[])

        # Record whichever combined-input fields supplied content for provenance.
        source_item_ids = [
            item_id for item_id, has_content in (
                ("field:scenario", bool(card.scenario.strip())),
                ("field:first_message", bool(card.first_message.strip())),
            )
            if has_content
        ]
        synthesized = await self._synthesize_from_prose(card=card, language=language)
        return LocationExtraction(locations=[
            ExtractedLocation(
                name=candidate.name, description=candidate.description, source_item_ids=source_item_ids,
            )
            for candidate in synthesized.locations
        ])
