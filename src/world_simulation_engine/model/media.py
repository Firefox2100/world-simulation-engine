from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import MediaType


class MediaFile(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the media file",
    )
    type: MediaType = Field(
        ...,
        description="Type of the media file",
    )
    title: Optional[str] = Field(
        None,
        description="Title of the media file",
    )
    hash: str = Field(
        ...,
        description="Hash of the media file",
    )
    filename: str = Field(
        ...,
        description="Filename of the media file, no format suffix",
    )
