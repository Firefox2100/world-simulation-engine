from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import TurnType


class Turn(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier of the turn",
    )
    sequence: int = Field(
        ...,
        description="The sequence number of the turn",
    )
    type: TurnType = Field(
        ...,
        description="The type of the turn",
    )
    content: str = Field(
        ...,
        description="The final, visible content of this turn, either human inputted or generated",
    )

    start_time: datetime = Field(
        ...,
        description="The start time of the turn",
    )
