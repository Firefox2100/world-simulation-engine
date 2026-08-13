from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.character_extractor import CharacterExtractionResult, \
    CharacterExtractor
from world_simulation_engine.component.sillytavern_converter.character_name_pool import merge_similar_names
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def test_merge_similar_names_merges_substrings_into_the_longer_form():
    canonical = merge_similar_names({"Casey Morgan", "Casey"})

    assert canonical["Casey"] == "Casey Morgan"
    assert canonical["Casey Morgan"] == "Casey Morgan"


def test_merge_similar_names_leaves_unrelated_names_distinct():
    canonical = merge_similar_names({"Example Character", "Clara Whitlock"})

    assert canonical["Example Character"] == "Example Character"
    assert canonical["Clara Whitlock"] == "Clara Whitlock"


def test_merge_similar_names_does_not_merge_names_shorter_than_minimum():
    # Single characters ("A") must never absorb an unrelated name just by substring luck.
    canonical = merge_similar_names({"A", "Ada"})

    assert canonical["A"] == "A"
    assert canonical["Ada"] == "Ada"


def make_card() -> PreprocessedCard:
    return PreprocessedCard(
        name="Casey",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="Caseybio", content="Casey is a researcher."),
            PreprocessedLorebookEntry(source_id="2", name="Jordan Leebio", content="Jordan Lee is quiet."),
            PreprocessedLorebookEntry(source_id="3", name="Jordan Leevoice", content="\"Have some tea.\""),
            PreprocessedLorebookEntry(source_id="4", name="secret", content="Jordan Lee privately holds the archive key."),
            PreprocessedLorebookEntry(source_id="5", name="orphan voice", content="\"...\""),
            PreprocessedLorebookEntry(source_id="6", name="history", content="They solved a case together."),
        ],
    )


def make_classification() -> LorebookClassification:
    return LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="Casey"),
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="Jordan Lee"),
        ClassifiedItem(item_id="entry:3", buckets=[LorebookItemBucket.CHARACTER_VOICE], target_name="Jordan Lee"),
        ClassifiedItem(item_id="entry:4", buckets=[LorebookItemBucket.HIDDEN_TRUTH], target_name="Jordan Lee"),
        ClassifiedItem(item_id="entry:5", buckets=[LorebookItemBucket.CHARACTER_VOICE], target_name="Casey Morgan"),
        ClassifiedItem(item_id="entry:6", buckets=[LorebookItemBucket.HISTORY_EVENT], target_name="Casey"),
    ])


def test_build_clusters_groups_by_canonical_name_without_encoding_unknowns():
    card = make_card()
    classification = make_classification()

    clusters = CharacterExtractor._build_clusters(card, classification)

    # "Casey" (bio/history) and "Casey Morgan" (voice) are merged into one cluster, canonicalized to
    # the longer/more complete spelling - the fuller name is preferred as canonical.
    by_name = {cluster.target_name: cluster for cluster in clusters}
    assert set(by_name) == {"Casey Morgan", "Jordan Lee"}

    jordan = by_name["Jordan Lee"]
    assert jordan.bio_content == ["Jordan Lee is quiet."]
    assert jordan.voice_content == ["\"Have some tea.\""]

    casey = by_name["Casey Morgan"]
    assert casey.bio_content == ["Casey is a researcher."]
    assert casey.related_history == ["They solved a case together."]
    assert casey.voice_content == ["\"...\""]


def test_build_clusters_skips_voice_only_content_with_no_bio_anywhere():
    card = PreprocessedCard(
        name="Nobody",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="voice", content="Orphan line."),
        ],
    )
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_VOICE], target_name="Ghost"),
    ])

    clusters = CharacterExtractor._build_clusters(card, classification)

    assert clusters == []


def test_build_clusters_empty_classification_yields_no_clusters():
    card = make_card()

    clusters = CharacterExtractor._build_clusters(card, LorebookClassification(items=[]))

    assert clusters == []


def test_build_clusters_drops_unnamed_bio_item_when_other_bio_items_are_named():
    card = PreprocessedCard(
        name="Example World",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="17", name="bio", content="Taylor is a caretaker."),
            PreprocessedLorebookEntry(source_id="20", name="bio2", content="He also collects old keys."),
        ],
    )
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:17", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="Taylor"),
        ClassifiedItem(item_id="entry:20", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name=None),
    ])

    clusters = CharacterExtractor._build_clusters(card, classification)

    assert [cluster.target_name for cluster in clusters] == ["Taylor"]
    assert clusters[0].bio_content == ["Taylor is a caretaker."]
    assert clusters[0].source_item_ids == ["entry:17"]


def test_build_clusters_falls_back_to_card_name_when_no_bio_item_is_ever_named():
    card = PreprocessedCard(
        name="Example Character",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="bio", content="A fictional resident with a secret."),
        ],
    )
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name=None),
    ])

    clusters = CharacterExtractor._build_clusters(card, classification)

    assert [cluster.target_name for cluster in clusters] == ["Example Character"]
    assert clusters[0].bio_content == ["A fictional resident with a secret."]


def test_build_clusters_mints_a_stable_id_per_cluster():
    card = make_card()
    classification = make_classification()

    clusters = CharacterExtractor._build_clusters(card, classification)

    ids = [cluster.id for cluster in clusters]
    assert len(ids) == len(set(ids))
    assert all(isinstance(cluster_id, str) and cluster_id for cluster_id in ids)


async def test_extract_dispatches_one_call_per_cluster():
    card = make_card()
    classification = make_classification()
    extractor = CharacterExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    def extract_by_name(**kwargs):
        assert "id" not in kwargs["data"]  # provisional id is for cross-referencing only, not LLM input
        target_name = kwargs["data"]["target_name"]
        return CharacterExtractionResult(
            name=target_name,
            age=30,
            gender="unknown",
            appearance="Plain",
            description="A character.",
            public_state="Present",
            private_state="Thinking",
            current_activity="idle",
        )

    extractor._prepare_global_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(side_effect=extract_by_name),
    ))

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    by_name = {entry.target_name: entry for entry in extraction.characters}
    assert set(by_name) == {"Casey Morgan", "Jordan Lee"}
    assert set(by_name["Jordan Lee"].source_item_ids) == {"entry:2", "entry:3"}

    assert by_name["Jordan Lee"].id and by_name["Casey Morgan"].id
    assert by_name["Jordan Lee"].id != by_name["Casey Morgan"].id


async def test_extract_returns_empty_without_calling_llm_when_no_clusters():
    card = PreprocessedCard(name="Empty", first_message="Hi")
    extractor = CharacterExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.characters == []
    extractor._prepare_global_llm_service.assert_not_awaited()
