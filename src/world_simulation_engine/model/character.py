from uuid import uuid4
from pydantic import BaseModel, Field


class Character(BaseModel):
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
