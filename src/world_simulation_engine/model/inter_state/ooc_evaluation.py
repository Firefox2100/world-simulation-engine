from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from world_simulation_engine.misc.enums import TriggerEffectKind, TriggerStatus

from ..trigger import GateEffect, TriggerCondition, TriggerEffectPayload
from .action_proposal import ProposedAction
from .state_commit import StateCommitOperation, repair_state_commit_operations


class OOCWorldStateMutation(BaseModel):
    """A direct world state edit forced by an OOC command, bypassing normal action validation."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def repair_operation_types(cls, value: Any) -> Any:
        # This operations list reaches apply_state_commit_proposal exactly like
        # StateCommitProposal.operations does, and carries the same entity-creation risk if a
        # missing discriminator is guessed wrong - see repair_state_commit_operations.
        if not isinstance(value, dict) or not isinstance(value.get("operations"), list):
            return value

        return {**value, "operations": repair_state_commit_operations(value["operations"])}

    category: Literal["world_state_mutation"]
    command_index: int = Field(
        ge=0,
        description="Zero-based index of the OOC command this evaluation responds to.",
    )
    command_text: str = Field(
        description="The command text this evaluation responds to, copied from the supplied command.",
    )
    operations: list[StateCommitOperation] = Field(
        default_factory=list,
        description="Direct world state changes the command requires, in the same shape as a state commit.",
    )
    consistent: bool = Field(
        description=(
            "Whether the command passed a basic consistency check against the supplied world state, "
            "such as referencing entities that exist or are a reasonable new creation."
        ),
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Brief reasons the command failed the basic consistency check. Empty when consistent.",
    )
    reason: str = Field(
        description="Brief explanation of what the mutation does and why, for the audit trail and player-facing notice.",
    )


class OOCCharacterActionGuide(BaseModel):
    """Guidance that overrides normal character proposal generation for one non-user character."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["character_action_guide"]
    command_index: int = Field(
        ge=0,
        description="Zero-based index of the OOC command this evaluation responds to.",
    )
    command_text: str = Field(
        description="The command text this evaluation responds to, copied from the supplied command.",
    )
    character_id: str = Field(
        description="The non-user character this guidance directs.",
    )
    actions: list[ProposedAction] = Field(
        min_length=1,
        description="Actions forced into this character's next proposal, replacing normal action generation.",
    )
    reason: str = Field(
        description="Brief explanation of why these actions satisfy the command, for the audit trail.",
    )


