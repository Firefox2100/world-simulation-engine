from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator

from world_simulation_engine.misc.enums import ActionType


class ProposedAction(BaseModel):
    type: ActionType = Field(
        description="The type of action to be performed"
    )
    label: str = Field(
        ...,
        description="Short machine-readable action label"
    )
    target_ids: list[str] = Field(
        default_factory=list,
        description="The IDs of the target of this action"
    )
    utterance: Optional[str] = Field(
        default=None,
        description="Only if the action includes speech. Keep in-character"
    )

    intended_duration_seconds: int = Field(
        ge=1,
        le=7200,
        description="Best estimate if uninterrupted. Maximum 2 hours, then re-evaluation is needed"
    )
    interruptible: bool = Field(
        True,
        description="Whether this action can be interrupted"
    )
    interruption_triggers: list[str] = Field(
        default_factory=list,
        description="Triggers that can interrupt this action if it is interruptible"
    )

    required_preconditions: list[str] = Field(
        default_factory=list,
        description="Conditions the engine should verify before initiating"
    )
    expected_effects: list[str] = Field(
        default_factory=list,
        description="Non-authoritative effects the engine may apply if valid"
    )


class ActionProposal(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def normalize_llm_memory_updates(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        updates = normalized.get("memory_updates_suggested")
        if not isinstance(updates, list):
            return normalized

        normalized["memory_updates_suggested"] = [
            cls._memory_update_to_string(update)
            for update in updates
        ]
        return normalized

    @staticmethod
    def _memory_update_to_string(update: Any) -> str:
        if isinstance(update, str):
            return update
        if not isinstance(update, dict):
            return str(update)

        key = update.get("key") or update.get("id") or update.get("name") or update.get("type")
        value = update.get("value") or update.get("summary") or update.get("description")
        confidence = update.get("confidence")

        parts = []
        if key:
            parts.append(str(key))
        if value:
            parts.append(str(value))
        if confidence is not None:
            parts.append(f"confidence={confidence}")

        return "; ".join(parts) if parts else str(update)

    chosen_action: ProposedAction = Field(
        ...,
        description="The action to be performed"
    )
    alternatives_considered: list[ProposedAction] = Field(
        default_factory=list,
        description="When the original action is not available or possible, try these in order"
    )

    reasoning_summary: str = Field(
        ...,
        description="Brief, non-hidden explanation for debugging; no chain-of-thought"
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Possible risks that the action could have"
    )
    memory_updates_suggested: list[str] = Field(
        default_factory=list,
        description="Candidate durable facts or open threads to store later"
    )
    next_review_hint_seconds: int = Field(
        ge=1,
        le=7200,
        description="When the scheduler should re-evaluate this actor if uninterrupted"
    )
