from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Simulation(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the simulation",
    )
    creation_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this simulation was created. Always set automatically, never by user input.",
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
    emotion_enabled: bool = Field(
        True,
        description="Whether private quantitative emotion state participates in simulation workflows.",
    )
    suggested_actions: list[str] = Field(
        default_factory=list,
        description="Short free-text suggestions for the user's next action, refreshed after each turn.",
    )
