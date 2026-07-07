from datetime import datetime
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Simulation(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the simulation",
    )
    name: str = Field(
        ...,
        description="Name of the simulation",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the simulation",
    )

    current_time: datetime = Field(
        ...,
        description="Current time of the simulation",
    )
