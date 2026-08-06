"""Split a card greeting into the canonical user/system turns it implies."""

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage, TurnType

from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .pipeline_component import SillyTavernPipelineComponent

_MAX_OPENING_TURNS = 8


class OpeningTurnCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TurnType
    content: str
    involved_names: list[str] = Field(default_factory=list, max_length=12)


class OpeningTurnCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turns: list[OpeningTurnCandidate] = Field(default_factory=list, max_length=_MAX_OPENING_TURNS)


class ExtractedOpeningTurn(BaseModel):
    type: TurnType
    content: str
    involved_character_ids: list[str] = Field(default_factory=list)


class OpeningTurnExtraction(BaseModel):
    turns: list[ExtractedOpeningTurn] = Field(default_factory=list)


class OpeningTurnExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_OPENING_TURN_EXTRACTOR

    async def extract(
            self, card: PreprocessedCard, characters: CharacterExtraction, *,
            language: SupportedLanguage,
    ) -> OpeningTurnExtraction:
        if not card.first_message.strip():
            return OpeningTurnExtraction()

        names = [character.target_name for character in characters.characters]
        prompt = await self._prepare_global_prompt(
            language=language, prompt_name="st_opening_turn_extractor",
        )
        llm = await self._prepare_global_llm_service()
        result = await llm.invoke_structured_with_repair(
            output_model=OpeningTurnCandidates,
            messages=prompt,
            data={"opening_message": card.first_message, "known_characters": names},
            repair_instruction=(
                "Return one OpeningTurnCandidates JSON object only. turns must contain at most "
                f"{_MAX_OPENING_TURNS} chronological entries; type must be user_input or "
                "system_response; content must be non-empty; involved_names may only contain exact "
                "names from known_characters."
            ),
            run_name="opening_turn_extractor.extract",
        )
        id_by_name = {character.target_name: character.id for character in characters.characters}
        turns = []
        for candidate in result.turns:
            content = candidate.content.strip()
            if not content:
                continue
            involved_ids = list(dict.fromkeys(
                id_by_name[name] for name in candidate.involved_names if name in id_by_name
            ))
            turns.append(ExtractedOpeningTurn(
                type=candidate.type, content=content, involved_character_ids=involved_ids,
            ))
        return OpeningTurnExtraction(turns=turns)
