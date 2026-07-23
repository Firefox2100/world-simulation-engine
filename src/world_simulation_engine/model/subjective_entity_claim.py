"""Private, evidence-backed models one character holds about an entity."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .entity_relationship import RelationshipEntityRef


class SubjectiveClaimCategory(StrEnum):
    APPEARANCE = "appearance"
    PERSONALITY = "personality"
    PREFERENCE = "preference"
    AVERSION = "aversion"
    CAPABILITY = "capability"
    HABIT = "habit"
    VALUE = "value"
    EXPECTATION = "relationship_expectation"
    IDENTITY = "identity"
    STATE = "state"
    SAFETY = "safety"
    ACCESS = "access"
    CONTENTS = "contents"
    PURPOSE = "purpose"
    CONDITION = "condition"
    OWNERSHIP = "ownership"
    RISK = "risk"
    HISTORY = "history"
    OTHER = "other"


class SubjectiveClaimStance(StrEnum):
    BELIEVES = "believes"
    SUSPECTS = "suspects"
    UNCERTAIN = "uncertain"
    DOUBTS = "doubts"
    DENIES = "denies"


class SubjectiveEntityClaim(BaseModel):
    """A private claim, distinct from an edge describing how two entities relate."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    simulation_id: str
    observer_character_id: str
    subject: RelationshipEntityRef
    category: SubjectiveClaimCategory
    statement: str = Field(min_length=1, max_length=500)
    normalized_statement: str = Field(min_length=1, max_length=500)
    stance: SubjectiveClaimStance
    confidence: float = Field(ge=0, le=1)
    supporting_memory_ids: list[str] = Field(default_factory=list)
    contradicting_memory_ids: list[str] = Field(default_factory=list)
    first_observed_at: datetime
    last_updated_at: datetime
    version: int = Field(default=1, ge=1)
    active: bool = True

    @model_validator(mode="after")
    def validate_claim(self) -> "SubjectiveEntityClaim":
        if self.subject.id == self.observer_character_id:
            raise ValueError("Subjective entity claims must concern another entity")
        self.supporting_memory_ids = list(dict.fromkeys(self.supporting_memory_ids))
        self.contradicting_memory_ids = list(dict.fromkeys(self.contradicting_memory_ids))
        if set(self.supporting_memory_ids) & set(self.contradicting_memory_ids):
            raise ValueError("The same memory cannot both support and contradict a claim")
        return self


class ProposedSubjectiveClaimChange(BaseModel):
    """Minimal local-model output; code owns confidence calculation and consolidation."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str | None = None
    subject_id: str
    category: SubjectiveClaimCategory
    statement: str = Field(min_length=1, max_length=500)
    stance: SubjectiveClaimStance
    evidence_effect: Literal["supports", "contradicts"] = "supports"
    evidence_memory_ids: list[str] = Field(min_length=1, max_length=4)


class SubjectiveClaimUpdateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[ProposedSubjectiveClaimChange] = Field(default_factory=list, max_length=2)


class SubjectiveClaimChangeAudit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    claim_id: str
    simulation_id: str
    observer_character_id: str
    turn_id: str
    evidence_memory_ids: list[str] = Field(min_length=1)
    changed_at: datetime
    change_type: Literal["create", "update"]
    previous_version: int | None = None
    new_version: int
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any]
