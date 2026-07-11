from datetime import datetime
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import IntentType, IntentStatus, IntentHorizon


class Intent(BaseModel):
    """
    An intent is a driving thread that sways the character behaviour to a certain goal or task
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the intent",
    )
    type: IntentType = Field(
        ...,
        description="Type of the intent",
    )
    name: str = Field(
        ...,
        description="Name of the intent",
    )
    description: str = Field(
        ...,
        description="Description of the intent",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="A list of keywords for this intent",
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="A list of embeddings for this intent",
    )

    priority: float = Field(
        ...,
        description="Priority of the intent",
        ge=0,
        le=1,
    )
    urgency: float = Field(
        ...,
        description="Urgency of the intent",
        ge=0,
        le=1,
    )
    status: IntentStatus = Field(
        ...,
        description="Current status of the intent",
    )

    desired_state: Optional[str] = Field(
        None,
        description="The state that this intent is trying to achieve, if any"
    )
    success_conditions: list[str] = Field(
        default_factory=list,
        description="The criteria to consider this intent as successfully achieved"
    )
    failure_conditions: list[str] = Field(
        default_factory=list,
        description="The criteria to consider this intent as failed"
    )
    maintenance_conditions: list[str] = Field(
        default_factory=list,
        description="The conditions to maintain this intent"
    )

    deadline: Optional[datetime] = Field(
        None,
        description="The deadline for this intent",
    )
    horizon: IntentHorizon = Field(
        ...,
        description="The horizon for this intent",
    )

    constraints: list[str] = Field(
        default_factory=list,
        description="A list of constraints for this intent, mostly on what the character cannot or must do",
    )
    current_plan: list[str] = Field(
        default_factory=list,
        description="The current plan to achieve this intent",
    )
    next_action_biases: list[str] = Field(
        default_factory=list,
        description="What the next action to achieve this intent is likely to be",
    )

    blockers: list[str] = Field(
        default_factory=list,
        description="A list of blockers for this intent",
    )
    open_threads: list[str] = Field(
        default_factory=list,
        description="A list of open threads for this intent",
    )
