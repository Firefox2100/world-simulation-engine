from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
            "This is not a prediction that the action will succeed. Explicit required_preconditions "
            "must be satisfied by the supplied state for this to be true."
        ),
    )
    reason: str = Field(
        description="Brief explanation of why the action is or is not allowed.",
    )
    blocking_conditions: list[str] = Field(
        default_factory=list,
        description=(
            "World-state, knowledge, genre, unmet required precondition, or environment conditions "
            "that prevent the action."
        ),
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Relevant non-blocking concerns for later scheduling or resolution.",
    )


class ActionValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_wrapper_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        validation_keys = {
            "action_index",
            "action",
            "allowed",
            "reason",
            "blocking_conditions",
            "warnings",
        }

        if "validations" not in normalized:
            for wrapper_key in ("action_validations", "validation_results", "results"):
                if wrapper_key in normalized:
                    normalized["validations"] = normalized.pop(wrapper_key)
                    break

        if "validations" not in normalized and validation_keys.intersection(normalized):
            normalized = {
                "validations": [normalized],
            }

        if normalized.get("type") == "ActionValidationResult":
            normalized.pop("type")

        return normalized

    validations: list[ActionValidation] = Field(
        description="One validation result for each proposed action, preserving input order.",
    )
    validator_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes about ambiguous assumptions. Do not include hidden chain-of-thought.",
    )
