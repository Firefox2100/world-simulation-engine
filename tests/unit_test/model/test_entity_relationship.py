from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from world_simulation_engine.model import (
    CompatibilityRelationshipDetails,
    EntityRelationship,
    InterpersonalRelationshipDetails,
    RelationshipEntityRef,
    RelationshipScope,
    RelationshipUpdateProposal,
    RelationshipVisibility,
)


def make_relationship(**updates) -> EntityRelationship:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    values = {
        "scope_type": RelationshipScope.SIMULATION,
        "scope_id": "simulation_1",
        "source": RelationshipEntityRef(type="character", id="character_1", name="Alex"),
        "target": RelationshipEntityRef(type="character", id="character_2", name="Blair"),
        "label": "trusts",
        "perspective_character_id": "character_1",
        "visibility": RelationshipVisibility.PRIVATE,
        "private_description": "Alex cautiously trusts Blair.",
        "details": InterpersonalRelationshipDetails(trust=0.4, familiarity=0.6),
        "evidence_memory_ids": ["memory_1"],
        "created_at": now,
        "last_changed_at": now,
    }
    values.update(updates)
    return EntityRelationship(**values)


def test_directional_relationship_preserves_subjective_scores_and_evidence():
    relationship = make_relationship()

    assert relationship.source.id == "character_1"
    assert relationship.target.id == "character_2"
    assert relationship.details.trust == 0.4
    assert relationship.evidence_memory_ids == ["memory_1"]


def test_interpersonal_details_require_character_endpoints():
    with pytest.raises(ValidationError, match="character source and target"):
        make_relationship(
            target=RelationshipEntityRef(type="location", id="location_1"),
        )


def test_private_relationship_requires_perspective_character():
    with pytest.raises(ValidationError, match="perspective_character_id"):
        make_relationship(perspective_character_id=None)


def test_generic_entity_relationship_supports_compatibility_constraints():
    relationship = make_relationship(
        source=RelationshipEntityRef(type="item", id="item_1", name="Battery"),
        target=RelationshipEntityRef(type="equipment", id="equipment_1", name="Radio"),
        label="not compatible with",
        visibility=RelationshipVisibility.OBJECTIVE,
        perspective_character_id=None,
        private_description=None,
        details=CompatibilityRelationshipDetails(
            compatible=False,
            conditions=["The battery voltage is too high."],
        ),
    )

    assert relationship.details.compatible is False
    assert relationship.source.type == "item"


def test_relationship_proposal_normalizes_scalar_notes_before_code_validation():
    proposal = RelationshipUpdateProposal.model_validate({
        "changes": [{
            "kind": "spatial",
            "source_id": "character_1",
            "target_id": "location_1",
            "label": "associated with",
            "private_description": "No measurable distance was supplied.",
            "confidence": .5,
            "evidence_memory_ids": ["memory_1"],
        }],
        "updater_notes": "The specialized fields are incomplete.",
    })

    assert proposal.updater_notes == ["The specialized fields are incomplete."]
