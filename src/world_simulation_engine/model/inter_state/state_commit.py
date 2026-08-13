from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PhysicalEntityType = Literal[
    "world",
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


# RelationshipType values are never valid field_changes.field_path entries - a relationship is
# always expressed as its own relationship_change operation, never as a field on a state_change.
# Enforced here (not just in the prompt) because local models under schema-constrained decoding
# still sometimes emit e.g. {"field_path": "held_by", ...} on a state_change instead of a proper
# relationship_change - a soft prompt warning alone did not reliably stop it (see git history for
# state_committer.json), so the schema itself now rejects the shape and routes it through
# invoke_structured_with_repair's retry loop.
_RESERVED_RELATIONSHIP_FIELD_PATHS = frozenset(get_args(RelationshipType))


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

    @field_validator("field_path")
    @classmethod
    def _forbid_relationship_field_paths(cls, value: str) -> str:
        if value in _RESERVED_RELATIONSHIP_FIELD_PATHS:
            raise ValueError(
                f"{value!r} is a relationship_type, not a field_changes.field_path - express it as "
                "a relationship_change operation instead of a state_change field."
            )
        return value


class ProposedEntityCreation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Keep the discriminator required in the generated JSON schema. A Python default makes
    # Pydantic advertise this field as optional, which lets schema-constrained local models emit
    # an untagged union member and guess the wrong operation shape.
    type: Literal["create"]
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

    type: Literal["state_change"]
    entity: StateCommitEntityRef
    # This operation is meaningless without a field change. Making the list required here (in
    # addition to the non-empty validator below) prevents constrained decoding from omitting it.
    field_changes: list[StateCommitFieldChange]
    source_action_refs: list[str] = Field(default_factory=list)
    reason: str

    @model_validator(mode="before")
    @classmethod
    def _coerce_missing_reason(cls, value):
        if not isinstance(value, dict) or value.get("reason") is not None:
            return value

        field_changes = value.get("field_changes") or []
        reasons = [
            field_change.get("reason")
            for field_change in field_changes
            if isinstance(field_change, dict) and field_change.get("reason")
        ]
        if not reasons:
            return value

        return {
            **value,
            "reason": reasons[0],
        }

    @model_validator(mode="after")
    def _require_at_least_one_field_change(self) -> "ProposedEntityStateChange":
        # An empty field_changes list is a no-op that still consumes an accepted action's
        # source_action_refs, which lets a model "account for" an action (satisfying that separate
        # rule) without ever actually committing anything - observed in practice as a placeholder
        # state_change describing a relationship transfer in `reason`/committer_notes prose instead
        # of emitting the required relationship_change operation. no_physical_change already exists
        # for "nothing physical changed"; this shape has no legitimate use.
        if not self.field_changes:
            raise ValueError(
                "state_change.field_changes must not be empty - use no_physical_change if nothing "
                "physical actually changed, or relationship_change if this is really a relationship "
                "update (e.g. an item/equipment changing hands, ownership, or who is interacting "
                "with whom)."
            )
        return self


class ProposedEntityPromotion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["promote"]
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

    type: Literal["relationship_change"]
    relationship_type: RelationshipType
    subject: StateCommitEntityRef
    # object/old_object are required keys (must be present, may be null) rather than defaulted -
    # a Python default makes Pydantic advertise the key as optional in the generated JSON schema,
    # which let schema-constrained decoding omit it entirely (observed: the key missing outright,
    # not even present as null) even with _require_object_or_old_object below rejecting the
    # result. Required-but-nullable forces the decoder to at least consider a value for both.
    object: StateCommitEntityRef | None = Field(
        description="Target entity for binary relationships. Null only when clearing or ending a relationship.",
    )
    old_object: StateCommitEntityRef | None = Field(
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

    @model_validator(mode="after")
    def _require_object_or_old_object(self) -> "ProposedRelationshipChange":
        # StateCommitStore.change_relationship silently no-ops (no query at all) when both object
        # and old_object are missing, regardless of `ended` - observed in practice as a model
        # emitting relationship_type="interacting_with", ended=false, object=null with a reason
        # like "Greeting establishes interaction": schema-valid, but a guaranteed no-op that
        # never actually persists the relationship it claims to establish.
        if self.object is None and self.old_object is None:
            raise ValueError(
                "relationship_change needs object (the related entity) or old_object (the prior "
                "one, to end/replace it) - with both null this operation can never do anything "
                "when applied."
            )
        return self


class ProposedNoPhysicalChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["no_physical_change"]
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


def _unwrap_relationship_only_promotion(operation: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Detect a mistagged promotion wrapper that in fact carries only relationship data."""
    if not ({"source_entity", "target_entity_type"} <= set(operation)):
        return None
    if (
        operation.get("target_properties")
        or operation.get("source_state_changes")
        or "preserve_source_as_state" in operation
    ):
        return None

    relationship_changes = operation.get("relationship_changes")
    if not isinstance(relationship_changes, list) or not relationship_changes:
        return None

    return [
        {"type": "relationship_change", **change}
        if isinstance(change, dict) and not change.get("type") else change
        for change in relationship_changes
    ]


def _infer_operation_type(operation: dict[str, Any]) -> str | None:
    fields = set(operation)
    if {"relationship_type", "subject"} <= fields:
        return "relationship_change"
    if "entity_type" in fields:
        return "create"
    if "entity" in fields:
        return "state_change"
    if fields <= {"source_action_refs", "reason"}:
        return "no_physical_change"
    return None


def repair_state_commit_operations(operations: Any) -> Any:
    """Repair discriminator omissions in a raw list of StateCommitOperation dicts.

    Local models under schema-constrained decoding still sometimes omit the "type" tag on a
    StateCommitOperation despite the schema marking it required, which otherwise fails the whole
    proposal with a discriminator error even though the intended variant is obvious from the
    other fields present (e.g. relationship_type+subject can only be a relationship_change).

    "promote" is deliberately never guessed: applying it calls create_entity, so a wrong guess
    would leave a spurious duplicate entity node in the graph - a real data-corruption risk, not
    just a rejected proposal. In observed failures the model instead wraps a plain relationship
    change in a source_entity/target_entity_type container with no other promote-specific field
    populated; that shape is unwrapped into its own relationship_change operation(s) rather than
    tagged as a promotion.

    Shared by StateCommitProposal.operations and OOCWorldStateMutation.operations, since both
    reach apply_state_commit_proposal and carry the identical entity-creation risk.
    """
    if not isinstance(operations, list):
        return operations

    repaired_operations = []
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("type"):
            repaired_operations.append(operation)
            continue

        unwrapped = _unwrap_relationship_only_promotion(operation)
        if unwrapped is not None:
            repaired_operations.extend(unwrapped)
            continue

        inferred_type = _infer_operation_type(operation)
        repaired_operations.append(
            {"type": inferred_type, **operation}
            if inferred_type else operation
        )
    return repaired_operations


class StateCommitProposal(BaseModel):
    """
    Non-authoritative proposed physical state changes for one coordinated turn.

    This model intentionally excludes events, memories, intent changes, and other abstract records.
    Physical entries should not be deleted; represent loss, destruction, death, or disappearance as
    state changes, promotions, or ended relationships.
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def infer_missing_operation_types(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("operations"), list):
            return value

        return {**value, "operations": repair_state_commit_operations(value["operations"])}

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
