from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PhysicalEntityType = Literal[
    "character",
    "background_character",
    "item",
    "item_stack",
    "equipment",
    "container",
    "location",
    "landmark",
    "body",
    "unknown",
]


RelationshipType = Literal[
    "located_at",
    "inside",
    "held_by",
    "owned_by",
    "equipped_by",
    "wearing",
    "attached_to",
    "near",
    "part_of",
    "derived_from",
    "interacting_with",
    "emotion_toward",
    "state_toward",
    "other",
]


class StateCommitEntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: PhysicalEntityType
    id: str | None = Field(
        default=None,
        description="Existing entity id when known. Null only for proposed new entities.",
    )
    name: str | None = Field(
        default=None,
        description="Human-readable entity name for review and debugging.",
    )


class StateCommitFieldChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(
        description="Dot-separated physical-state field path, such as public_state, state, quality, or current_activity.name.",
    )
    old_value: Any | None = Field(
        default=None,
        description="Current value when known from context. Null when unknown or not supplied.",
    )
    new_value: Any = Field(
        description="Proposed new value.",
    )
    reason: str = Field(
        description="Why this field should change based on what happened.",
    )


class ProposedEntityCreation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["create"] = "create"
    entity_type: PhysicalEntityType
    proposed_id: str | None = Field(
        default=None,
        description="Optional stable id suggested by the model. The committer may replace it.",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial physical/entity properties matching the target entity model as much as possible.",
    )
    initial_relationships: list["ProposedRelationshipChange"] = Field(default_factory=list)
    source_action_refs: list[str] = Field(
        default_factory=list,
        description="References to accepted actions or summaries that justify this creation.",
    )
    reason: str


class ProposedEntityStateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["state_change"] = "state_change"
    entity: StateCommitEntityRef
    field_changes: list[StateCommitFieldChange] = Field(default_factory=list)
    source_action_refs: list[str] = Field(default_factory=list)
    reason: str


class ProposedEntityPromotion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["promote"] = "promote"
    source_entity: StateCommitEntityRef
    target_entity_type: PhysicalEntityType
    target_properties: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Properties for the target entity form. Include carried-over physical state from the source when relevant."
        ),
    )
    preserve_source_as_state: bool = Field(
        True,
        description=(
            "Whether the source entry should remain as a physical state/history marker instead of being deleted."
        ),
    )
    source_state_changes: list[StateCommitFieldChange] = Field(
        default_factory=list,
        description="Changes to apply to the source entity to represent the promotion without deleting it.",
    )
    relationship_changes: list["ProposedRelationshipChange"] = Field(default_factory=list)
    source_action_refs: list[str] = Field(default_factory=list)
    reason: str


class ProposedRelationshipChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["relationship_change"] = "relationship_change"
    relationship_type: RelationshipType
    subject: StateCommitEntityRef
    object: StateCommitEntityRef | None = Field(
        default=None,
        description="Target entity for binary relationships. Null only when clearing or ending a relationship.",
    )
    old_object: StateCommitEntityRef | None = Field(
        default=None,
        description="Previous related entity when known, such as the old location or holder.",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Relationship properties, such as equipped_position, position, intensity, or visibility.",
    )
    ended: bool = Field(
        False,
        description="True when the relationship should be marked inactive/ended rather than deleted.",
    )
    source_action_refs: list[str] = Field(default_factory=list)
    reason: str


class ProposedNoPhysicalChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["no_physical_change"] = "no_physical_change"
    source_action_refs: list[str] = Field(default_factory=list)
    reason: str = Field(
        description="Why no physical state/entity change is needed for the referenced accepted action.",
    )


StateCommitOperation = Annotated[
    ProposedEntityCreation
    | ProposedEntityStateChange
    | ProposedEntityPromotion
    | ProposedRelationshipChange
    | ProposedNoPhysicalChange,
    Field(discriminator="type"),
]


class StateCommitProposal(BaseModel):
    """
    Non-authoritative proposed physical state changes for one coordinated turn.

    This model intentionally excludes events, memories, intent changes, and other abstract records.
    Physical entries should not be deleted; represent loss, destruction, death, or disappearance as
    state changes, promotions, or ended relationships.
    """

    model_config = ConfigDict(extra="forbid")

    operations: list[StateCommitOperation] = Field(default_factory=list)
    unchanged_action_refs: list[str] = Field(
        default_factory=list,
        description="Accepted actions that require no physical state change.",
    )
    committer_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )

    @field_validator("committer_notes", mode="before")
    @classmethod
    def _coerce_single_note(cls, value):
        if isinstance(value, str):
            return [value]
        return value
