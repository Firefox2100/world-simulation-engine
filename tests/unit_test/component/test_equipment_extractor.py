from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.equipment_extractor import EquipmentCandidates, \
    EquipmentExtractor, EquipmentFieldCandidate
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def make_card(*, lorebook_entries=None, first_message="") -> PreprocessedCard:
    return PreprocessedCard(name="Card", lorebook_entries=lorebook_entries or [], first_message=first_message)


async def test_extract_dispatches_one_call_per_item_bucket_entry():
    card = make_card(lorebook_entries=[
        PreprocessedLorebookEntry(source_id="1", name="随身物品", content="小雨总是穿着一件磨损的旅行斗篷。"),
    ])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.ITEM]),
    ])
    extractor = EquipmentExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=EquipmentCandidates(equipment=[
            EquipmentFieldCandidate(
                name="磨损的旅行斗篷", description="一件带兜帽的羊毛斗篷。", quality="磨损",
                holder_hint="小雨", slot="外套",
            ),
        ])),
    ))

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert len(extraction.equipment) == 1
    equipment = extraction.equipment[0]
    assert equipment.name == "磨损的旅行斗篷"
    assert equipment.holder_hint == "小雨"
    assert equipment.slot == "外套"
    assert equipment.source_item_ids == ["entry:1"]
    prompt_call = extractor._prepare_global_prompt.await_args
    assert prompt_call.kwargs["prompt_name"] == "st_equipment_extractor"


async def test_extract_ignores_lorebook_entries_not_classified_as_item():
    card = make_card(lorebook_entries=[
        PreprocessedLorebookEntry(source_id="1", name="Bio", content="Alex is a streamer."),
    ])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_BIO]),
    ])
    extractor = EquipmentExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    assert extraction.equipment == []
    extractor._prepare_global_llm_service.assert_not_awaited()


async def test_extract_returns_empty_without_calling_llm_when_no_signal():
    card = make_card()
    extractor = EquipmentExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.equipment == []
    extractor._prepare_global_llm_service.assert_not_awaited()


async def test_extract_dispatches_a_call_for_a_first_message_initial_value_block():
    card = make_card(
        first_message="<UpdateVariable>\n<initvar>\n小雨:\n  着装:\n    上装: 白衬衫\n</initvar>\n</UpdateVariable>",
    )
    extractor = EquipmentExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=EquipmentCandidates(equipment=[
            EquipmentFieldCandidate(
                name="白衬衫", description="A white shirt.", holder_hint="小雨", slot="上装",
            ),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert len(extraction.equipment) == 1
    equipment = extraction.equipment[0]
    assert equipment.holder_hint == "小雨"
    assert equipment.slot == "上装"
    assert equipment.source_item_ids == ["first_message"]
    prompt_call = extractor._prepare_global_prompt.await_args
    assert prompt_call.kwargs["prompt_name"] == "st_equipment_initial_value_extractor"


async def test_extract_returns_empty_without_calling_llm_when_first_message_has_no_marker():
    card = make_card(first_message="He walked into the room wearing his favorite jacket.")
    extractor = EquipmentExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.equipment == []
    extractor._prepare_global_llm_service.assert_not_awaited()
