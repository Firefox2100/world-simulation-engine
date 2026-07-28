from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    category: Literal["world_state_mutation"] = "world_state_mutation"
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

    category: Literal["character_action_guide"] = "character_action_guide"
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


OOCEvaluationItem = Annotated[
    OOCWorldStateMutation | OOCCharacterActionGuide,
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
        misapplying the item, so this stays safe even without special-casing.
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
