from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import (
    CharacterExtraction, CharacterExtractionResult, ExtractedCharacter, ExtractedOpeningTurn,
    OpeningEventCandidate, OpeningMemoryCandidate, OpeningNarrativeExtractor, OpeningTurnExtraction,
)
from world_simulation_engine.misc.enums import SupportedLanguage


def character(name, entity_id):
    return ExtractedCharacter(
        id=entity_id, target_name=name, source_item_ids=[],
        result=CharacterExtractionResult(
            name=name, age=30, gender="unknown", appearance="plain", description="A person.",
            public_state="present", private_state="uncertain", current_activity="thinking",
        ),
    )


async def test_extract_encodes_important_internal_change_as_event_outcome_and_memory():
    extractor = OpeningNarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=OpeningEventCandidate(
            has_event=True,
            name="Swallowed by the fish",
            summary="A great fish swallowed Jacob.",
            outcome="Jacob reconsidered his refusal and decided to accept the mission.",
            involved_names=["Jacob"],
            memories=[OpeningMemoryCandidate(
                observer_name="Jacob",
                summary="Being swallowed forced Jacob to reconsider and accept the mission.",
                keywords=["fish", "decision", "mission"],
            )],
        )),
    ))

    result = await extractor.extract(
        OpeningTurnExtraction(turns=[ExtractedOpeningTurn(
            type="system_response", content="A fish swallowed Jacob, and he changed his mind.",
        )]),
        CharacterExtraction(characters=[character("Jacob", "char-jacob")]),
        language=SupportedLanguage.ENGLISH,
    )

    assert len(result.events) == 1
    event = result.events[0]
    assert event.opening_turn_index == 0
    assert event.outcome == "Jacob reconsidered his refusal and decided to accept the mission."
    assert result.memories[0].event_id == event.id
    assert result.memories[0].character_ids == ["char-jacob"]
    assert "reconsider" in result.memories[0].summary


async def test_extract_does_not_create_memory_for_unknown_observer():
    extractor = OpeningNarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=OpeningEventCandidate(
            has_event=True, name="A noise", summary="A noise sounded.",
            involved_names=["Jacob"], memories=[OpeningMemoryCandidate(
                observer_name="Invented", summary="Invented heard it.",
            )],
        )),
    ))

    result = await extractor.extract(
        OpeningTurnExtraction(turns=[ExtractedOpeningTurn(
            type="system_response", content="A noise sounded.",
        )]),
        CharacterExtraction(characters=[character("Jacob", "char-jacob")]),
        language=SupportedLanguage.ENGLISH,
    )

    assert len(result.events) == 1
    assert result.memories == []
