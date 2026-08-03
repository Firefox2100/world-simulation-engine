"""Stage 2 (narrative branch) of the SillyTavern import pipeline: turn stage 1's `history_event`
and `relationship` buckets into candidate `Event`/`MemoryAtom`/`EntityRelationship`s.

Runs after `CharacterExtractor` (needs its output as the character roster) - one structured-output
call per `history_event` item and one per `relationship` item, fanned out together in a single
batch. Per SILLYTAVERN_IMPORT_PLAN.md §3.3's knowledge-boundary rule, every call is given the
roster of already-extracted characters together with each one's `do_not_know` list, and the model
is instructed to only attach a memory to characters it doesn't contradict - but since an LLM cannot
reliably invent or copy a provisional uuid, every reference is by name, copied verbatim from the
supplied roster, and resolved to the real provisional id deterministically in code afterward (same
idiom as `LocationExtractor`'s `parent_name` resolution - see §6.2). A name that doesn't match
anything in the roster is dropped, never guessed at; an event/relationship left with no resolvable
participant is dropped entirely rather than persisted with a dangling reference. Name resolution
(`name_resolution.resolve_name`/`resolve_names`, shared with `WorldAssembler`) falls back to
substring containment when there's no byte-exact match, since this local model doesn't always
reproduce a multi-part roster name verbatim across calls - confirmed on a real card, where a
relationship about "艾琳·莫里亚蒂" resolved to zero relationships under exact-match-only resolution.
"""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage

from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .lorebook_classifier import LorebookClassification
from .name_resolution import resolve_name as _resolve_name, resolve_names as _resolve_names
from .pipeline_component import SillyTavernPipelineComponent

_MAX_ROSTER_NAMES = 6
_MAX_KEYWORDS = 6


class HistoryEventCandidate(BaseModel):
    """Structured output for one `history_event` item."""

    model_config = ConfigDict(extra="forbid")

    event_name: str
    event_summary: str
    involved_names: list[str] = Field(default_factory=list, max_length=_MAX_ROSTER_NAMES)
    memory_summary: str
    memory_keywords: list[str] = Field(default_factory=list, max_length=_MAX_KEYWORDS)
    knowing_names: list[str] = Field(
        default_factory=list, max_length=_MAX_ROSTER_NAMES,
        description="Subset of involved_names who actually remember/know this - excluding anyone "
                    "whose supplied do_not_know list rules it out.",
    )


class RelationshipCandidate(BaseModel):
    """Structured output for one `relationship` item."""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    target_name: str
    label: str
    description: str


class ExtractedEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    summary: str
    involved_character_ids: list[str] = Field(default_factory=list)
    source_item_ids: list[str] = Field(default_factory=list)


class ExtractedMemory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    character_ids: list[str] = Field(default_factory=list)
    source_item_ids: list[str] = Field(default_factory=list)


class ExtractedRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_character_id: str
    target_character_id: str
    label: str
    description: str
    source_item_ids: list[str] = Field(default_factory=list)


class NarrativeExtraction(BaseModel):
    events: list[ExtractedEvent] = Field(default_factory=list)
    memories: list[ExtractedMemory] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


def _roster(characters: CharacterExtraction) -> tuple[list[dict], dict[str, str]]:
    roster = [
        {"name": character.target_name, "do_not_know": character.result.do_not_know}
        for character in characters.characters
    ]
    id_by_name = {character.target_name: character.id for character in characters.characters}
    return roster, id_by_name


class NarrativeExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_NARRATIVE_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_history_event(
            self, *, content: str, roster: list[dict], language: SupportedLanguage,
    ) -> HistoryEventCandidate:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_narrative_event_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=HistoryEventCandidate,
            messages=prompt,
            data={"content": content, "known_characters": roster},
            repair_instruction=(
                "Return a single HistoryEventCandidate JSON object only. event_name, "
                "event_summary and memory_summary must be non-empty. involved_names and "
                "knowing_names must only contain names copied exactly from known_characters - "
                "never invent a new name."
            ),
            run_name="narrative_extractor.extract_history_event",
        )

    async def _extract_relationship(
            self, *, content: str, roster: list[dict], language: SupportedLanguage,
    ) -> RelationshipCandidate:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_narrative_relationship_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=RelationshipCandidate,
            messages=prompt,
            data={"content": content, "known_characters": roster},
            repair_instruction=(
                "Return a single RelationshipCandidate JSON object only. source_name and "
                "target_name must be two different names copied exactly from known_characters - "
                "never invent a new name. label and description must be non-empty."
            ),
            run_name="narrative_extractor.extract_relationship",
        )

    @staticmethod
    def _resolve_events(
            history_items: list[tuple[str, str]],
            history_results: list[HistoryEventCandidate],
            id_by_name: dict[str, str],
    ) -> tuple[list[ExtractedEvent], list[ExtractedMemory]]:
        events: list[ExtractedEvent] = []
        memories: list[ExtractedMemory] = []
        for (item_id, _), candidate in zip(history_items, history_results):
            involved_ids = _resolve_names(candidate.involved_names, id_by_name)
            if not involved_ids:
                continue  # no resolvable participant - never persist a dangling/fabricated event
            event = ExtractedEvent(
                name=candidate.event_name, summary=candidate.event_summary,
                involved_character_ids=involved_ids, source_item_ids=[item_id],
            )
            knowing_ids = _resolve_names(candidate.knowing_names, id_by_name)
            memories.append(ExtractedMemory(
                event_id=event.id, summary=candidate.memory_summary,
                keywords=candidate.memory_keywords,
                character_ids=knowing_ids or involved_ids, source_item_ids=[item_id],
            ))
            events.append(event)
        return events, memories

    @staticmethod
    def _resolve_relationships(
            relationship_items: list[tuple[str, str]],
            relationship_results: list[RelationshipCandidate],
            id_by_name: dict[str, str],
    ) -> list[ExtractedRelationship]:
        relationships: list[ExtractedRelationship] = []
        for (item_id, _), candidate in zip(relationship_items, relationship_results):
            source_id = _resolve_name(candidate.source_name, id_by_name)
            target_id = _resolve_name(candidate.target_name, id_by_name)
            if not source_id or not target_id or source_id == target_id:
                continue  # unresolved or self-referential - never fabricate a relationship
            relationships.append(ExtractedRelationship(
                source_character_id=source_id, target_character_id=target_id,
                label=candidate.label, description=candidate.description, source_item_ids=[item_id],
            ))
        return relationships

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            characters: CharacterExtraction,
            *,
            language: SupportedLanguage,
    ) -> NarrativeExtraction:
        content_by_id = content_by_item_id(card)
        history_items = [
            (classified.item_id, content_by_id[classified.item_id])
            for classified in classification.by_bucket(LorebookItemBucket.HISTORY_EVENT)
            if classified.item_id in content_by_id
        ]
        relationship_items = [
            (classified.item_id, content_by_id[classified.item_id])
            for classified in classification.by_bucket(LorebookItemBucket.RELATIONSHIP)
            if classified.item_id in content_by_id
        ]
        if not history_items and not relationship_items:
            return NarrativeExtraction()

        roster, id_by_name = _roster(characters)
        calls = [
            functools.partial(
                self._extract_history_event, content=content, roster=roster, language=language,
            )
            for _, content in history_items
        ] + [
            functools.partial(
                self._extract_relationship, content=content, roster=roster, language=language,
            )
            for _, content in relationship_items
        ]
        results = await run_fan_out(
            self._fan_out_graph, calls,
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="narrative_extractor.extract",
        )

        events, memories = self._resolve_events(
            history_items, results[:len(history_items)], id_by_name,
        )
        relationships = self._resolve_relationships(
            relationship_items, results[len(history_items):], id_by_name,
        )
        return NarrativeExtraction(events=events, memories=memories, relationships=relationships)
