"""Stage 2 (world lore branch) of the SillyTavern import pipeline: turn stage 1's `world_lore`-
bucket items into a single `World.description`.

Unlike `CharacterExtractor`/`LocationExtractor`, this is a many-to-one consolidation, not a
fan-out: every `world_lore`-bucket item (which already includes a card's own `description` field
when stage 1 classifies it that way - e.g. card 04, where `description` holds only shared setting
lore, no single protagonist) is handed to one structured-output call that writes a single cohesive
description, mirroring `MemorySummarizer`'s "many sources, one summary" shape rather than
`LorebookClassifier`'s "one call per item" shape. No per-world narration-style output is produced
here - see SILLYTAVERN_IMPORT_PLAN.md §4, the user rejected that as redundant with the existing
narrator prompt override.
"""

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .classifiable_items import content_by_item_id
from .lorebook_classifier import LorebookClassification
from .pipeline_component import SillyTavernPipelineComponent


class WorldLoreExtractionResult(BaseModel):
    """Structured output for the single consolidation call."""

    model_config = ConfigDict(extra="forbid")

    description: str


class WorldLoreExtraction(BaseModel):
    description: str | None = None
    source_item_ids: list[str] = Field(default_factory=list)


class WorldLoreExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_WORLD_LORE_EXTRACTOR

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            *,
            language: SupportedLanguage,
    ) -> WorldLoreExtraction:
        content_by_id = content_by_item_id(card)
        lore_items = [
            (classified.item_id, content_by_id[classified.item_id])
            for classified in classification.by_bucket(LorebookItemBucket.WORLD_LORE)
            if classified.item_id in content_by_id
        ]
        if not lore_items:
            return WorldLoreExtraction()

        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_world_lore_extractor",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=WorldLoreExtractionResult,
            messages=prompt,
            data={"card_name": card.name, "lore_items": [content for _, content in lore_items]},
            repair_instruction=(
                "Return a single WorldLoreExtractionResult JSON object only. description must be "
                "non-empty prose consolidating every supplied lore item - do not just concatenate "
                "them verbatim."
            ),
            run_name="world_lore_extractor.extract",
        )
        return WorldLoreExtraction(
            description=result.description,
            source_item_ids=[item_id for item_id, _ in lore_items],
        )
