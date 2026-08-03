from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.location_extractor import LocationCandidate, \
    LocationExtractor, SynthesizedLocations, _stitch_parents
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def test_stitch_parents_links_by_exact_name_match():
    candidates = [
        (LocationCandidate(name="上海", description="A city.", parent_name=None), "entry:1"),
        (LocationCandidate(name="文景楼", description="A building.", parent_name="上海"), "entry:2"),
    ]

    locations = _stitch_parents(candidates)

    by_name = {location.name: location for location in locations}
    assert by_name["文景楼"].parent_id == by_name["上海"].id
    assert by_name["上海"].parent_id is None


def test_stitch_parents_drops_unmatched_parent_name():
    candidates = [
        (LocationCandidate(name="文景楼", description="A building.", parent_name="Nowhere"), "entry:1"),
    ]

    locations = _stitch_parents(candidates)

    assert locations[0].parent_id is None


def test_stitch_parents_never_self_references():
    candidates = [
        (LocationCandidate(name="上海", description="A city.", parent_name="上海"), "entry:1"),
    ]

    locations = _stitch_parents(candidates)

    assert locations[0].parent_id is None


def make_card(*, scenario: str = "", first_message: str = "", lorebook_entries=None) -> PreprocessedCard:
    return PreprocessedCard(
        name="Card",
        scenario=scenario,
        first_message=first_message,
        lorebook_entries=lorebook_entries or [],
    )


async def test_extract_dispatches_one_call_per_location_item():
    card = make_card(lorebook_entries=[
        PreprocessedLorebookEntry(source_id="1", name="地点/上海", content="Shanghai, a big city."),
        PreprocessedLorebookEntry(source_id="2", name="地点/上海/文景楼", content="A haunted building in Shanghai."),
    ])
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.LOCATION], target_name="上海"),
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.LOCATION], target_name="文景楼"),
    ])
    extractor = LocationExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    def extract_by_content(**kwargs):
        content = kwargs["data"]["content"]
        if "haunted" in content:
            return LocationCandidate(name="文景楼", description="A haunted building.", parent_name="上海")
        return LocationCandidate(name="上海", description="A big city.", parent_name=None)

    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(side_effect=extract_by_content),
    ))

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    by_name = {location.name: location for location in extraction.locations}
    assert set(by_name) == {"上海", "文景楼"}
    assert by_name["文景楼"].parent_id == by_name["上海"].id
    assert by_name["上海"].source_item_ids == ["entry:1"]


async def test_extract_falls_back_to_synthesis_when_no_location_items():
    card = make_card(scenario="A cozy bedroom during a late-night stream.")
    extractor = LocationExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=SynthesizedLocations(locations=[
            LocationCandidate(name="Bedroom", description="A cozy bedroom.", parent_name=None),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert [location.name for location in extraction.locations] == ["Bedroom"]
    assert extraction.locations[0].source_item_ids == ["field:scenario"]


async def test_extract_synthesis_records_both_sources_when_both_are_present():
    card = make_card(scenario="A cozy bedroom.", first_message="Hey chat, welcome back!")
    extractor = LocationExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=SynthesizedLocations(locations=[
            LocationCandidate(name="Bedroom", description="A cozy bedroom.", parent_name=None),
        ])),
    ))

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.locations[0].source_item_ids == ["field:scenario", "field:first_message"]


async def test_extract_returns_empty_without_calling_llm_when_no_signal_at_all():
    card = make_card()
    extractor = LocationExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.locations == []
    extractor._prepare_global_llm_service.assert_not_awaited()
