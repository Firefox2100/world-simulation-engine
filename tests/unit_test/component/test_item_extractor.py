from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.item_extractor import \
    ContainerFieldCandidate, ItemCandidates, ItemExtractor, ItemFieldCandidate
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def make_card(*, lorebook_entries=None) -> PreprocessedCard:
    return PreprocessedCard(name="Card", lorebook_entries=lorebook_entries or [])


async def test_extract_dispatches_one_call_per_item_bucket_entry():
    card = make_card(lorebook_entries=[
        PreprocessedLorebookEntry(source_id="1", name="随身物品", content="示例角色总是随身携带一把生锈的短刀。"),
    ])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.ITEM]),
    ])
    extractor = ItemExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=ItemCandidates(items=[
            ItemFieldCandidate(
                name="生锈的短刀", description="一把老旧生锈的短刀。", quality="生锈",
                holder_hint="示例角色",
            ),
        ])),
    ))

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert len(extraction.items) == 1
    item = extraction.items[0]
    assert item.name == "生锈的短刀"
    assert item.holder_hint == "示例角色"
    assert item.quantity == 1
    assert item.source_item_ids == ["entry:1"]
    prompt_call = extractor._prepare_global_prompt.await_args
    assert prompt_call.kwargs["prompt_name"] == "st_item_extractor"


async def test_extract_separates_container_and_preserves_its_relationship_hints():
    card = make_card(lorebook_entries=[PreprocessedLorebookEntry(
        source_id="1", name="Chest", content="Alice's locked chest is in the Vault.",
    )])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.ITEM]),
    ])
    extractor = ItemExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=ItemCandidates(containers=[
            ContainerFieldCandidate(
                name="Chest", description="A locked chest.", state="locked",
                owner_hint="Alice", location_hint="Vault", position="against the wall",
                unlocking_item_names=["Brass key"],
            ),
        ])),
    ))

    result = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert result.items == []
    assert result.containers[0].owner_hint == "Alice"
    assert result.containers[0].state == "locked"


async def test_extract_ignores_lorebook_entries_not_classified_as_item():
    card = make_card(lorebook_entries=[
        PreprocessedLorebookEntry(source_id="1", name="Bio", content="Example is a fictional resident."),
    ])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_BIO]),
    ])
    extractor = ItemExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert extraction.items == []
    extractor._prepare_global_llm_service.assert_not_awaited()


async def test_extract_returns_empty_without_calling_llm_when_no_item_bucket_entries():
    card = make_card()
    extractor = ItemExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.items == []
    extractor._prepare_global_llm_service.assert_not_awaited()
