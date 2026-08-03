from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import CharacterExtraction, CharacterExtractionResult, \
    ExtractedCharacter
from world_simulation_engine.component.sillytavern_converter.intent_extractor import IntentCandidate, \
    IntentCandidates, IntentExtractor
from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType, SupportedLanguage


def make_character(name: str, char_id: str) -> ExtractedCharacter:
    return ExtractedCharacter(
        id=char_id,
        target_name=name,
        source_item_ids=[],
        result=CharacterExtractionResult(
            name=name, age=30, gender="unknown", appearance="Plain",
            description="An investigator with an unsolved case.",
            public_state="Present", private_state="Obsessed with the case", current_activity="idle",
        ),
    )


async def test_extract_dispatches_one_call_per_character_and_tags_intents():
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"),
        make_character("Bob", "id-bob"),
    ])
    extractor = IntentExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    def dispatch(**kwargs):
        name = kwargs["data"]["name"]
        if name == "Alice":
            return IntentCandidates(intents=[
                IntentCandidate(
                    name="Solve the case", type=IntentType.QUEST, description="Find the truth.",
                    priority=0.9, urgency=0.5, status=IntentStatus.ACTIVE, horizon=IntentHorizon.LONG,
                ),
            ])
        return IntentCandidates(intents=[])

    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(side_effect=dispatch),
    ))

    extraction = await extractor.extract(characters, language=SupportedLanguage.ENGLISH)

    assert len(extraction.intents) == 1
    intent = extraction.intents[0]
    assert intent.character_id == "id-alice"
    assert intent.name == "Solve the case"
    assert intent.type == IntentType.QUEST


async def test_extract_returns_empty_without_calling_llm_when_no_characters():
    extractor = IntentExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(CharacterExtraction(characters=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.intents == []
    extractor._prepare_global_llm_service.assert_not_awaited()
