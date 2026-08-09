from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import ExtractedCharacter, CharacterExtraction, \
    CharacterExtractionResult, PreprocessedCard, PreprocessedLorebookEntry
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import ClassifiedItem, \
    LorebookClassification
from world_simulation_engine.component.sillytavern_converter.narrative_extractor import \
    HistoricalMemoryCandidate, HistoryEventCandidate, NarrativeExtractor, RelationshipCandidate
from world_simulation_engine.misc.enums import LorebookItemBucket, SupportedLanguage


def make_character(name: str, char_id: str) -> ExtractedCharacter:
    return ExtractedCharacter(
        id=char_id,
        target_name=name,
        source_item_ids=[],
        result=CharacterExtractionResult(
            name=name, age=30, gender="unknown", appearance="Plain", description="A character.",
            public_state="Present", private_state="Thinking", current_activity="idle",
        ),
    )


def make_card(*, history_content="They completed a project together.", relationship_content="Longtime colleagues.") -> PreprocessedCard:
    return PreprocessedCard(
        name="Card",
        lorebook_entries=[
            PreprocessedLorebookEntry(source_id="1", name="history", content=history_content),
            PreprocessedLorebookEntry(source_id="2", name="relationship", content=relationship_content),
        ],
    )


def make_classification() -> LorebookClassification:
    return LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.HISTORY_EVENT]),
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.RELATIONSHIP]),
    ])


async def test_extract_resolves_names_to_ids_and_encodes_only_positive_knowing_names():
    card = make_card()
    classification = make_classification()
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"),
        make_character("Bob", "id-bob"),
    ])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])

    def dispatch(**kwargs):
        output_model = kwargs["output_model"]
        if output_model is HistoryEventCandidate:
            return HistoryEventCandidate(
                event_name="The Project", event_summary="They collaborated successfully.",
                involved_names=["Alice", "Bob"], memory_summary="We completed the project together.",
                memory_keywords=["project"], knowing_names=["Bob"],
            )
        return RelationshipCandidate(
            source_name="Alice", target_name="Bob", label="colleagues", description="Known for years.",
        )

    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(side_effect=dispatch),
    ))

    extraction = await extractor.extract(card, classification, characters, language=SupportedLanguage.ENGLISH)

    assert len(extraction.events) == 1
    event = extraction.events[0]
    assert set(event.involved_character_ids) == {"id-alice", "id-bob"}
    assert event.source_item_ids == ["entry:1"]

    assert len(extraction.memories) == 1
    memory = extraction.memories[0]
    assert memory.event_id == event.id
    assert memory.character_ids == ["id-bob"]  # Alice excluded via knowing_names

    assert len(extraction.relationships) == 1
    relationship = extraction.relationships[0]
    assert relationship.source_character_id == "id-alice"
    assert relationship.target_character_id == "id-bob"
    assert relationship.source_item_ids == ["entry:2"]


async def test_extract_drops_event_with_no_resolvable_participant():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.HISTORY_EVENT]),
    ])
    characters = CharacterExtraction(characters=[make_character("Alice", "id-alice")])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=HistoryEventCandidate(
            event_name="Unrelated", event_summary="Something happened.",
            involved_names=["Someone Else"], memory_summary="N/A", knowing_names=[],
        )),
    ))

    extraction = await extractor.extract(card, classification, characters, language=SupportedLanguage.ENGLISH)

    assert extraction.events == []
    assert extraction.memories == []


async def test_extract_does_not_create_memory_when_knowing_names_empty():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.HISTORY_EVENT]),
    ])
    characters = CharacterExtraction(characters=[make_character("Alice", "id-alice")])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=HistoryEventCandidate(
            event_name="Solo event", event_summary="Alice did something.",
            involved_names=["Alice"], memory_summary="I did something.", knowing_names=[],
        )),
    ))

    extraction = await extractor.extract(card, classification, characters, language=SupportedLanguage.ENGLISH)

    assert extraction.memories == []


async def test_extract_creates_separate_perspective_memories_from_one_event():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:1", buckets=[LorebookItemBucket.HISTORY_EVENT]),
    ])
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"), make_character("Bob", "id-bob"),
    ])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=HistoryEventCandidate(
            event_name="Argument", event_summary="Alice and Bob argued.",
            involved_names=["Alice", "Bob"], memories=[
                HistoricalMemoryCandidate(
                    observer_name="Alice", summary="Bob refused to listen.", keywords=["argument"],
                ),
                HistoricalMemoryCandidate(
                    observer_name="Bob", summary="Alice accused me unfairly.", keywords=["argument"],
                ),
            ],
        )),
    ))

    result = await extractor.extract(card, classification, characters, language=SupportedLanguage.ENGLISH)

    assert len(result.memories) == 2
    assert {memory.character_ids[0] for memory in result.memories} == {"id-alice", "id-bob"}


async def test_extract_drops_relationship_with_unresolved_or_self_reference():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.RELATIONSHIP]),
    ])
    characters = CharacterExtraction(characters=[make_character("Alice", "id-alice")])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=RelationshipCandidate(
            source_name="Alice", target_name="Alice", label="self", description="n/a",
        )),
    ))

    extraction = await extractor.extract(card, classification, characters, language=SupportedLanguage.ENGLISH)

    assert extraction.relationships == []


async def test_extract_resolves_relationship_with_a_partial_name_from_the_model():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.RELATIONSHIP]),
    ])
    characters = CharacterExtraction(characters=[
        make_character("Riley Bennett", "id-riley"),
        make_character("Casey Morgan", "id-casey"),
    ])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=RelationshipCandidate(
            source_name="Riley", target_name="Casey Morgan", label="colleagues", description="Former colleagues.",
        )),
    ))

    extraction = await extractor.extract(card, classification, characters, language=SupportedLanguage.ENGLISH)

    assert len(extraction.relationships) == 1
    assert extraction.relationships[0].source_character_id == "id-riley"
    assert extraction.relationships[0].target_character_id == "id-casey"


async def test_extract_preserves_private_relationship_perspective():
    card = make_card()
    classification = LorebookClassification(items=[
        ClassifiedItem(item_id="entry:2", buckets=[LorebookItemBucket.RELATIONSHIP]),
    ])
    characters = CharacterExtraction(characters=[
        make_character("Alice", "id-alice"), make_character("Bob", "id-bob"),
    ])
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=RelationshipCandidate(
            source_name="Alice", target_name="Bob", label="secret admiration",
            description="Alice privately admires Bob.", visibility="private",
            perspective_name="Alice", confidence=.8,
        )),
    ))

    extraction = await extractor.extract(
        card, classification, characters, language=SupportedLanguage.ENGLISH,
    )

    relationship = extraction.relationships[0]
    assert relationship.visibility == "private"
    assert relationship.perspective_character_id == "id-alice"
    assert relationship.confidence == .8


async def test_extract_returns_empty_without_calling_llm_when_no_relevant_items():
    card = make_card()
    extractor = NarrativeExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    extraction = await extractor.extract(
        card, LorebookClassification(items=[]), CharacterExtraction(characters=[]),
        language=SupportedLanguage.ENGLISH,
    )

    assert extraction.events == [] and extraction.memories == [] and extraction.relationships == []
    extractor._prepare_global_llm_service.assert_not_awaited()
