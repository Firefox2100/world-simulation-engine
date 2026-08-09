"""Convert already-split opening turns into events and observer-specific memories."""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage

from .character_extractor import CharacterExtraction
from .fan_out import build_fan_out_graph, run_fan_out
from .narrative_extractor import ExtractedEvent, ExtractedMemory, NarrativeExtraction
from .opening_turn_extractor import ExtractedOpeningTurn, OpeningTurnExtraction
from .pipeline_component import SillyTavernPipelineComponent

_MAX_MEMORIES_PER_TURN = 8


class OpeningMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observer_name: str
    summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list, max_length=6)


class OpeningEventCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_event: bool
    name: str | None = None
    summary: str | None = None
    outcome: str | None = None
    involved_names: list[str] = Field(default_factory=list, max_length=12)
    memories: list[OpeningMemoryCandidate] = Field(
        default_factory=list, max_length=_MAX_MEMORIES_PER_TURN,
    )


class OpeningNarrativeExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_OPENING_NARRATIVE_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_one(
            self, *, turn_index: int, turn: ExtractedOpeningTurn, known_names: list[str],
            language: SupportedLanguage,
    ) -> tuple[int, OpeningEventCandidate]:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_opening_narrative_extractor",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=OpeningEventCandidate,
            messages=prompt,
            data={
                "turn_index": turn_index, "turn_type": turn.type, "content": turn.content,
                "known_characters": known_names,
            },
            repair_instruction=(
                "Return one OpeningEventCandidate JSON object only. If has_event is false, use null "
                "name/summary/outcome and empty lists. If true, name and summary are required; "
                "names must exactly match known_characters. Create memories only for characters "
                "positively established as perceiving, experiencing, or later remembering the event."
            ),
            run_name="opening_narrative_extractor.extract_one",
        )
        return turn_index, result

    async def extract(
            self, opening: OpeningTurnExtraction, characters: CharacterExtraction, *,
            language: SupportedLanguage,
    ) -> NarrativeExtraction:
        if not opening.turns:
            return NarrativeExtraction()
        known_names = [character.target_name for character in characters.characters]
        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(
                    self._extract_one, turn_index=index, turn=turn,
                    known_names=known_names, language=language,
                )
                for index, turn in enumerate(opening.turns)
            ],
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="opening_narrative_extractor.extract",
        )
        id_by_name = {character.target_name: character.id for character in characters.characters}
        events = []
        memories = []
        for turn_index, candidate in results:
            if not candidate.has_event or not candidate.name or not candidate.summary:
                continue
            involved_ids = list(dict.fromkeys(
                id_by_name[name] for name in candidate.involved_names if name in id_by_name
            ))
            resolved_memories = [
                memory for memory in candidate.memories if memory.observer_name in id_by_name
            ]
            # An event with neither a known participant nor a known observer cannot connect to the
            # authored character graph and is omitted rather than fabricated.
            if not involved_ids and not resolved_memories:
                continue
            event = ExtractedEvent(
                id=str(uuid4()), name=candidate.name, summary=candidate.summary,
                outcome=candidate.outcome, opening_turn_index=turn_index,
                involved_character_ids=involved_ids, source_item_ids=[f"opening_turn:{turn_index}"],
            )
            events.append(event)
            for memory in resolved_memories:
                memories.append(ExtractedMemory(
                    id=str(uuid4()), event_id=event.id, summary=memory.summary,
                    keywords=memory.keywords,
                    character_ids=[id_by_name[memory.observer_name]],
                    source_item_ids=[f"opening_turn:{turn_index}"],
                ))
        return NarrativeExtraction(events=events, memories=memories)
