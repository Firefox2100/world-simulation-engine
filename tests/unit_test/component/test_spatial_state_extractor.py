from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import (
    CharacterExtraction, CharacterExtractionResult, EquipmentExtraction, ExtractedCharacter,
    ExtractedItem, ExtractedLocation, ItemExtraction, LocationExtraction, PreprocessedCard,
    SpatialEntityType, SpatialPlacementCandidate, SpatialPlacementCandidates, SpatialStateExtractor,
)
from world_simulation_engine.misc.enums import SupportedLanguage


def make_character():
    return ExtractedCharacter(
        id="char-a", target_name="Alice", source_item_ids=[],
        result=CharacterExtractionResult(
            name="Alice", age=30, gender="unknown", appearance="plain", description="A person.",
            public_state="inside", private_state="calm", current_activity="reading",
        ),
    )


async def test_extract_resolves_exact_entities_and_locations_and_drops_hallucinations():
    extractor = SpatialStateExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=SpatialPlacementCandidates(placements=[
            SpatialPlacementCandidate(
                entity_type=SpatialEntityType.CHARACTER, entity_name="Alice",
                location_name="Library", position="beside the window",
            ),
            SpatialPlacementCandidate(
                entity_type=SpatialEntityType.ITEM, entity_name="Invented",
                location_name="Library",
            ),
            SpatialPlacementCandidate(
                entity_type=SpatialEntityType.ITEM, entity_name="Book",
                location_name="Invented place",
            ),
        ])),
    ))

    result = await extractor.extract(
        PreprocessedCard(name="Card", scenario="A library", first_message="Alice reads."),
        CharacterExtraction(characters=[make_character()]),
        LocationExtraction(locations=[ExtractedLocation(
            id="loc-library", name="Library", description="Bookshelves.",
        )]),
        ItemExtraction(items=[ExtractedItem(
            name="Book", description="A book.", unique=False, quantity=1,
        )]),
        EquipmentExtraction(), language=SupportedLanguage.ENGLISH,
    )

    assert len(result.placements) == 1
    assert result.placements[0].entity_name == "Alice"
    assert result.placements[0].location_id == "loc-library"
    assert result.placements[0].position == "beside the window"


async def test_extract_skips_model_call_when_there_are_no_locations():
    extractor = SpatialStateExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    result = await extractor.extract(
        PreprocessedCard(name="Card"), CharacterExtraction(characters=[make_character()]),
        LocationExtraction(), ItemExtraction(), EquipmentExtraction(),
        language=SupportedLanguage.ENGLISH,
    )

    assert result.placements == []
    extractor._prepare_global_llm_service.assert_not_awaited()
