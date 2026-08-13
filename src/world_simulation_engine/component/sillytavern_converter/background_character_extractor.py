"""Stage 2 (background character branch) of the SillyTavern import pipeline: turns names that are
only ever *mentioned* - never given their own biography - into candidate `BackgroundCharacter`s
(this system's model for "not important enough to have his own agent... only reactive, cannot make
decisions directly" - see `model/character.py`). A guard posted at a door, a bartender who only
exists to serve a scene, a name in a history event with no bio of their own: exactly this model.

Runs immediately after `CharacterExtractor` and reuses its exact name pool
(`character_name_pool.character_related_names`) so a name is a "background" candidate here iff
`CharacterExtractor` never turned it into a main character - the two stages are two outcomes of one
partition, not independently-derived guesses that could disagree with each other.

Identity resolution happens twice, deterministically, using the same `name_resolution.resolve_name`
convention every other stage-3 extractor already relies on to match free-text names against a known
roster - never an LLM judgment call, per this pipeline's "never trust the model to invent/match ids"
discipline (see narrative_extractor.py's module docstring for the same idiom):

1. Before extraction: a candidate name that already resolves (exact or substring) against the main
   character roster is dropped immediately - this is what stops a main character who is only
   briefly mentioned in one chunk (a history event, a stray relationship note) from spawning a
   duplicate background entry. The content itself doesn't need separate handling: any event/
   relationship/item reference using that name already resolves to the main character elsewhere.
2. After extraction: the LLM's own inferred `name` for a surviving candidate is checked again
   against the main roster - source prose sometimes only reveals a person's real identity once
   enough of their scattered mentions are read together (e.g. "the bartender" turns out to be
   named in one of the gathered fragments), which the pre-filter's literal string matching can't
   see in advance. A post-extraction match here means this was actually a main character in
   disguise, not a genuine background one, so it is dropped rather than kept as a duplicate.

A third, purely structural pass merges any two surviving candidates whose *extracted* names
converge (again by `character_name_pool.merge_similar_names`, not by re-invoking the LLM) - two
different raw surface forms (e.g. a voice-only mention and a separate history-event mention) can
easily end up in different pre-extraction clusters and still resolve to the same normalized name
once the model has actually read their content.

Every drop/merge decision is recorded in `BackgroundCharacterExtraction.conversion_notes` so
`WorldAssembler` can surface it in the conversion report - a user reviewing the import should be
able to see why a name they remember from the card isn't a separate background character.
"""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .character_name_pool import character_related_names, merge_similar_names
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .lorebook_classifier import LorebookClassification
from .name_resolution import resolve_name
from .pipeline_component import SillyTavernPipelineComponent


class BackgroundCharacterCluster(BaseModel):
    """Everything gathered about one candidate background character, before extraction."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    target_name: str
    voice_content: list[str] = Field(default_factory=list)
    related_history: list[str] = Field(default_factory=list)
    source_item_ids: list[str] = Field(default_factory=list)


class BackgroundCharacterExtractionResult(BaseModel):
    """Structured output for one background character extraction call. Deliberately thin - a
    background character is `id`/`name`/`description` only in this system's own model (plus a
    location, resolved separately), never a full agent profile."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    location_hint: str | None = Field(
        default=None,
        description="Best-effort name of the place this character is normally found, copied from "
                    "context, or null if not stated.",
    )


class ExtractedBackgroundCharacter(BaseModel):
    """One cluster's extraction result, still tagged with its source for provenance."""

    id: str
    target_name: str
    result: BackgroundCharacterExtractionResult
    source_item_ids: list[str]


class BackgroundCharacterExtraction(BaseModel):
    characters: list[ExtractedBackgroundCharacter] = Field(default_factory=list)
    conversion_notes: list[str] = Field(default_factory=list)


class BackgroundCharacterExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_BACKGROUND_CHARACTER_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    @staticmethod
    def _build_clusters(
            card: PreprocessedCard,
            classification: LorebookClassification,
            main_character_names: set[str],
    ) -> list[BackgroundCharacterCluster]:
        content_by_id = content_by_item_id(card)
        main_lookup = {name: name for name in main_character_names}

        names = character_related_names(classification)
        orphan_names = {
            name for name in names
            if resolve_name(name, main_lookup) is None
        }
        if not orphan_names:
            return []
        canonical_names = merge_similar_names(orphan_names)

        clusters: dict[str, BackgroundCharacterCluster] = {}

        def cluster_for(canonical: str) -> BackgroundCharacterCluster:
            return clusters.setdefault(canonical, BackgroundCharacterCluster(target_name=canonical))

        for classified in classification.by_bucket(LorebookItemBucket.CHARACTER_VOICE):
            content = content_by_id.get(classified.item_id)
            if not content or not classified.target_name:
                continue
            canonical = canonical_names.get(classified.target_name)
            if not canonical:
                continue  # resolved to a main character, not an orphan
            cluster = cluster_for(canonical)
            cluster.voice_content.append(content)
            cluster.source_item_ids.append(classified.item_id)

        for bucket in (LorebookItemBucket.HISTORY_EVENT, LorebookItemBucket.RELATIONSHIP):
            for classified in classification.by_bucket(bucket):
                content = content_by_id.get(classified.item_id)
                if not content or not classified.target_name:
                    continue
                canonical = canonical_names.get(classified.target_name)
                if not canonical:
                    continue
                cluster = cluster_for(canonical)
                cluster.related_history.append(content)
                cluster.source_item_ids.append(classified.item_id)

        # A name that only ever showed up as a bare reference with no attachable content (every
        # matching item's content lookup failed) has nothing to extract from - drop it rather than
        # asking the model to invent a person from nothing.
        return [
            cluster for cluster in clusters.values()
            if cluster.voice_content or cluster.related_history
        ]

    async def _extract_one(
            self,
            *,
            cluster: BackgroundCharacterCluster,
            language: SupportedLanguage,
    ) -> ExtractedBackgroundCharacter:
        prompt = await self._prepare_global_prompt(
            language=language,
            prompt_name="st_background_character_extractor",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=BackgroundCharacterExtractionResult,
            messages=prompt,
            data=cluster.model_dump(exclude={"id"}),
            repair_instruction=(
                "Return a single BackgroundCharacterExtractionResult JSON object only. name and "
                "description must be non-empty."
            ),
            run_name="background_character_extractor.extract_one",
        )
        return ExtractedBackgroundCharacter(
            id=cluster.id,
            target_name=cluster.target_name,
            result=result,
            source_item_ids=cluster.source_item_ids,
        )

    @staticmethod
    def _reconcile(
            results: list[ExtractedBackgroundCharacter],
            main_character_names: set[str],
    ) -> BackgroundCharacterExtraction:
        main_lookup = {name: name for name in main_character_names}
        notes: list[str] = []

        survivors: list[ExtractedBackgroundCharacter] = []
        for candidate in results:
            if resolve_name(candidate.result.name, main_lookup) is not None:
                notes.append(
                    f"Dropped background character candidate {candidate.result.name!r} "
                    f"(clustered from mentions of {candidate.target_name!r}): once extracted, its "
                    "name resolved to an already-extracted main character, not a separate minor "
                    "character. Any event/relationship/item referencing this name already "
                    "resolves to that main character."
                )
                continue
            survivors.append(candidate)

        # Second dedup pass on the *extracted* names, not the raw clustering input names - two
        # different raw surface forms can independently converge on the same normalized name once
        # the model has actually read their content (see module docstring).
        canonical_by_extracted_name = merge_similar_names({c.result.name for c in survivors})
        merged: dict[str, ExtractedBackgroundCharacter] = {}
        for candidate in survivors:
            canonical = canonical_by_extracted_name[candidate.result.name]
            existing = merged.get(canonical)
            if existing is None:
                merged[canonical] = candidate
                continue
            notes.append(
                f"Merged background character candidate {candidate.result.name!r} into "
                f"{existing.result.name!r}: both resolved to the same person."
            )
            richer = (
                candidate.result
                if len(candidate.result.description) > len(existing.result.description)
                else existing.result
            )
            merged[canonical] = ExtractedBackgroundCharacter(
                id=existing.id,
                target_name=existing.target_name,
                result=richer,
                source_item_ids=[*existing.source_item_ids, *candidate.source_item_ids],
            )

        return BackgroundCharacterExtraction(
            characters=list(merged.values()),
            conversion_notes=notes,
        )

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            characters: CharacterExtraction,
            *,
            language: SupportedLanguage,
    ) -> BackgroundCharacterExtraction:
        main_character_names = {character.target_name for character in characters.characters}
        clusters = self._build_clusters(card, classification, main_character_names)
        if not clusters:
            return BackgroundCharacterExtraction()

        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(self._extract_one, cluster=cluster, language=language)
                for cluster in clusters
            ],
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="background_character_extractor.extract",
        )
        return self._reconcile(results, main_character_names)
