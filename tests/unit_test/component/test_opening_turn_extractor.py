from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import (
    CharacterExtraction, CharacterExtractionResult, ExtractedCharacter, OpeningTurnCandidate,
    OpeningTurnCandidates, OpeningTurnExtractor, PreprocessedCard,
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


async def test_extract_skips_model_call_for_empty_opening():
    extractor = OpeningTurnExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    result = await extractor.extract(
        PreprocessedCard(name="Card"), CharacterExtraction(), language=SupportedLanguage.ENGLISH,
    )

    assert result.turns == []
    extractor._prepare_global_llm_service.assert_not_awaited()
