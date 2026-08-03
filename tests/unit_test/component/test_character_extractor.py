from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.character_extractor import CharacterExtractionResult, \
    CharacterExtractor, _merge_similar_names
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def test_merge_similar_names_merges_substrings_into_the_longer_form():
    canonical = _merge_similar_names({"陌白·福尔摩斯", "陌白"})

    assert canonical["陌白"] == "陌白·福尔摩斯"
    assert canonical["陌白·福尔摩斯"] == "陌白·福尔摩斯"


def test_merge_similar_names_leaves_unrelated_names_distinct():
    canonical = _merge_similar_names({"Kiki Mora", "Clara Whitlock"})

    assert canonical["Kiki Mora"] == "Kiki Mora"
    assert canonical["Clara Whitlock"] == "Clara Whitlock"


def test_merge_similar_names_does_not_merge_names_shorter_than_minimum():
    # Single characters ("凛") must never absorb an unrelated name just by substring luck.
    canonical = _merge_similar_names({"凛", "神代凛霜"})

    assert canonical["凛"] == "凛"
    assert canonical["神代凛霜"] == "神代凛霜"


def make_card() -> PreprocessedCard:
    return PreprocessedCard(
        name="陌白",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="陌白bio", content="陌白 is a detective."),
            PreprocessedLorebookEntry(source_id="2", name="林汐月bio", content="林汐月 is quiet."),
            PreprocessedLorebookEntry(source_id="3", name="林汐月voice", content="\"Have some tea.\""),
            PreprocessedLorebookEntry(source_id="4", name="secret", content="林汐月 is secretly the killer."),
            PreprocessedLorebookEntry(source_id="5", name="orphan voice", content="\"...\""),
            PreprocessedLorebookEntry(source_id="6", name="history", content="They solved a case together."),
        ],
    )


def make_classification() -> LorebookClassification:
    return LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="陌白"),
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="林汐月"),
        ClassifiedItem(item_id="entry:3", buckets=[LorebookItemBucket.CHARACTER_VOICE], target_name="林汐月"),
        ClassifiedItem(item_id="entry:4", buckets=[LorebookItemBucket.HIDDEN_TRUTH], target_name="林汐月"),
        ClassifiedItem(item_id="entry:5", buckets=[LorebookItemBucket.CHARACTER_VOICE], target_name="陌白·福尔摩斯"),
        ClassifiedItem(item_id="entry:6", buckets=[LorebookItemBucket.HISTORY_EVENT], target_name="陌白"),
    ])


def test_build_clusters_groups_by_canonical_name_and_carries_secrets():
    card = make_card()
    classification = make_classification()

    clusters = CharacterExtractor._build_clusters(card, classification)

    # "陌白" (bio/history) and "陌白·福尔摩斯" (voice) are merged into one cluster, canonicalized to
    # the longer/more complete spelling - the fuller name is preferred as canonical.
    by_name = {cluster.target_name: cluster for cluster in clusters}
    assert set(by_name) == {"陌白·福尔摩斯", "林汐月"}

    lin = by_name["林汐月"]
    assert lin.bio_content == ["林汐月 is quiet."]
    assert lin.voice_content == ["\"Have some tea.\""]
    assert lin.card_secrets == ["林汐月 is secretly the killer."]

    mo = by_name["陌白·福尔摩斯"]
    assert mo.bio_content == ["陌白 is a detective."]
    assert mo.related_history == ["They solved a case together."]
    assert mo.voice_content == ["\"...\""]


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
    # Regression for a real bug found on card 03: entry:20 was a second bio fragment about an
    # already-named character (马库斯·"马克"·科尔特斯) that stage 1 left unnamed. Falling back to
    # card.name fabricated a bogus duplicate character named after the card's own title.
    card = PreprocessedCard(
        name="尸变纪元 v0.5",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="17", name="bio", content="马库斯 is a sewer worker."),
            PreprocessedLorebookEntry(source_id="20", name="bio2", content="He also collects old keys."),
        ],
    )
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:17", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name="马库斯"),
        ClassifiedItem(item_id="entry:20", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name=None),
    ])

    clusters = CharacterExtractor._build_clusters(card, classification)

    assert [cluster.target_name for cluster in clusters] == ["马库斯"]
    assert clusters[0].bio_content == ["马库斯 is a sewer worker."]
    assert clusters[0].source_item_ids == ["entry:17"]


def test_build_clusters_falls_back_to_card_name_when_no_bio_item_is_ever_named():
    card = PreprocessedCard(
        name="Kiki Mora",
        first_message="Hi",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="bio", content="A streamer with a secret."),
        ],
    )
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.CHARACTER_BIO], target_name=None),
    ])

    clusters = CharacterExtractor._build_clusters(card, classification)

    assert [cluster.target_name for cluster in clusters] == ["Kiki Mora"]
    assert clusters[0].bio_content == ["A streamer with a secret."]


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
        do_not_know = ["killer secret"] if target_name == "林汐月" else []
        return CharacterExtractionResult(
            name=target_name,
            age=30,
            gender="unknown",
            appearance="Plain",
            description="A character.",
            public_state="Present",
            private_state="Thinking",
            current_activity="idle",
            do_not_know=do_not_know,
        )

    extractor._prepare_global_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(side_effect=extract_by_name),
    ))

    extraction = await extractor.extract(card, classification, language=SupportedLanguage.ENGLISH)

    by_name = {entry.target_name: entry for entry in extraction.characters}
    assert set(by_name) == {"陌白·福尔摩斯", "林汐月"}
    assert by_name["林汐月"].result.do_not_know == ["killer secret"]
    assert by_name["陌白·福尔摩斯"].result.do_not_know == []
    assert set(by_name["林汐月"].source_item_ids) == {"entry:2", "entry:3"}

    assert by_name["林汐月"].id and by_name["陌白·福尔摩斯"].id
    assert by_name["林汐月"].id != by_name["陌白·福尔摩斯"].id


async def test_extract_returns_empty_without_calling_llm_when_no_clusters():
    card = PreprocessedCard(name="Empty", first_message="Hi")
    extractor = CharacterExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(card, LorebookClassification(items=[]), language=SupportedLanguage.ENGLISH)

    assert extraction.characters == []
    extractor._prepare_global_llm_service.assert_not_awaited()
