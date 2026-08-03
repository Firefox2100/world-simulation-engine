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


class IntentExtraction(BaseModel):
    intents: list[ExtractedIntent] = Field(default_factory=list)


class IntentExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_INTENT_EXTRACTOR

    def __init__(self, database, prompt_loader=None):
        super().__init__(database=database, prompt_loader=prompt_loader)
        self._fan_out_graph = build_fan_out_graph()

    async def _extract_one(
            self, *, character: ExtractedCharacter, language: SupportedLanguage,
    ) -> IntentCandidates:
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_intent_extractor",
        )
        llm = await self._prepare_global_llm_service()
        return await llm.invoke_structured_with_repair(
            output_model=IntentCandidates,
            messages=prompt,
            data={
                "name": character.target_name,
                "description": character.result.description,
                "public_state": character.result.public_state,
                "private_state": character.result.private_state,
                "current_activity": character.result.current_activity,
            },
            repair_instruction=(
                "Return a single IntentCandidates JSON object only, with at most "
                f"{_MAX_INTENTS_PER_CHARACTER} entries. An empty intents list is correct when "
                "nothing goal-driving is implied for this character - do not fabricate one."
            ),
            run_name="intent_extractor.extract_one",
        )

    async def extract(
            self,
            characters: CharacterExtraction,
            *,
            language: SupportedLanguage,
    ) -> IntentExtraction:
        if not characters.characters:
            return IntentExtraction()

        results = await run_fan_out(
            self._fan_out_graph,
            [
                functools.partial(self._extract_one, character=character, language=language)
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
