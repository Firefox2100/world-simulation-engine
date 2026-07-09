from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Event(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="The unique identifier of this event",
    )
    name: str = Field(
        ...,
        description="The name of the event",
    )
    summary: str = Field(
        ...,
        description="The summary of the event",
    )
