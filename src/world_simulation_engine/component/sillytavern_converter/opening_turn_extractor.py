"""Split a card greeting into the canonical user/system turns it implies.

Turns split only on control changing between the user persona and the system (narrator/other
characters) - matching `WorldSimulator`'s own turn boundaries (see
`_create_turn_and_apply_commit`'s two call sites: one `TurnType.USER_INPUT` turn per user action,
one `TurnType.SYSTEM_RESPONSE`/`SYSTEM_CONTINUE` turn per narrated response, never split further).
A system turn's narration and any character speech within it stay one turn, carried as ordered
`blocks` - the same `NarrationBlock`/`SpeechBlock` shape `Narrator.serialize_content` already
produces for a live turn's `Turn.content` (see `model/inter_state/narration.py`). `WorldAssembler`
serializes these into that exact JSON shape (never plain prose) so an imported world's system turns
present identically to a live simulation's, through the same `TurnPresentationBlock` machinery -
see `router/turn.py`'s `_legacy_presentation`, which parses `Turn.content` as a `NarrationProposal`
when no explicit presentation rendering has been stored yet.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage, TurnType

from .background_character_extractor import BackgroundCharacterExtraction
from .card_preprocessor import PreprocessedCard
from .character_extractor import CharacterExtraction
from .pipeline_component import SillyTavernPipelineComponent

_MAX_OPENING_TURNS = 8
_MAX_BLOCKS_PER_TURN = 20


class OpeningTurnBlockCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["narration", "speech"]
    text: str = Field(min_length=1)
    character_name: str | None = Field(
        default=None,
        description="Exact known character name who speaks - required when type is speech, "
                    "always null when type is narration.",
    )


class OpeningTurnCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TurnType
    content: str
    blocks: list[OpeningTurnBlockCandidate] = Field(default_factory=list, max_length=_MAX_BLOCKS_PER_TURN)
    involved_names: list[str] = Field(default_factory=list, max_length=12)


class OpeningTurnCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turns: list[OpeningTurnCandidate] = Field(default_factory=list, max_length=_MAX_OPENING_TURNS)


class ExtractedOpeningTurnBlock(BaseModel):
    type: Literal["narration", "speech"]
    text: str
    character_id: str | None = None
    character_name: str | None = None


class ExtractedOpeningTurn(BaseModel):
    type: TurnType
    content: str
    blocks: list[ExtractedOpeningTurnBlock] = Field(default_factory=list)
    involved_character_ids: list[str] = Field(default_factory=list)


class OpeningTurnExtraction(BaseModel):
    turns: list[ExtractedOpeningTurn] = Field(default_factory=list)


def _resolve_block(
        block: OpeningTurnBlockCandidate, id_by_name: dict[str, str],
) -> ExtractedOpeningTurnBlock | None:
    text = block.text.strip()
    if not text:
        return None
    if block.type == "speech":
        character_id = id_by_name.get(block.character_name) if block.character_name else None
        if not character_id:
            # A live SpeechBlock requires a real character_id (see narration.py) - an
            # unresolvable name is folded into narration rather than emitting an invalid speech
            # block or silently dropping the line, the same "never fabricate a reference, keep
            # the content" idiom every other stage-2 extractor already follows.
            return ExtractedOpeningTurnBlock(type="narration", text=text)
        return ExtractedOpeningTurnBlock(
            type="speech", text=text, character_id=character_id, character_name=block.character_name,
        )
    return ExtractedOpeningTurnBlock(type="narration", text=text)


class OpeningTurnExtractor(SillyTavernPipelineComponent):
    COMPONENT_TYPE = ComponentType.ST_OPENING_TURN_EXTRACTOR

    async def extract(
            self, card: PreprocessedCard, characters: CharacterExtraction,
            background_characters: BackgroundCharacterExtraction | None = None, *,
            language: SupportedLanguage,
    ) -> OpeningTurnExtraction:
        if not card.first_message.strip():
            return OpeningTurnExtraction()

        background_characters = background_characters or BackgroundCharacterExtraction()
        names = [character.target_name for character in characters.characters] + [
            character.result.name for character in background_characters.characters
        ]
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
                "names from known_characters. For a system_response turn, also split its content "
                "into blocks: narration blocks (character_name null) and speech blocks "
                "(character_name an exact known name) in reading order - never split one scene "
                "into multiple turns just because it mixes narration and speech."
            ),
            run_name="opening_turn_extractor.extract",
        )
        id_by_name = {character.target_name: character.id for character in characters.characters}
        for character in background_characters.characters:
            id_by_name.setdefault(character.target_name, character.id)
            id_by_name.setdefault(character.result.name, character.id)
        turns = []
        for candidate in result.turns:
            content = candidate.content.strip()
            if not content:
                continue
            involved_ids = list(dict.fromkeys(
                id_by_name[name] for name in candidate.involved_names if name in id_by_name
            ))
            blocks = []
            if candidate.type != TurnType.USER_INPUT:
                blocks = [
                    resolved
                    for block in candidate.blocks
                    if (resolved := _resolve_block(block, id_by_name)) is not None
                ]
            turns.append(ExtractedOpeningTurn(
                type=candidate.type, content=content, blocks=blocks,
                involved_character_ids=involved_ids,
            ))
        return OpeningTurnExtraction(turns=turns)
