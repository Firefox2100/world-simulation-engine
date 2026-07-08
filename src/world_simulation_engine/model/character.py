from datetime import datetime
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class CurrentActivity(BaseModel):
    """
    An activity that the character is currently engaged in

    This model matches what would be proposed by the LLM, so that later the proposal becomes
    the new state
    """

    name: str = Field(
        ...,
        description="Name of the activity",
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Date and time the activity was started",
    )
    expected_end: Optional[datetime] = Field(
        None,
        description="Date and time the activity is expected to end, if not interrupted",
    )
    interruptible: bool = Field(
        True,
        description="Whether the activity is interruptible",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints for the activity",
    )


class Character(BaseModel):
    """
    A character in a simulation.

    A character may be an important NPC or the character that the user controls. The system does not
    differentiate between them internally to maintain consistency on decision-making.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the character",
    )
    name: str = Field(
        ...,
        description="Name of the character",
    )
    age: int = Field(
        ...,
        description="Age of the character",
    )
    gender: str = Field(
        ...,
        description="Gender of the character",
    )
    appearance: str = Field(
        ...,
        description="Appearance of the character",
    )
    description: str = Field(
        ...,
        description="Description of the character",
    )

    public_state: str = Field(
        ...,
        description="Public state of the character, i.e. what he is appeared to be doing",
    )
    private_state: str = Field(
        ...,
        description="Private state of the character, i.e. what he is thinking or secretly doing",
    )
    current_activity: CurrentActivity = Field(
        ...,
        description="Current activity of the character",
    )


class BackgroundCharacter(BaseModel):
    """
    A background character is someone who is not important enough to have his own agent. They are only
    reactive, cannot make decisions directly, and is controlled as world state changes. They can be friendly,
    neutral or hostile, so enemies are also using this model
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the background character",
    )
    name: str = Field(
        ...,
        description="Name of the background character",
    )
    description: str = Field(
        ...,
        description="Description of the background character",
    )
