from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from world_simulation_engine.component.simulator.subjective_model_updater import (
    SubjectiveModelUpdateContext, SubjectiveModelUpdater,
)
from world_simulation_engine.model import (
    MemoryAtom, ProposedSubjectiveClaimChange, RelationshipEntityRef, SubjectiveClaimUpdateProposal,
    SubjectiveEntityClaim,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def context(existing=None):
    return SubjectiveModelUpdateContext(
        simulation_id="simulation_1", actor_id="observer", actor_name="Alex",
        simulation_time=NOW, turn_id="turn_1",
        new_memories=[MemoryAtom(id="memory_1", summary="The bridge shook.", keywords=[], embedding=None)],
        candidate_entities=[RelationshipEntityRef(type="location", id="bridge", name="Bridge")],
        existing_claims=existing or [],
    )


def change(**updates):
    values = dict(subject_id="bridge", category="safety", statement="The bridge seems unsafe",
                  stance="suspects", evidence_effect="supports", evidence_memory_ids=["memory_1"])
    values.update(updates)
    return ProposedSubjectiveClaimChange(**values)


async def test_creates_private_typed_claim_with_code_confidence_and_audit():
    db = Mock()
    db.subjective_entity_claim.create_claim = AsyncMock(side_effect=lambda value: value)
    db.subjective_entity_claim.create_change_audit = AsyncMock(side_effect=lambda value: value)
    result = await SubjectiveModelUpdater(database=db)._apply_proposal(
        SubjectiveClaimUpdateProposal(changes=[change()]), context())
    created = db.subjective_entity_claim.create_claim.await_args.args[0]
    assert result.applied_claim_ids == [created.id]
    assert created.observer_character_id == "observer"
    assert created.confidence == .45
    assert created.normalized_statement == "the bridge seems unsafe"
    assert db.subjective_entity_claim.create_change_audit.await_args.args[0].turn_id == "turn_1"


async def test_exact_duplicate_is_consolidated_and_contradiction_is_preserved():
    current = SubjectiveEntityClaim(
        id="claim_1", simulation_id="simulation_1", observer_character_id="observer",
        subject=RelationshipEntityRef(type="location", id="bridge", name="Bridge"), category="safety",
        statement="The bridge seems unsafe.", normalized_statement="the bridge seems unsafe",
        stance="suspects", confidence=.45, supporting_memory_ids=["old_memory"],
        first_observed_at=NOW, last_updated_at=NOW,
    )
    db = Mock()
    db.subjective_entity_claim.update_claim = AsyncMock(side_effect=lambda value: value)
    db.subjective_entity_claim.create_change_audit = AsyncMock(side_effect=lambda value: value)
    updater = SubjectiveModelUpdater(database=db)
    result = await updater._apply_proposal(
        SubjectiveClaimUpdateProposal(changes=[change(
            statement="The bridge seems unsafe!", evidence_effect="contradicts", stance="doubts")]),
        context([current]),
    )
    updated = db.subjective_entity_claim.update_claim.await_args.args[0]
    assert result.applied_claim_ids == ["claim_1"]
    assert updated.version == 2
    assert updated.confidence == pytest.approx(.35)
    assert updated.supporting_memory_ids == ["old_memory"]
    assert updated.contradicting_memory_ids == ["memory_1"]


async def test_rejects_unknown_evidence_and_contradictory_new_claim():
    db = Mock()
    db.subjective_entity_claim.create_claim = AsyncMock()
    updater = SubjectiveModelUpdater(database=db)
    result = await updater._apply_proposal(SubjectiveClaimUpdateProposal(changes=[
        change(evidence_memory_ids=["invented"]), change(evidence_effect="contradicts")]), context())
    assert result.skipped_changes == 2
    db.subjective_entity_claim.create_claim.assert_not_awaited()