class OOCTriggerDraft(BaseModel):
    """Full authored definition of a trigger, for the create/update trigger_directive operations -
    mirrors router/trigger.py's TriggerCreate/TriggerUpdate DTOs but lives in model/ (not router/)
    since it needs to be embedded inside OOCTriggerDirective."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def repair_state_mutation_operation_types(cls, value: Any) -> Any:
        # A trigger's own state_mutation effect carries a nested StateCommitOperation list -
        # exactly the same shape and discriminator-omission risk as OOCWorldStateMutation.operations,
        # so it gets the same repair pass.
        if not isinstance(value, dict) or not isinstance(value.get("effects"), list):
            return value

        repaired_effects = []
        for effect in value["effects"]:
            if (
                    isinstance(effect, dict)
                    and effect.get("type") == "state_mutation"
                    and isinstance(effect.get("operations"), list)
            ):
                effect = {**effect, "operations": repair_state_commit_operations(effect["operations"])}
            repaired_effects.append(effect)
        return {**value, "effects": repaired_effects}

    name: str = Field(min_length=1, description="Author-facing label, never shown to any LLM.")
    description: str = Field(default="", description="Author-facing notes, never shown to any LLM.")
    condition: TriggerCondition
    effect_kind: TriggerEffectKind
    effects: list[TriggerEffectPayload] = Field(default_factory=list, max_length=3)
    gate_effect: GateEffect | None = None
    chance: float | None = Field(default=None, ge=0, le=1)
    repeatable: bool = False
    cooldown_turns: int | None = Field(default=None, ge=1)
    reversible: bool = True


class OOCTriggerDirective(BaseModel):
    """A trigger created, redefined, retired, or removed by an OOC command - the authoring path
    for long-term scripted story threads (see CLAUDE.md/trigger.py) that no in-world character
    could plausibly have originated, so they can never be derived from normal conversation and
    must be hand-authored by the player acting as narrator/GM."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["trigger_directive"]
    command_index: int = Field(
        ge=0,
        description="Zero-based index of the OOC command this evaluation responds to.",
    )
    command_text: str = Field(
        description="The command text this evaluation responds to, copied from the supplied command.",
    )
    operation: Literal["create", "update", "set_status", "delete"] = Field(
        description="create: author a brand new trigger. update: redefine an existing trigger's "
                    "condition/effect. set_status: arm/disable/retire an existing trigger without "
                    "touching its definition. delete: remove an existing trigger entirely.",
    )
    trigger_id: str | None = Field(
        default=None,
        description="The existing trigger this directive targets. Required for update/set_status/"
                    "delete, null for create.",
    )
    draft: OOCTriggerDraft | None = Field(
        default=None,
        description="The full authored trigger definition. Required for create/update, null for "
                    "set_status/delete.",
    )
    status: TriggerStatus | None = Field(
        default=None,
        description="The new status to set. Required for set_status, null otherwise.",
    )
    consistent: bool = Field(
        description=(
            "Whether the command passed a basic consistency check, such as referencing an "
            "existing trigger_id that was actually supplied in context, or a reasonable new "
            "condition/effect for a create."
        ),
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Brief reasons the command failed the basic consistency check. Empty when consistent.",
    )
    reason: str = Field(
        description="Brief explanation of what the directive does and why, for the audit trail and player-facing notice.",
    )

    @model_validator(mode="after")
    def _validate_operation_shape(self) -> "OOCTriggerDirective":
        if self.operation == "create":
            if self.trigger_id is not None:
                raise ValueError("trigger_id must be null for a create operation.")
            if self.draft is None:
                raise ValueError("create needs draft set.")
        elif self.operation == "update":
            if self.trigger_id is None:
                raise ValueError("update needs trigger_id set.")
            if self.draft is None:
                raise ValueError("update needs draft set.")
        elif self.operation == "set_status":
            if self.trigger_id is None:
                raise ValueError("set_status needs trigger_id set.")
            if self.status is None:
                raise ValueError("set_status needs status set.")
        elif self.operation == "delete" and self.trigger_id is None:
            raise ValueError("delete needs trigger_id set.")
        return self


OOCEvaluationItem = Annotated[
    OOCWorldStateMutation | OOCCharacterActionGuide | OOCTriggerDirective,
    Field(discriminator="category"),
]


class OOCEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def infer_missing_item_categories(cls, value: Any) -> Any:
        """Repair a missing "category" discriminator when unambiguous from an item's fields.

        world_state_mutation and character_action_guide share no field names at all - a wrong
        guess simply fails normal required-field validation afterward rather than silently
        misapplying the item, so this stays safe even without special-casing. trigger_directive
        is checked first since "operation" is unique to it, even though it shares "consistent"
        with world_state_mutation.
        """
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            return value

        inferred_items = []
        for item in value["items"]:
            if not isinstance(item, dict) or item.get("category"):
                inferred_items.append(item)
                continue

            inferred_category = cls._infer_item_category(item)
            inferred_items.append(
                {"category": inferred_category, **item} if inferred_category else item
            )
        return {**value, "items": inferred_items}

    @staticmethod
    def _infer_item_category(item: dict[str, Any]) -> str | None:
        fields = set(item)
        if "operation" in fields:
            return "trigger_directive"
        if {"character_id", "actions"} <= fields:
            return "character_action_guide"
        if "consistent" in fields or "operations" in fields:
            return "world_state_mutation"
        return None

    items: list[OOCEvaluationItem] = Field(
        description="One evaluation item for every supplied OOC command, preserving command_index.",
    )
    evaluator_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )
