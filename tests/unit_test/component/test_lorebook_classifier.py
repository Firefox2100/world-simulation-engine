from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassifier, \
    LorebookItemClassification
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def make_card() -> PreprocessedCard:
    return PreprocessedCard(
        name="Kiki",
        description="Kiki is a streamer.",
        personality="",
        scenario="",
        first_message="Hi!",
        system_prompt="",
        post_history_instructions="",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="Stage 1", keys=["seal"], content="The seal breaks."),
            PreprocessedLorebookEntry(source_id="2", name=None, keys=[], content="Empty-named entry."),
        ],
    )


async def test_classify_dispatches_one_call_per_item_and_tags_results():
    card = make_card()
    database = Mock()
    classifier = LorebookClassifier(database=database)
    classifier._prepare_global_prompt = AsyncMock(return_value=[])

    def classify_by_content(**kwargs):
        content = kwargs["data"]["content"]
        if "streamer" in content:
            return LorebookItemClassification(buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="Kiki")
        if "seal" in content or "breaks" in content:
            return LorebookItemClassification(buckets=[LorebookItemBucket.HISTORY_EVENT])
        return LorebookItemClassification(buckets=[LorebookItemBucket.IRRELEVANT])

    classifier._prepare_global_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(side_effect=classify_by_content),
    ))

    result = await classifier.classify(card, language=SupportedLanguage.ENGLISH)

    by_id = {item.item_id: item for item in result.items}
    assert len(by_id) == 3
    assert by_id["field:description"].buckets == [LorebookItemBucket.CHARACTER_BIO]
    assert by_id["field:description"].target_name == "Kiki"
    assert by_id["entry:1"].buckets == [LorebookItemBucket.HISTORY_EVENT]
    assert by_id["entry:2"].buckets == [LorebookItemBucket.IRRELEVANT]
    assert result.by_bucket(LorebookItemBucket.HISTORY_EVENT) == [by_id["entry:1"]]


async def test_classify_supports_multiple_buckets_on_one_item():
    # Real content routinely mixes categories in one entry (confirmed on card 03: every one of 17
    # characters' entries mixed bio/history/relationship content, invisible to NarrativeExtractor
    # under single-label classification) - by_bucket must find such an item under every one of its
    # labels, not just its first.
    card = make_card()
    classifier = LorebookClassifier(database=Mock())
    classifier._prepare_global_prompt = AsyncMock(return_value=[])
    classifier._prepare_global_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(return_value=LorebookItemClassification(
            buckets=[LorebookItemBucket.CHARACTER_BIO, LorebookItemBucket.HISTORY_EVENT],
            target_name="Kiki",
        )),
    ))

    result = await classifier.classify(card, language=SupportedLanguage.ENGLISH)

    for item in result.items:
        assert item.buckets == [LorebookItemBucket.CHARACTER_BIO, LorebookItemBucket.HISTORY_EVENT]
    assert len(result.by_bucket(LorebookItemBucket.CHARACTER_BIO)) == len(result.items)
    assert result.by_bucket(LorebookItemBucket.CHARACTER_BIO) == result.by_bucket(LorebookItemBucket.HISTORY_EVENT)


async def test_classify_returns_empty_result_without_calling_llm_for_empty_card():
    card = PreprocessedCard(name="Empty", first_message="Hi")
    classifier = LorebookClassifier(database=Mock())
    classifier._prepare_global_llm_service = AsyncMock()

    result = await classifier.classify(card, language=SupportedLanguage.ENGLISH)

    assert result.items == []
    classifier._prepare_global_llm_service.assert_not_awaited()
