from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import GenerationJobStatus, SimulationGenerationRequestType


class GenerationJob(BaseModel):
    """A durable, simulation-scoped generation run and its lifecycle state."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    simulation_id: str
    client_request_id: str | None = None
    request_fingerprint: str | None = None
    request_type: SimulationGenerationRequestType
    regenerate_turn_sequence: int | None = Field(default=None, ge=0)
    status: GenerationJobStatus = GenerationJobStatus.QUEUED
    stage: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    final_turn_id: str | None = None
"""Persistent metadata for a simulator generation run."""
