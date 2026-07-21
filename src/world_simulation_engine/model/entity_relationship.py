"""Typed first-class relationships between simulation entities."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .inter_state.state_commit import PhysicalEntityType


class RelationshipVisibility(StrEnum):
    """Who may recall a relationship."""
    PUBLIC = "public"
    PRIVATE = "private"
    OBJECTIVE = "objective"


class RelationshipScope(StrEnum):
    """Whether a record is a template or live simulation state."""
    WORLD = "world"
    SIMULATION = "simulation"


class RelationshipEntityRef(BaseModel):
    """Stable typed reference to a relationship endpoint."""
    model_config = ConfigDict(extra="forbid")

    type: PhysicalEntityType
    id: str
    name: str | None = None


class InterpersonalRelationshipDetails(BaseModel):
    """Directional social attitude dimensions."""
    kind: Literal["interpersonal"] = "interpersonal"
    category: str = "acquaintance"
    familiarity: float = Field(default=0, ge=0, le=1)
    trust: float = Field(default=0, ge=-1, le=1)
    affinity: float = Field(default=0, ge=-1, le=1)
    tension: float = Field(default=0, ge=0, le=1)


class SpatialRelationshipDetails(BaseModel):
    """Explicit distance or travel information."""
    kind: Literal["spatial"] = "spatial"
    distance_metres: float | None = Field(default=None, ge=0)
    travel_time_seconds: int | None = Field(default=None, ge=0)
    bidirectional: bool = True


class InteractionRelationshipDetails(BaseModel):
    """Repeated interaction or habit metadata."""
    kind: Literal["interaction"] = "interaction"
    frequency: str | None = None
    last_occurrence_at: datetime | None = None


class GoalRelationshipDetails(BaseModel):
    """An entity-directed goal such as looking for an item."""
    kind: Literal["goal"] = "goal"
    status: str = "active"
    priority: float | None = Field(default=None, ge=0, le=1)


class CompatibilityRelationshipDetails(BaseModel):
    """Compatibility constraint between two entities."""
    kind: Literal["compatibility"] = "compatibility"
    compatible: bool
    conditions: list[str] = Field(default_factory=list)


class GenericRelationshipDetails(BaseModel):
    """Extensible attributes for uncategorised relationships."""
    kind: Literal["generic"] = "generic"
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


EntityRelationshipDetails = Annotated[
    InterpersonalRelationshipDetails
    | SpatialRelationshipDetails
    | InteractionRelationshipDetails
    | GoalRelationshipDetails
    | CompatibilityRelationshipDetails
    | GenericRelationshipDetails,
    Field(discriminator="kind"),
]


class EntityRelationship(BaseModel):
    """A directional, simulation-scoped relationship with optional subjective ownership."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    scope_type: RelationshipScope
    scope_id: str
    source: RelationshipEntityRef
    target: RelationshipEntityRef
    label: str = Field(min_length=1)
    public_description: str | None = None
    private_description: str | None = None
    visibility: RelationshipVisibility = RelationshipVisibility.OBJECTIVE
    perspective_character_id: str | None = Field(
        default=None,
        description=(
            "Character whose subjective knowledge this record represents; "
            "null for objective facts."
        ),
    )
    confidence: float = Field(default=1, ge=0, le=1)
    details: EntityRelationshipDetails = Field(
        default_factory=GenericRelationshipDetails,
    )
    evidence_memory_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    last_changed_at: datetime
    version: int = Field(default=1, ge=1)
    active: bool = True

    @model_validator(mode="after")
    def validate_scope(self) -> "EntityRelationship":
        """Enforce endpoint and subjective-visibility invariants."""
        if self.source.id == self.target.id:
            raise ValueError("Relationship source and target must be different entities")
        if self.visibility == RelationshipVisibility.PRIVATE and not self.perspective_character_id:
            raise ValueError("Private relationships require perspective_character_id")
        if self.private_description and not self.perspective_character_id:
            raise ValueError("private_description requires perspective_character_id")
        if isinstance(self.details, InterpersonalRelationshipDetails):
            if self.source.type != "character" or self.target.type != "character":
                raise ValueError("Interpersonal relationships require character source and target")
        self.evidence_memory_ids = list(dict.fromkeys(self.evidence_memory_ids))
        return self


class RecalledEntityRelationship(BaseModel):
    """Relationship plus a code-calculated recall reason."""
    relationship: EntityRelationship
    recall_reason: str


class ProposedRelationshipChange(BaseModel):
    """Small LLM proposal; code constructs or updates the authoritative relationship."""

    model_config = ConfigDict(extra="forbid")

    relationship_id: str | None = None
    kind: Literal["interpersonal", "spatial", "interaction", "goal", "compatibility", "generic"]
    source_id: str
    target_id: str
    label: str = Field(min_length=1)
    private_description: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_memory_ids: list[str] = Field(min_length=1, max_length=4)
    familiarity_delta: float | None = Field(default=None, ge=-0.25, le=0.25)
    trust_delta: float | None = Field(default=None, ge=-0.25, le=0.25)
    affinity_delta: float | None = Field(default=None, ge=-0.25, le=0.25)
    tension_delta: float | None = Field(default=None, ge=-0.25, le=0.25)
    distance_metres: float | None = Field(default=None, ge=0)
    travel_time_seconds: int | None = Field(default=None, ge=0)
    frequency: str | None = None
    goal_status: str | None = None
    goal_priority: float | None = Field(default=None, ge=0, le=1)
    compatible: bool | None = None
    conditions: list[str] = Field(default_factory=list, max_length=4)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "ProposedRelationshipChange":
        """Reject ambiguous specialized changes before deterministic application."""
        if self.kind == "compatibility" and self.compatible is None:
            raise ValueError("Compatibility changes require compatible")
        if self.kind == "spatial" and self.distance_metres is None and self.travel_time_seconds is None:
            raise ValueError("Spatial changes require distance or travel time")
        return self


class RelationshipUpdateProposal(BaseModel):
    """Bounded changes for one character perspective and one committed turn."""

    model_config = ConfigDict(extra="forbid")

    changes: list[ProposedRelationshipChange] = Field(default_factory=list, max_length=2)
    updater_notes: list[str] = Field(default_factory=list, max_length=3)


class RelationshipChangeAudit(BaseModel):
    """Immutable provenance record for one applied relationship version."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    relationship_id: str
    scope_id: str
    perspective_character_id: str
    turn_id: str
    evidence_memory_ids: list[str] = Field(min_length=1)
    changed_at: datetime
    change_type: Literal["create", "update"]
    previous_version: int | None = None
    new_version: int
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any]
