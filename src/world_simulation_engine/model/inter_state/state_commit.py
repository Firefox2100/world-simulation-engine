import json
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    _MAX_OPERATIONS: ClassVar[int] = 24

    operations: list[StateCommitOperation] = Field(default_factory=list)
    unchanged_action_refs: list[str] = Field(
        default_factory=list,
        description="Accepted actions that require no physical state change.",
    )
    committer_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )

    @staticmethod
    def _operation_key(operation: dict[str, Any]) -> str:
        if operation.get("type") == "state_change":
            key = {
                "type": operation.get("type"),
                "entity": operation.get("entity"),
                "field_changes": operation.get("field_changes"),
                "source_action_refs": operation.get("source_action_refs", []),
            }
        else:
            key = operation

        return json.dumps(key, sort_keys=True, default=str)

    @model_validator(mode="before")
    @classmethod
    def normalize_model_output(cls, data: Any):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return data

        if not isinstance(data, dict):
            return data

        operations = data.get("operations")
        if not isinstance(operations, list):
            return data

        normalized_operations = []
        seen_operation_keys = set()

        for operation in operations:
            if not isinstance(operation, dict):
                normalized_operations.append(operation)
                continue

            nested_relationships = operation.get("relationship_changes")
            if (
                "type" not in operation
                and isinstance(nested_relationships, list)
                and nested_relationships
            ):
                for nested_relationship in nested_relationships:
                    if not isinstance(nested_relationship, dict):
                        normalized_operations.append(nested_relationship)
                        continue

                    normalized_relationship = dict(nested_relationship)
                    normalized_relationship.setdefault("type", "relationship_change")
                    if not normalized_relationship.get("source_action_refs"):
                        normalized_relationship["source_action_refs"] = operation.get("source_action_refs", [])
                    operation_key = cls._operation_key(normalized_relationship)
                    if operation_key in seen_operation_keys:
                        continue

                    seen_operation_keys.add(operation_key)
                    normalized_operations.append(normalized_relationship)
                continue

            normalized_operation = dict(operation)
            if (
                "type" not in normalized_operation
                and "entity" in normalized_operation
                and "field_changes" in normalized_operation
            ):
                normalized_operation["type"] = "state_change"
            elif (
                "type" not in normalized_operation
                and "relationship_type" in normalized_operation
                and "subject" in normalized_operation
            ):
                normalized_operation["type"] = "relationship_change"

            for split_operation in cls._split_relationship_field_changes(normalized_operation):
                if "type" not in split_operation:
                    continue

                operation_key = cls._operation_key(split_operation)
                if operation_key in seen_operation_keys:
                    continue

                seen_operation_keys.add(operation_key)
                normalized_operations.append(split_operation)

        return {
            **data,
            "operations": normalized_operations[:cls._MAX_OPERATIONS],
        }

    @classmethod
    def _split_relationship_field_changes(cls, operation: dict[str, Any]) -> list[dict[str, Any]]:
        if operation.get("type") != "state_change":
            return [operation]

        entity = operation.get("entity")
        field_changes = operation.get("field_changes")
        if not isinstance(entity, dict) or not isinstance(field_changes, list):
            return [operation]

        state_field_changes = []
        relationship_operations = []
        for field_change in field_changes:
            if not isinstance(field_change, dict):
                state_field_changes.append(field_change)
                continue

            field_path = field_change.get("field_path")
            if field_path in cls._relationship_field_paths():
                relationship_operations.append(
                    {
                        "type": "relationship_change",
                        "relationship_type": field_path,
                        "subject": entity,
                        "object": field_change.get("new_value"),
                        "old_object": field_change.get("old_value"),
                        "properties": {},
                        "ended": field_change.get("new_value") is None,
                        "source_action_refs": operation.get("source_action_refs", []),
                        "reason": field_change.get("reason") or operation.get("reason") or "Relationship changed.",
                    }
                )
            else:
                state_field_changes.append(field_change)

        split_operations = []
        if state_field_changes:
            state_operation = dict(operation)
            state_operation["field_changes"] = state_field_changes
            split_operations.append(state_operation)
        split_operations.extend(relationship_operations)
        return split_operations

    @staticmethod
    def _relationship_field_paths() -> set[str]:
        return {
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
        }
