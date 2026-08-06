from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.sillytavern_converter import (
    CharacterExtraction, CharacterExtractionResult, EquipmentExtraction, ExtractedCharacter,
    ExtractedMemory, ItemExtraction, LocationExtraction, NarrativeExtraction,
    PrivateKnowledgeClaimCandidate, PrivateKnowledgeClaimCandidates, PrivateKnowledgeExtractor,
)
from world_simulation_engine.misc.enums import SupportedLanguage


def character(name, entity_id):
    return ExtractedCharacter(
        id=entity_id, target_name=name, source_item_ids=[],
        result=CharacterExtractionResult(
            name=name, age=30, gender="unknown", appearance="plain", description="A person.",
            public_state="present", private_state="calm", current_activity="idle",
        ),
    )


async def test_extract_accepts_only_positive_claims_with_observer_owned_evidence():
    extractor = PrivateKnowledgeExtractor(database=Mock())
    extractor._prepare_global_prompt = AsyncMock(return_value=[])
    extractor._prepare_global_llm_service = AsyncMock(return_value=Mock(
        invoke_structured_with_repair=AsyncMock(return_value=PrivateKnowledgeClaimCandidates(claims=[
            PrivateKnowledgeClaimCandidate(
                subject_id="char-bob", category="history", statement="Bob survived the fire.",
                stance="believes", confidence=.9, supporting_memory_ids=["memory-alice"],
            ),
            PrivateKnowledgeClaimCandidate(
                subject_id="char-bob", category="state", statement="Bob has the key.",
                stance="suspects", confidence=.5, supporting_memory_ids=["memory-bob-only"],
            ),
            PrivateKnowledgeClaimCandidate(
                subject_id="char-alice", category="state", statement="I am safe.",
                stance="believes", confidence=1, supporting_memory_ids=["memory-alice"],
            ),
        ])),
    ))
    characters = CharacterExtraction(characters=[
        character("Alice", "char-alice"), character("Bob", "char-bob"),
    ])
    narrative = NarrativeExtraction(memories=[
        ExtractedMemory(
            id="memory-alice", event_id="event-1", summary="Alice saw Bob escape.",
            character_ids=["char-alice"],
        ),
        ExtractedMemory(
            id="memory-bob-only", event_id="event-2", summary="Bob found a key.",
            character_ids=["char-bob"],
        ),
    ])

    result = await extractor.extract(
        characters, LocationExtraction(), ItemExtraction(), EquipmentExtraction(), narrative,
        language=SupportedLanguage.ENGLISH,
    )

    alice_claims = [claim for claim in result.claims if claim.observer_character_id == "char-alice"]
    assert len(alice_claims) == 1
    assert alice_claims[0].subject_id == "char-bob"
    assert alice_claims[0].supporting_memory_ids == ["memory-alice"]


async def test_extract_makes_no_call_and_no_negative_record_without_positive_memory():
    extractor = PrivateKnowledgeExtractor(database=Mock())
    extractor._prepare_global_llm_service = AsyncMock()

    result = await extractor.extract(
        CharacterExtraction(characters=[character("Alice", "char-alice")]),
        LocationExtraction(), ItemExtraction(), EquipmentExtraction(), NarrativeExtraction(),
        language=SupportedLanguage.ENGLISH,
    )

    assert result.claims == []
    extractor._prepare_global_llm_service.assert_not_awaited()
