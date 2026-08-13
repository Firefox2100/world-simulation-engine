"""Stage 2 (intent branch) of the SillyTavern import pipeline: infer candidate `Intent`s per
already-extracted character.

Runs after `CharacterExtractor` - one call per character, working off its already-synthesized
`CharacterExtractionResult` (description/public_state/private_state/current_activity) rather than
re-deriving raw lorebook content, since that description is already meant to be a self-contained
summary of background, personality and role (§5's `CharacterExtractor` write-up) and re-clustering
here would need to re-match by name anyway - clusters built a second time would mint fresh
provisional ids, not the ones already assigned to `characters.characters`. Bounded output (at most
3 intents per character, same discipline as `RelationshipUpdateProposal.changes`'s cap): the plan's
"per major character" scoping is left to the model itself rather than a separate classifier - an
empty list is the correct, expected answer for a minor/background character with nothing
goal-driving implied, not a failure.
"""

import functools
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import (
    ComponentType, IntentHorizon, IntentStatus, IntentType, SupportedLanguage,
)

from .character_extractor import CharacterExtraction, ExtractedCharacter
from .fan_out import build_fan_out_graph, run_fan_out
from .narrative_extractor import NarrativeExtraction
from .pipeline_component import SillyTavernPipelineComponent

_MAX_INTENTS_PER_CHARACTER = 3


class IntentCandidate(BaseModel):
    """One inferred intent - field shape mirrors `Intent`'s core fields, minus id/embedding."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: IntentType
    description: str
    priority: float = Field(ge=0, le=1)
    urgency: float = Field(ge=0, le=1)
    status: IntentStatus
    horizon: IntentHorizon
    desired_state: str | None = None
    success_conditions: list[str] = Field(default_factory=list, max_length=5)
    failure_conditions: list[str] = Field(default_factory=list, max_length=5)
    maintenance_conditions: list[str] = Field(default_factory=list, max_length=5)
    constraints: list[str] = Field(default_factory=list, max_length=5)
    current_plan: list[str] = Field(default_factory=list, max_length=6)
    next_action_biases: list[str] = Field(default_factory=list, max_length=5)
    blockers: list[str] = Field(default_factory=list, max_length=5)
    open_threads: list[str] = Field(default_factory=list, max_length=5)
    created_by_event_id: str | None = None
    contributing_event_ids: list[str] = Field(default_factory=list, max_length=5)


class IntentCandidates(BaseModel):
    """Structured output for one character's intent-extraction call."""

    model_config = ConfigDict(extra="forbid")

    intents: list[IntentCandidate] = Field(
        default_factory=list, max_length=_MAX_INTENTS_PER_CHARACTER,
    )


class ExtractedIntent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    character_id: str
    name: str
    type: IntentType
    description: str
    priority: float
    urgency: float
    status: IntentStatus
    horizon: IntentHorizon
    desired_state: str | None = None
    success_conditions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    maintenance_conditions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    current_plan: list[str] = Field(default_factory=list)
    next_action_biases: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    created_by_event_id: str | None = None
    contributing_event_ids: list[str] = Field(default_factory=list)


class IntentExtraction(BaseModel):
    intents: list[ExtractedIntent] = Field(default_factory=list)


class IntentExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_INTENT_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_one(
            self, *, character: ExtractedCharacter, narrative: NarrativeExtraction,
            language: SupportedLanguage,
    ) -> IntentCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_intent_extractor",
        )
        llm = await self._prepare_global_llm_service()
        relevant_events = [
            event for event in narrative.events if character.id in event.involved_character_ids
        ]
        result = await llm.invoke_structured_with_repair(
            output_model=IntentCandidates,
            messages=prompt,
            data={
                "name": character.target_name,
                "description": character.result.description,
                "public_state": character.result.public_state,
                "private_state": character.result.private_state,
                "current_activity": character.result.current_activity,
                "events": [event.model_dump() for event in relevant_events],
            },
            repair_instruction=(
                "Return a single IntentCandidates JSON object only, with at most "
                f"{_MAX_INTENTS_PER_CHARACTER} entries. An empty intents list is correct when "
                "nothing goal-driving is implied for this character - do not fabricate one. "
                "priority and urgency are decimals between 0 and 1 (e.g. 0.7) - never a 1-10 or "
                "percentage scale; rescale any value outside that range instead of clamping it to "
                "0 or 1."
            ),
            run_name="intent_extractor.extract_one",
        )
        known_event_ids = {event.id for event in relevant_events}
        for intent in result.intents:
            if intent.created_by_event_id not in known_event_ids:
                intent.created_by_event_id = None
            intent.contributing_event_ids = list(dict.fromkeys(
                event_id for event_id in intent.contributing_event_ids
                if event_id in known_event_ids and event_id != intent.created_by_event_id
            ))
        return result

    async def extract(
            self,
            characters: CharacterExtraction,
            narrative: NarrativeExtraction | None = None,
            *,
            language: SupportedLanguage,
    ) -> IntentExtraction:
        if not characters.characters:
            return IntentExtraction()
        narrative = narrative or NarrativeExtraction()

        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(
                    self._extract_one, character=character, narrative=narrative, language=language,
                )
                for character in characters.characters
            ],
            max_concurrency=CONFIG.sillytavern_import_max_concurrency,
            run_name="intent_extractor.extract",
        )
        intents = [
            ExtractedIntent(character_id=character.id, **candidate.model_dump())
            for character, batch in zip(characters.characters, results)
            for candidate in batch.intents
        ]
        return IntentExtraction(intents=intents)
