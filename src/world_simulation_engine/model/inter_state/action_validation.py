from pydantic import BaseModel, ConfigDict, Field

from .action_proposal import ProposedAction


class ActionValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_index: int = Field(
        ge=0,
        description="Zero-based index of the proposed action in the input action list.",
    )
    action: ProposedAction
    allowed: bool = Field(
        description=(
            "Whether this action is allowed to begin from the current world state. "
            "This is not a prediction that the action will succeed."
        ),
    )
    reason: str = Field(
        description="Brief explanation of why the action is or is not allowed.",
    )
    blocking_conditions: list[str] = Field(
        default_factory=list,
        description="World-state, knowledge, genre, or environment conditions that prevent the action.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Relevant non-blocking concerns for later scheduling or resolution.",
    )


class ActionValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validations: list[ActionValidation] = Field(
        description="One validation result for each proposed action, preserving input order.",
    )
    validator_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes about ambiguous assumptions. Do not include hidden chain-of-thought.",
    )
