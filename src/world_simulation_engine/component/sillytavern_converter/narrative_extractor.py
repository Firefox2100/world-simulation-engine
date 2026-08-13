"""Stage 2 (narrative branch) of the SillyTavern import pipeline: turn stage 1's `history_event`
and `relationship` buckets into candidate `Event`/`MemoryAtom`/`EntityRelationship`s.

Runs after `CharacterExtractor` (needs its output as the character roster) - one structured-output
call per `history_event` item and one per `relationship` item, fanned out together in a single
batch. Every call receives the already-extracted character roster and must positively identify the
characters who know or remember an event. Missing knowledge produces no memory link under the
open-world model. Since an LLM cannot
reliably invent or copy a provisional uuid, every reference is by name, copied verbatim from the
supplied roster, and resolved to the real provisional id deterministically in code afterward (same
idiom as `LocationExtractor`'s `parent_name` resolution - see §6.2). A name that doesn't match
anything in the roster is dropped, never guessed at; an event/relationship left with no resolvable
participant is dropped entirely rather than persisted with a dangling reference. Name resolution
(`name_resolution.resolve_name`/`resolve_names`, shared with `WorldAssembler`) falls back to
substring containment when there is no exact match because local models may shorten roster names.
"""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, LorebookItemBucket, SupportedLanguage
from world_simulation_engine.model import RelationshipVisibility

from .background_character_extractor import BackgroundCharacterExtraction
from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .classifiable_items import content_by_item_id
from .fan_out import build_fan_out_graph, run_fan_out
from .lorebook_classifier import LorebookClassification
from .name_resolution import resolve_name as _resolve_name, resolve_names as _resolve_names
from .pipeline_component import SillyTavernPipelineComponent

_MAX_ROSTER_NAMES = 6
_MAX_KEYWORDS = 6


class HistoricalMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observer_name: str
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list, max_length=_MAX_KEYWORDS)


class HistoryEventCandidate(BaseModel):
    """Structured output for one `history_event` item."""

    model_config = ConfigDict(extra="forbid")

    event_name: str
    event_summary: str
    involved_names: list[str] = Field(default_factory=list, max_length=_MAX_ROSTER_NAMES)
    memory_summary: str | None = None
    memory_keywords: list[str] = Field(default_factory=list, max_length=_MAX_KEYWORDS)
    knowing_names: list[str] = Field(
        default_factory=list, max_length=_MAX_ROSTER_NAMES,
        description="Characters the source positively establishes as knowing or remembering this.",
    )
    memories: list[HistoricalMemoryCandidate] = Field(default_factory=list, max_length=16)
    outcome: str | None = Field(
        default=None,
        description="What changed or resulted when the event ended; null if no outcome is stated.",
    )


class RelationshipCandidate(BaseModel):
    """Structured output for one `relationship` item."""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    target_name: str
    label: str
    description: str
    visibility: RelationshipVisibility = RelationshipVisibility.OBJECTIVE
    perspective_name: str | None = Field(
        default=None,
        description="Exact known character whose private perspective this is; required for private.",
    )
    confidence: float = Field(default=1, ge=0, le=1)


class RelationshipCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationships: list[RelationshipCandidate] = Field(default_factory=list, max_length=12)


class ExtractedEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    summary: str
    outcome: str | None = None
    opening_turn_index: int | None = Field(default=None, ge=0)
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
    visibility: RelationshipVisibility = RelationshipVisibility.OBJECTIVE
    perspective_character_id: str | None = None
    confidence: float = 1
    source_item_ids: list[str] = Field(default_factory=list)


class NarrativeExtraction(BaseModel):
    events: list[ExtractedEvent] = Field(default_factory=list)
    memories: list[ExtractedMemory] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    dropped_event_source_ids: list[str] = Field(
        default_factory=list,
        description="history_event source item ids whose candidate had no resolvable participant "
                    "and was therefore dropped entirely, never persisted.",
    )
    dropped_relationship_source_ids: list[str] = Field(
        default_factory=list,
        description="relationship source item ids that produced at least one candidate dropped "
                    "for an unresolvable source/target name or a private claim missing its "
                    "perspective character.",
    )


