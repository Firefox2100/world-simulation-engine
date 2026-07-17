from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import GraphStateSnapshotType


class GraphStateSnapshot(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this saved graph state snapshot.",
    )
    simulation_id: str = Field(
        description="Simulation this snapshot belongs to.",
    )
    type: GraphStateSnapshotType = Field(
        description="Which limited regeneration boundary this snapshot represents.",
    )
    turn_id: str | None = Field(
        default=None,
        description="Turn whose boundary anchors this snapshot, when available.",
    )
    turn_sequence: int | None = Field(
        default=None,
        description="Turn sequence whose boundary anchors this snapshot, when available.",
    )
    state: dict[str, Any] = Field(
        description="Serialized graph state readable for regeneration setup.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="When this snapshot was saved.",
    )
