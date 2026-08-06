"""Stage 2 (character branch) of the SillyTavern import pipeline: turn classified card content
into candidate `Character`s.

Deterministically clusters stage-1 output by (best-effort normalized) character name, then runs
one structured-output LLM call per cluster - fan-out per item again, no batching, same discipline
as stage 1. Each cluster mints its own provisional id (`CharacterCluster.id`/`ExtractedCharacter.id`)
so later stages (narrative/intent extraction, `WorldAssembler`) can reference a character by id
directly instead of re-resolving `target_name` strings - `WorldAssembler` remaps these provisional
ids to real ones exactly the way `WorldImportService` already remaps archive-supplied ids.
"""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .lorebook_classifier import LorebookClassification
from .pipeline_component import SillyTavernPipelineComponent

# A character extracted from voice-line content alone, with no matching bio entry anywhere, is
# more likely a naming mismatch (stage 1 classifies each item with no cross-item context, so the
# same person can surface under different surface forms - see _merge_similar_names) than a real
# bio-less character; such voice-only clusters are dropped rather than fabricating a character
# from dialogue samples alone.
_MIN_NAME_MERGE_LENGTH = 2


class CharacterCluster(BaseModel):
    """Everything gathered about one candidate character, before extraction."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Provisional id, stable for the rest of this pipeline run - later extractors "
                    "(narrative, intents) and WorldAssembler reference this character by id rather "
                    "than re-resolving target_name, mirroring how WorldImportService already treats "
                    "archive-supplied ids (remapped once, referenced by id from then on).",
    )
    target_name: str
    card_name: str
    bio_content: list[str] = Field(default_factory=list)
    voice_content: list[str] = Field(default_factory=list)
    related_history: list[str] = Field(default_factory=list)
    source_item_ids: list[str] = Field(default_factory=list)


class CharacterExtractionResult(BaseModel):
    """Structured output for one character extraction call. Every field is best-effort inference,
    not a verbatim copy - cards rarely spell these out the way this system's model wants."""

    model_config = ConfigDict(extra="forbid")

    name: str
    age: int = Field(ge=0, le=200)
    gender: str
    appearance: str
    description: str
    public_state: str
    private_state: str
    current_activity: str
    speech_style: str = ""
    user_controlled: bool = False


class ExtractedCharacter(BaseModel):
    """One cluster's extraction result, still tagged with its source for provenance."""

    id: str
    target_name: str
    result: CharacterExtractionResult
    source_item_ids: list[str]


class CharacterExtraction(BaseModel):
    characters: list[ExtractedCharacter] = Field(default_factory=list)


def _merge_similar_names(names: set[str]) -> dict[str, str]:
    """Map each name to a canonical form, merging names that are substrings of one another.

    Stage 1 classifies every item in isolation, so the same character can appear under different
    surface forms across items. Names shorter than `_MIN_NAME_MERGE_LENGTH` are never merge targets,
    to avoid a short/common substring accidentally absorbing an unrelated longer name.
    """
    canonical: dict[str, str] = {}
    for name in sorted(names, key=len, reverse=True):
        match = None
        for existing in dict.fromkeys(canonical.values()):
            if len(existing) < _MIN_NAME_MERGE_LENGTH or len(name) < _MIN_NAME_MERGE_LENGTH:
                continue
            if name in existing or existing in name:
                match = existing
                break
        canonical[name] = match or name
    return canonical


class CharacterExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_CHARACTER_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    @staticmethod
    def _build_clusters(card: PreprocessedCard, classification: LorebookClassification) -> list[CharacterCluster]:
        content_by_id = content_by_item_id(card)
        bio_classifications = classification.by_bucket(LorebookItemBucket.CHARACTER_BIO)
        # Only use the card name when every bio item is unnamed. Otherwise, dropping an unnamed
        # fragment avoids fabricating a duplicate character from the card title.
        has_named_bio = any(classified.target_name for classified in bio_classifications)

        character_buckets = (
            LorebookItemBucket.CHARACTER_BIO, LorebookItemBucket.CHARACTER_VOICE,
            LorebookItemBucket.HISTORY_EVENT, LorebookItemBucket.RELATIONSHIP,
        )
        # Merge names across every character-related bucket so shortened forms share a cluster.
        names = {
            classified.target_name
            for bucket in character_buckets
            for classified in classification.by_bucket(bucket)
            if classified.target_name
        }
        if not has_named_bio:
            names.add(card.name)
        canonical_names = _merge_similar_names(names)

        clusters: dict[str, CharacterCluster] = {}

        def cluster_for(name: str) -> CharacterCluster:
            canonical = canonical_names.get(name, name)
            return clusters.setdefault(canonical, CharacterCluster(
                target_name=canonical, card_name=card.name,
            ))

        for classified in bio_classifications:
            content = content_by_id.get(classified.item_id)
            if not content:
                continue
            name = classified.target_name or (None if has_named_bio else card.name)
            if not name:
                continue
            cluster = cluster_for(name)
            cluster.bio_content.append(content)
            cluster.source_item_ids.append(classified.item_id)

        for classified in classification.by_bucket(LorebookItemBucket.CHARACTER_VOICE):
            content = content_by_id.get(classified.item_id)
            if not content or not classified.target_name:
                continue
            canonical = canonical_names.get(classified.target_name)
            if not canonical or canonical not in clusters:
                continue  # no bio to attach voice-only content to
            clusters[canonical].voice_content.append(content)
            clusters[canonical].source_item_ids.append(classified.item_id)

        for bucket in (LorebookItemBucket.HISTORY_EVENT, LorebookItemBucket.RELATIONSHIP):
            for classified in classification.by_bucket(bucket):
                content = content_by_id.get(classified.item_id)
                if not content or not classified.target_name:
                    continue
                canonical = canonical_names.get(classified.target_name)
                if canonical and canonical in clusters:
                    clusters[canonical].related_history.append(content)

        return list(clusters.values())

    async def _extract_one(
            self,
            *,
            cluster: CharacterCluster,
            language: SupportedLanguage,
    ) -> ExtractedCharacter:
        prompt = await self._prepare_global_prompt(
            language=language,
            prompt_name="st_character_extractor",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=CharacterExtractionResult,
            messages=prompt,
            data=cluster.model_dump(exclude={"id"}),
            repair_instruction=(
                "Return a single CharacterExtractionResult JSON object only. age must be a "
                "concrete integer (your best estimate if not stated)."
            ),
            run_name="character_extractor.extract_one",
        )
        return ExtractedCharacter(
            id=cluster.id,
            target_name=cluster.target_name,
            result=result,
            source_item_ids=cluster.source_item_ids,
        )

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            *,
            language: SupportedLanguage,
    ) -> CharacterExtraction:
        clusters = self._build_clusters(card, classification)
        if not clusters:
            return CharacterExtraction(characters=[])

        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(self._extract_one, cluster=cluster, language=language)
                for cluster in clusters
            ],
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="character_extractor.extract",
        )
        return CharacterExtraction(characters=results)
