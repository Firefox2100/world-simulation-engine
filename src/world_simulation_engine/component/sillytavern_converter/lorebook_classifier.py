"""Stage 1 of the SillyTavern import pipeline: classify every card field and lorebook entry.

One structured-output LLM call per item (no batching - see CLAUDE.md's local-model rules and
SILLYTAVERN_IMPORT_PLAN.md §3.5/§9.6), fanned out concurrently through `fan_out.run_fan_out` and
capped by `CONFIG.sillytavern_import_max_concurrency`. This is deliberately a classification pass,
not an extraction pass: cheap, bounded, and it's what lets every stage-2 extractor work off a
filtered subset instead of re-scanning the whole card.
"""

import functools

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .classifiable_items import ClassifiableItem, classifiable_items
from .fan_out import build_fan_out_graph, run_fan_out
from .pipeline_component import SillyTavernPipelineComponent


_MAX_BUCKETS_PER_ITEM = 4


class LorebookItemClassification(BaseModel):
    """Structured output for one classification call.

    `buckets` is a list because one entry can mix biography, event, and relationship content.
    Every stage-2 extractor filters via
    `LorebookClassification.by_bucket`, which now checks membership rather than equality, so one
    item can be picked up by multiple downstream extractors, each pulling its own facet out of the
    same raw text via its own dedicated prompt.
    """

    model_config = ConfigDict(extra="forbid")

    buckets: list[LorebookItemBucket] = Field(
        min_length=1, max_length=_MAX_BUCKETS_PER_ITEM,
        description="Every category that genuinely applies to this item's content, most important "
                    "first - almost always just one, but list more when the content itself mixes "
                    "categories. Use [irrelevant] alone when nothing else applies.",
    )
    target_name: str | None = Field(
        default=None,
        description="The character or location name this item is primarily about, using the "
                    "exact spelling from the content, when applicable to any of its buckets.",
    )


class ClassifiedItem(BaseModel):
    """One item's classification result, still tagged with the id that produced it."""

    item_id: str
    buckets: list[LorebookItemBucket]
    target_name: str | None = None


class LorebookClassification(BaseModel):
    items: list[ClassifiedItem] = Field(default_factory=list)

    def by_bucket(self, bucket: LorebookItemBucket) -> list[ClassifiedItem]:
        return [item for item in self.items if bucket in item.buckets]


class LorebookClassifier(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_LOREBOOK_CLASSIFIER

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _classify_item(
            self,
            *,
            item: ClassifiableItem,
            language: SupportedLanguage,
    ) -> ClassifiedItem:
        prompt = await self._prepare_global_prompt(
            language=language,
            prompt_name="st_lorebook_classifier",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=LorebookItemClassification,
            messages=prompt,
            data=item.model_dump(),
            repair_instruction=(
                f"Return a single LorebookItemClassification JSON object only. buckets must be a "
                f"list of 1-{_MAX_BUCKETS_PER_ITEM} values from the listed categories - most items "
                "need only one, list more only when the content genuinely mixes categories, and "
                "use [\"irrelevant\"] alone when nothing else applies. target_name is optional - "
                "omit or use null when no specific character/location name applies."
            ),
            run_name="lorebook_classifier.classify_item",
        )
        return ClassifiedItem(
            item_id=item.item_id, buckets=result.buckets, target_name=result.target_name,
        )

    async def classify(
            self,
            card: PreprocessedCard,
            *,
            language: SupportedLanguage,
    ) -> LorebookClassification:
        items = classifiable_items(card)
        if not items:
            return LorebookClassification(items=[])

        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(self._classify_item, item=item, language=language)
                for item in items
            ],
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="lorebook_classifier.classify",
        )
        return LorebookClassification(items=results)
