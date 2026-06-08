from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import NarrationPermission, WorldEntryRecallType, WorldEntryVisibility


class WorldEntryRecallKeyword(BaseModel):
    """
    A keyword matching criteria for recalling the world entry
    """
    keyword: str = Field(
        ...,
        description="The phrase to match against.",
    )
    similarity: float = Field(
        ...,
        description="The minimum unified similarity to consider recalling the entry.",
        ge=0.0,
        le=1.0,
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="The embedding of the world entry, used for recalling."
    )


class WorldEntry(BaseModel):
    id: int = Field(
        ...,
        description="The unique identifier of the world entry.",
    )
    scope: list[int] = Field(
        ...,
        description="The character IDs who can see this entry. 0 for everyone and -1 for no one.",
    )
    content: str = Field(
        ...,
        description="The content of the world entry. e.g. Alice found a hidden door in her room.",
    )
    visibility: WorldEntryVisibility = Field(
        ...,
        description="The visibility of the world entry.",
    )
    confidence: float = Field(
        ...,
        description="The confidence level of the world entry.",
        le=1.0,
        ge=0.0,
    )
    created_at: Optional[int] = Field(
        None,
        description="The round number of which the world entry was created. None if it's part of the background."
    )
    narration_permission: NarrationPermission = Field(
        ...,
        description="The narration permission of the world entry. This is used to determine whether the world "
                    "entry can be narrated by the narrator agent.",
    )

    recall_type: WorldEntryRecallType = Field(
        ...,
        description="How this entry should be recalled and added to the context.",
    )
    keywords: Optional[list[WorldEntryRecallKeyword]] = Field(
        None,
        description="The keyword filters to recall the world entry.",
    )
    chained_ids: Optional[list[int]] = Field(
        None,
        description="A list of IDs that, if any of them are recalled, this entry will be recalled together."
    )
    semantic_instruction: Optional[str] = Field(
        None,
        description="The instruction for LLM to know when to recall this entry or not."
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="The embedding of the world entry, used for semantic recall."
    )
