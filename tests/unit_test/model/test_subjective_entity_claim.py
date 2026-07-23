from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from world_simulation_engine.model import RelationshipEntityRef, SubjectiveEntityClaim


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_claim(**updates):
    values = dict(simulation_id="simulation_1", observer_character_id="observer",
                  subject=RelationshipEntityRef(type="location", id="location_1"), category="safety",
                  statement="The west path may be unsafe.", normalized_statement="the west path may be unsafe",
                  stance="suspects", confidence=.45, supporting_memory_ids=["memory_1"],
                  first_observed_at=NOW, last_updated_at=NOW)
    values.update(updates)
    return SubjectiveEntityClaim(**values)


def test_claim_supports_typed_non_character_subject():
    claim = make_claim()
    assert claim.subject.type == "location"
    assert claim.category == "safety"


def test_claim_rejects_self_model_and_overlapping_evidence():
    with pytest.raises(ValidationError, match="another entity"):
        make_claim(subject=RelationshipEntityRef(type="character", id="observer"))
    with pytest.raises(ValidationError, match="both support and contradict"):
        make_claim(contradicting_memory_ids=["memory_1"])
