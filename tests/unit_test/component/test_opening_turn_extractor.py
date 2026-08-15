from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import (
    CharacterExtraction, CharacterExtractionResult, ExtractedCharacter, OpeningTurnBlockCandidate,
    OpeningTurnCandidate, OpeningTurnCandidates, OpeningTurnExtractor, PreprocessedCard,
)
from world_simulation_engine.misc.enums import SupportedLanguage, TurnType


def make_character(name="Guide", char_id="char-guide"):
    return ExtractedCharacter(
        id=char_id, target_name=name, source_item_ids=[],
        result=CharacterExtractionResult(
            name=name, age=30, gender="unknown", appearance="plain", description="A guide.",
            public_state="waiting", private_state="calm", current_activity="waiting",
        ),
    )


async def test_extract_splits_opening_and_resolves_only_exact_character_names():
    extractor = OpeningTurnExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=OpeningTurnCandidates(turns=[
            OpeningTurnCandidate(
                type=TurnType.USER_INPUT, content="You enter the room.", involved_names=["Guide"],
            ),
            OpeningTurnCandidate(
                type=TurnType.SYSTEM_RESPONSE, content="Guide welcomes you.",
                involved_names=["Guide", "Invented Person"],
            ),
        ])),
    ))

    result = await extractor.extract(
        PreprocessedCard(name="Card", first_message="Mixed greeting"),
        CharacterExtraction(characters=[make_character()]), language=SupportedLanguage.ENGLISH,
    )

    assert [turn.type for turn in result.turns] == [TurnType.USER_INPUT, TurnType.SYSTEM_RESPONSE]
    assert result.turns[0].involved_character_ids == ["char-guide"]
    assert result.turns[1].involved_character_ids == ["char-guide"]


async def test_extract_resolves_speech_blocks_and_folds_unknown_speakers_into_narration():
    extractor = OpeningTurnExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=OpeningTurnCandidates(turns=[
            OpeningTurnCandidate(
                type=TurnType.SYSTEM_RESPONSE,
                content='The Guide steps forward. "Welcome," they say. A stranger scoffs.',
                blocks=[
                    OpeningTurnBlockCandidate(type="narration", text="The Guide steps forward."),
                    OpeningTurnBlockCandidate(type="speech", text="Welcome.", character_name="Guide"),
                    OpeningTurnBlockCandidate(
                        type="speech", text="A stranger scoffs.", character_name="Unknown Person",
                    ),
                ],
                involved_names=["Guide"],
            ),
            OpeningTurnCandidate(
                type=TurnType.USER_INPUT,
                content="You nod back.",
                blocks=[OpeningTurnBlockCandidate(type="narration", text="You nod back.")],
            ),
        ])),
    ))

    result = await extractor.extract(
        PreprocessedCard(name="Card", first_message="Mixed greeting"),
        CharacterExtraction(characters=[make_character()]), language=SupportedLanguage.ENGLISH,
    )

    system_turn, user_turn = result.turns
    assert [block.type for block in system_turn.blocks] == ["narration", "speech", "narration"]
    assert system_turn.blocks[1].character_id == "char-guide"
    assert system_turn.blocks[1].character_name == "Guide"
    # The unresolvable "Unknown Person" speaker must not produce an invalid speech block (a real
    # SpeechBlock requires character_id) - it is folded into narration instead of dropped.
    assert system_turn.blocks[2].character_id is None
    assert system_turn.blocks[2].text == "A stranger scoffs."

    # user_input turns never carry blocks, even if the model supplied one - live simulation user
    # turns are always plain text (see world_simulator.py's commit_user_actions).
    assert user_turn.blocks == []


async def test_extract_skips_model_call_for_empty_opening():
    extractor = OpeningTurnExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    result = await extractor.extract(
        PreprocessedCard(name="Card"), CharacterExtraction(), language=SupportedLanguage.ENGLISH,
    )

    assert result.turns == []
    extractor._prepare_global_llm_service.assert_not_awaited()
