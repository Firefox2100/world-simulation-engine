from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TurnVersion(BaseModel):
    """One archived alternate of a turn slot (a specific `turn_sequence`), captured right before
    that slot's live turn is about to be replaced - by a regeneration, or by reverting to a
    different archived version. Lets a user browse back through discarded regenerations instead of
    a swipe destroying the previous one outright.

    `turn`/`presentation_blocks` are opaque JSON dumps (Turn.model_dump(mode="json") and each
    TurnPresentationBlock's, respectively) - the same "arbitrarily nested, not a flat graph
    property" pattern used elsewhere (TriggerStore, WorldStateCheckpoint) - captured with the
    turn's own original id preserved, so re-materializing a version reuses that id rather than
    minting a new one, keeping any WorldStateCheckpoint-captured Event/Memory turn_id links valid.

    `user_input` is stored per-version (the user message that led to this particular generation)
    even though every version of one slot shares the same value today, since regeneration always
    replays the same input - this is forward-looking for a future "edit your message and
    regenerate" feature, where different versions of a slot could genuinely have different inputs.

    `checkpoint_id` points at the WorldStateCheckpoint capturing world state right after this
    version committed, letting a revert restore the world exactly as it was under this version -
    not just the text. It can go stale (the checkpoint may have since been pruned by the next real
    user turn's retention wipe - see WorldStateCheckpointStore); reverting then falls back to
    restoring the turn/presentation content alone.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    simulation_id: str
    turn_sequence: int
    turn: dict[str, Any]
    presentation_blocks: list[dict[str, Any]] = Field(default_factory=list)
    user_input: str | None = None
    checkpoint_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
