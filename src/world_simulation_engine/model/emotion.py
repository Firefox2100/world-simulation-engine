"""Compact private emotion state and memory-grounded change records."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EmotionVector(BaseModel):
    """Valence-arousal-dominance coordinates with a stable extension map."""

    model_config = ConfigDict(extra="forbid")

    valence: float = Field(default=0, ge=-1, le=1)
    arousal: float = Field(default=0, ge=-1, le=1)
    dominance: float = Field(default=0, ge=-1, le=1)
    dimensions: dict[str, float] = Field(default_factory=dict, max_length=4)


class EmotionState(BaseModel):
    """Slow baseline and fast response for one character in one simulation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    simulation_id: str
    character_id: str
    baseline: EmotionVector = Field(default_factory=EmotionVector)
    immediate: EmotionVector = Field(default_factory=EmotionVector)
    baseline_half_life_seconds: int = Field(default=604800, ge=60)
    immediate_half_life_seconds: int = Field(default=1800, ge=60)
    last_updated_at: datetime
    version: int = Field(default=1, ge=1)


class ProposedEmotionChange(BaseModel):
    """Small-model output; authoritative values are calculated by code."""

    model_config = ConfigDict(extra="forbid")

    immediate_delta: EmotionVector = Field(default_factory=EmotionVector)
    baseline_delta: EmotionVector = Field(default_factory=EmotionVector)
    evidence_memory_ids: list[str] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=1)

    @field_validator("immediate_delta", "baseline_delta", mode="before")
    @classmethod
    def null_delta_means_zero(cls, value):
        """Local models often emit null for a deliberately unchanged vector."""
        return {} if value is None else value


class EmotionUpdateProposal(BaseModel):
    """At most one emotional response for a single character perspective."""

    model_config = ConfigDict(extra="forbid")

    change: ProposedEmotionChange | None = None
    updater_notes: list[str] = Field(default_factory=list, max_length=2)

    @model_validator(mode="before")
    @classmethod
    def normalize_misplaced_notes(cls, value):
        if not isinstance(value, dict):
            return value

        change = value.get("change")
        if not isinstance(change, dict) or "updater_notes" not in change:
            return value

        normalized = dict(value)
        normalized_change = dict(change)
        notes = normalized_change.pop("updater_notes")
        normalized["change"] = normalized_change
        if not normalized.get("updater_notes"):
            normalized["updater_notes"] = notes
        return normalized

    @field_validator("updater_notes", mode="before")
    @classmethod
    def normalize_notes(cls, value):
        if value is None:
            return []
        return [value] if isinstance(value, str) else value


class EmotionChangeAudit(BaseModel):
    """Immutable provenance for one event-based emotion update."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    emotion_state_id: str
    simulation_id: str
    character_id: str
    turn_id: str
    evidence_memory_ids: list[str] = Field(min_length=1)
    changed_at: datetime
    change_type: Literal["create", "update"]
    previous_version: int | None = None
    new_version: int
    previous_state: dict | None = None
    new_state: dict