def _roster(
        characters: CharacterExtraction,
        background_characters: BackgroundCharacterExtraction | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """Main characters and background characters (a guard, a bartender - see
    background_character_extractor.py) share one name pool here: an event or relationship can
    involve either kind, and this extractor has no reason to treat them differently when all it
    needs is a name to resolve. Background characters are listed by their extracted `result.name`
    (the more polished identity), but `id_by_name` also keeps their raw cluster `target_name` as a
    fallback key in case a candidate still uses the original mention phrasing - main characters
    always win a name collision via setdefault, though the background reconciliation pass should
    already prevent one from happening in practice."""
    background_characters = background_characters or BackgroundCharacterExtraction()
    roster = [
        {"name": character.target_name}
        for character in characters.characters
    ] + [
        {"name": character.result.name}
        for character in background_characters.characters
    ]
    id_by_name = {character.target_name: character.id for character in characters.characters}
    for character in background_characters.characters:
        id_by_name.setdefault(character.target_name, character.id)
        id_by_name.setdefault(character.result.name, character.id)
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
                "Return one HistoryEventCandidate JSON object only. event_name and event_summary "
                "must be non-empty. Create one separate memory per positively established "
                "observer. All names must exactly match known_characters. Unknown knowledge "
                "creates no memory. Legacy memory_summary may be null and knowing_names empty."
            ),
            run_name="narrative_extractor.extract_history_event",
        )

    async def _extract_relationship(
            self, *, content: str, roster: list[dict], language: SupportedLanguage,
    ) -> RelationshipCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_narrative_relationship_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=RelationshipCandidates,
            messages=prompt,
            data={"content": content, "known_characters": roster},
            repair_instruction=(
                "Return one RelationshipCandidates JSON object only, with at most 12 distinct "
                "directional relationships. Names must exactly match known_characters. Private "
                "relationships require the owning perspective_name; do not merge opposing views."
            ),
            run_name="narrative_extractor.extract_relationship",
        )

    @staticmethod
    def _resolve_events(
            history_items: list[tuple[str, str]],
            history_results: list[HistoryEventCandidate],
            id_by_name: dict[str, str],
    ) -> tuple[list[ExtractedEvent], list[ExtractedMemory], list[str]]:
        events: list[ExtractedEvent] = []
        memories: list[ExtractedMemory] = []
        dropped_source_ids: list[str] = []
        for (item_id, _), candidate in zip(history_items, history_results):
            involved_ids = _resolve_names(candidate.involved_names, id_by_name)
            if not involved_ids:
                # no resolvable participant - never persist a dangling/fabricated event, but
                # record the drop so WorldAssembler can surface it in the conversion report
                # instead of the loss being invisible to the user reviewing the import.
                dropped_source_ids.append(item_id)
                continue
            event = ExtractedEvent(
                name=candidate.event_name, summary=candidate.event_summary, outcome=candidate.outcome,
                involved_character_ids=involved_ids, source_item_ids=[item_id],
            )
            resolved_memories = [
                memory for memory in candidate.memories if memory.observer_name in id_by_name
            ]
            if resolved_memories:
                memories.extend(ExtractedMemory(
                    event_id=event.id, summary=memory.summary, keywords=memory.keywords,
                    character_ids=[id_by_name[memory.observer_name]], source_item_ids=[item_id],
                ) for memory in resolved_memories)
            elif candidate.memory_summary:
                memories.extend(ExtractedMemory(
                    event_id=event.id, summary=candidate.memory_summary,
                    keywords=candidate.memory_keywords, character_ids=[character_id],
                    source_item_ids=[item_id],
                ) for character_id in _resolve_names(candidate.knowing_names, id_by_name))
            events.append(event)
        return events, memories, dropped_source_ids

    @staticmethod
    def _resolve_relationships(
            relationship_items: list[tuple[str, str]],
            relationship_results: list[RelationshipCandidates | RelationshipCandidate],
            id_by_name: dict[str, str],
    ) -> tuple[list[ExtractedRelationship], list[str]]:
        relationships: list[ExtractedRelationship] = []
        dropped_source_ids: list[str] = []
        for (item_id, _), batch in zip(relationship_items, relationship_results):
            candidates = batch.relationships if isinstance(batch, RelationshipCandidates) else [batch]
            for candidate in candidates:
                source_id = _resolve_name(candidate.source_name, id_by_name)
                target_id = _resolve_name(candidate.target_name, id_by_name)
                if not source_id or not target_id or source_id == target_id:
                    dropped_source_ids.append(item_id)
                    continue
                perspective_id = _resolve_name(candidate.perspective_name, id_by_name) \
                    if candidate.perspective_name else None
                if candidate.visibility == RelationshipVisibility.PRIVATE and not perspective_id:
                    dropped_source_ids.append(item_id)
                    continue
                relationships.append(ExtractedRelationship(
                    source_character_id=source_id, target_character_id=target_id,
                    label=candidate.label, description=candidate.description,
                    visibility=candidate.visibility, perspective_character_id=perspective_id,
                    confidence=candidate.confidence, source_item_ids=[item_id],
                ))
        return relationships, dropped_source_ids

    async def extract(
            self,
            card: PreprocessedCard,
            classification: LorebookClassification,
            characters: CharacterExtraction,
            background_characters: BackgroundCharacterExtraction | None = None,
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

        roster, id_by_name = _roster(characters, background_characters)
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

        events, memories, dropped_event_source_ids = self._resolve_events(
            history_items, results[:len(history_items)], id_by_name,
        )
        relationships, dropped_relationship_source_ids = self._resolve_relationships(
            relationship_items, results[len(history_items):], id_by_name,
        )
        return NarrativeExtraction(
            events=events,
            memories=memories,
            relationships=relationships,
            dropped_event_source_ids=dropped_event_source_ids,
            dropped_relationship_source_ids=dropped_relationship_source_ids,
        )
