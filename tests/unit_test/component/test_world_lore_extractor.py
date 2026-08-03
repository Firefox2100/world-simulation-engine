from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.component.sillytavern_converter.world_lore_extractor import WorldLoreExtractionResult, \
    WorldLoreExtractor
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def make_card() -> PreprocessedCard:
    return PreprocessedCard(
        name="Card",
        description="A cursed village bound by an old pact.",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="cult", content="A demon cult operates in secret."),
            PreprocessedLorebookEntry(source_id="2", name="bio", content="Not lore, a character bio."),
        ],
    )


async def test_extract_consolidates_all_world_lore_items_in_one_call():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="field:description", buckets=[LorebookItemBucket.WORLD_LORE]),
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.WORLD_LORE]),
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="Someone"),
    ])
    extractor = WorldLoreExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    llm_service = Mock(invoke_structured_with_repair=AsyncMock(
        return_value=WorldLoreExtractionResult(description="A cursed village troubled by a secret demon cult."),
    ))
    extractor._prepare_global_llm_service = AsyncMock(return_value=llm_service)

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert extraction.description == "A cursed village troubled by a secret demon cult."
    assert set(extraction.source_item_ids) == {"field:description", "entry:1"}
    llm_service.invoke_structured_with_repair.assert_awaited_once()
    call_data = llm_service.invoke_structured_with_repair.await_args.kwargs["data"]
    assert set(call_data["lore_items"]) == {
        "A cursed village bound by an old pact.", "A demon cult operates in secret.",
    }


async def test_extract_returns_empty_without_calling_llm_when_no_world_lore_items():
    card = make_card()
    extractor = WorldLoreExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(
        card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH,
    )

    assert extraction.description is None
    assert extraction.source_item_ids == []
    extractor._prepare_global_llm_service.assert_not_awaited()
