from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .action_proposal import ProposedAction
from .state_commit import StateCommitOperation


class OOCWorldStateMutation(BaseModel):
    """A direct world state edit forced by an OOC command, bypassing normal action validation."""

    model_config = ConfigDict(extra="forbid")

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

    items: list[OOCEvaluationItem] = Field(
        description="One evaluation item for every supplied OOC command, preserving command_index.",
    )
    evaluator_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )
