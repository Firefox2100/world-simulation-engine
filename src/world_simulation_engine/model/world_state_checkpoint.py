from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import WorldStateCheckpointType


class WorldStateCheckpoint(BaseModel):
    """A full capture of a simulation's mutable entity graph at one point in time, sufficient to
    restore it later (turn regeneration, and eventually undoing an OOC-forced mutation). Paired
    with a GraphStateSnapshot at the same simulation_id/turn boundary for the three types they
    share, but captures the actual persisted Neo4j entity state rather than transient LangGraph
    proposal state - see service/simulation_state_checkpoint_service.py for capture/restore.

    Each entity list is that entity's own model dump (mode="json") plus whatever
    relationship-derived fields (owner/holder/location/position, event/turn links, ...) are needed
    to fully reconstruct it, opaque JSON to this model - the same "arbitrarily nested, not a flat
    graph property" pattern used by TriggerStore/VariableStore.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    simulation_id: str
    type: WorldStateCheckpointType
    turn_id: str | None = None
    turn_sequence: int | None = None

    characters: list[dict[str, Any]] = Field(default_factory=list)
    background_characters: list[dict[str, Any]] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    item_stacks: list[dict[str, Any]] = Field(default_factory=list)
    equipment: list[dict[str, Any]] = Field(default_factory=list)
    containers: list[dict[str, Any]] = Field(default_factory=list)
    variable_sets: list[dict[str, Any]] = Field(default_factory=list)
    entity_relationships: list[dict[str, Any]] = Field(default_factory=list)
    emotion_states: list[dict[str, Any]] = Field(default_factory=list)
    subjective_entity_claims: list[dict[str, Any]] = Field(default_factory=list)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
