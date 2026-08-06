from unittest.mock import AsyncMock, Mock

from world_simulation_engine.service.world_import_service import WorldImportService


async def test_import_subjective_claim_remaps_observer_subject_and_positive_memory_evidence():
    database = Mock()
    database.subjective_entity_claim.create_world_claim = AsyncMock(side_effect=lambda claim: claim)
    service = WorldImportService(database, Mock())
    row = {
        "id": "claim-old",
        "observer_character_id": "alice-old",
        "subject": {"type": "character", "id": "bob-old", "name": "Bob"},
        "category": "history",
        "statement": "Bob survived the fire.",
        "normalized_statement": "bob survived the fire.",
        "stance": "believes",
        "confidence": .9,
        "supporting_memory_ids": ["memory-old"],
        "contradicting_memory_ids": [],
        "first_observed_at": "2026-01-01T00:00:00Z",
        "last_updated_at": "2026-01-01T00:00:00Z",
        "version": 1,
        "active": True,
    }

    await service._import_subjective_claims(
        "world-new", [row],
        {"alice-old": "alice-new", "bob-old": "bob-new"},
        {"memory-old": "memory-new"},
    )

    claim = database.subjective_entity_claim.create_world_claim.await_args.args[0]
    assert claim.world_id == "world-new"
    assert claim.simulation_id is None
    assert claim.observer_character_id == "alice-new"
    assert claim.subject.id == "bob-new"
    assert claim.supporting_memory_ids == ["memory-new"]


async def test_import_skips_claim_without_resolvable_positive_evidence():
    database = Mock()
    database.subjective_entity_claim.create_world_claim = AsyncMock()
    service = WorldImportService(database, Mock())

    await service._import_subjective_claims(
        "world-new",
        [{
            "observer_character_id": "alice-old",
            "subject": {"type": "character", "id": "bob-old"},
            "supporting_memory_ids": ["unknown-memory"],
        }],
        {"alice-old": "alice-new", "bob-old": "bob-new"},
        {},
    )

    database.subjective_entity_claim.create_world_claim.assert_not_awaited()
