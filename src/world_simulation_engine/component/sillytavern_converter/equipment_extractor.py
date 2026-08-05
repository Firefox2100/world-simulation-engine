"""Stage 2 (equipment branch, conditional) of the SillyTavern import pipeline: turn wearable-item
mentions into candidate `Equipment` rows (§4/§7), instead of letting them fall into `ItemExtractor`
(not worn, e.g. carried/stored items) or `VariableSchemaExtractor` (generic tracked stats).

Two sources, mirroring `ItemExtractor`'s and `VariableSchemaExtractor`'s designs respectively:

- Lorebook entries the classifier routes into `LorebookItemBucket.ITEM` (the same bucket
  `ItemExtractor` reads) - `_extract_source` uses a dedicated prompt tuned to pick out only
  *worn* items from that content, explicitly told to skip anything carried/stored (that's
  `ItemExtractor`'s job). Both extractors process the same entries, each pulling its own facet out
  via its own prompt - the same "one item, several dedicated extraction passes" idiom
  `LorebookClassifier`'s multi-bucket design already established.
- The opening message's MVU-conventional `<UpdateVariable><initvar>...</initvar></UpdateVariable>`
  block (`_extract_first_message_source`, gated by the same `has_initial_value_block` marker check
  `VariableSchemaExtractor` uses - real bug this was built to fix: that block's per-character outfit
  sub-section was previously falling into `VariableSchemaExtractor` as flat string variables like
  `outfit_top`, even though `Equipment` is the real domain model for "what a character is wearing."
  `VariableSchemaExtractor`'s own first-message prompt is now told to skip clothing fields entirely,
  so this extractor is the only place that block's outfit data ends up.

`holder_hint` is free text, resolved to a real character provisional id by `WorldAssembler`
(`_equipment_rows`), reusing the exact same "self"/name resolution `_resolve_item_holder` already
does for items - unlike `ItemStack`, `Equipment` has no "must be placed somewhere" constraint at
persistence time, so an equipment candidate whose holder never resolves is still imported
(unassigned), just flagged low-confidence in the report rather than dropped.
"""

import functools

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .initial_value_block import has_initial_value_block
from .lorebook_classifier import LorebookClassification
from .pipeline_component import SillyTavernPipelineComponent

_MAX_EQUIPMENT_PER_SOURCE = 20


class EquipmentFieldCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    quality: str | None = None
    holder_hint: str | None = Field(
        default=None,
        description="Best-effort name of the character who wears this, copied from context - "
                    "'self' for the card's own protagonist, another character's name if clearly "
                    "theirs, or null if not stated.",
    )
    slot: str | None = Field(
        default=None,
        description="Where on the body this is worn (e.g. 'top', 'bottom', 'footwear'), copied or "
                    "inferred from context - null if not stated/inferable.",
    )


class EquipmentCandidates(BaseModel):
    """Structured output for one source (a wearable-item lorebook entry, or the opening message)."""

    model_config = ConfigDict(extra="forbid")

    equipment: list[EquipmentFieldCandidate] = Field(
        default_factory=list, max_length=_MAX_EQUIPMENT_PER_SOURCE,
    )


class ExtractedEquipment(BaseModel):
    name: str
    description: str
    quality: str | None = None
    holder_hint: str | None = None
    slot: str | None = None
    source_item_ids: list[str] = Field(default_factory=list)


class EquipmentExtraction(BaseModel):
    equipment: list[ExtractedEquipment] = Field(default_factory=list)


class EquipmentExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_EQUIPMENT_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_source(
            self, *, label: str, content: str, language: SupportedLanguage,
    ) -> EquipmentCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_equipment_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=EquipmentCandidates,
            messages=prompt,
            data={"label": label, "content": content},
            repair_instruction=(
                "Return a single EquipmentCandidates JSON object only, with at most "
                f"{_MAX_EQUIPMENT_PER_SOURCE} entries. Only include something you can clearly name "
                "and describe as being worn - an empty list is correct if nothing in the content is "
                "a real wearable item."
            ),
            run_name="equipment_extractor.extract_source",
        )

    async def _extract_first_message_source(
            self, *, content: str, language: SupportedLanguage,
    ) -> EquipmentCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_equipment_initial_value_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=EquipmentCandidates,
            messages=prompt,
            data={"content": content},
            repair_instruction=(
                "Return a single EquipmentCandidates JSON object only, with at most "
                f"{_MAX_EQUIPMENT_PER_SOURCE} entries. Only include equipment if the opening "
                "message actually has a clothing/outfit-shaped sub-section for a character; an "
                "empty list is correct otherwise. holder_hint must be the real top-level key text "
                "from that block, never a field label."
            ),
            run_name="equipment_extractor.extract_first_message",
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
    ) -> EquipmentExtraction:
        sources = self._collect_sources(card, classification)
        has_initial_values = has_initial_value_block(card.first_message)
        if not sources and not has_initial_values:
            return EquipmentExtraction()

        calls = [
            functools.partial(
                self._extract_source, label=label, content=content, language=language,
            )
            for _, label, content in sources
        ]
        source_ids = [item_id for item_id, _, _ in sources]
        if has_initial_values:
            calls.append(
                functools.partial(
                    self._extract_first_message_source,
                    content=card.first_message,
                    language=language,
                ),
            )
            source_ids.append("first_message")

        results = await run_fan_out(
            self._fan_out_graph,
            calls,
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="equipment_extractor.extract",
        )
        equipment = [
            ExtractedEquipment(source_item_ids=[item_id], **candidate.model_dump())
            for item_id, batch in zip(source_ids, results)
            for candidate in batch.equipment
        ]
        return EquipmentExtraction(equipment=equipment)
