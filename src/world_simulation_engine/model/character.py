from pydantic import BaseModel, Field


class Character(BaseModel):
    id: int = Field(
        ...,
        description="The unique identifier of the character."
    )
    name: str = Field(
        ...,
        description="The name of the character."
    )
    gender: str = Field(
        ...,
        description="The gender of the character."
    )
    age: int = Field(
        ...,
        description="The age of the character."
    )
    description: str = Field(
        ...,
        description="A brief summary or description of the character. This should be a general description; "
                    "for additional stats and attributes that will change over time, use the specialised fields.",
    )
    appearance: str = Field(
        ...,
        description="The appearance of the character. This should be persistent description, not things like clothes. "
                    "It may still be updated for significant persistent changes.",
    )
    public_state: str = Field(
        ...,
        description="The publicly known state of the character."
    )
    private_state: str = Field(
        ...,
        description="The privately state of the character. This is not known to other characters."
    )

    attributes: dict[str, list[str]] = Field(
        default_factory=dict,
        description="A dictionary of attributes associated with the character."
    )
    stats: dict[str, float] = Field(
        default_factory=dict,
        description="A dictionary of stats associated with the character."
    )

    location: int = Field(
        ...,
        description="The location ID of the character."
    )

    user_controlled: bool = Field(
        False,
        description="Whether or not the character is played by the user."
    )
