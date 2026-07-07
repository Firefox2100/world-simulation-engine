from uuid import uuid4
from pydantic import BaseModel, Field


class Location(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the location",
    )
    name: str = Field(
        ...,
        description="Name of the location",
    )
    description: str = Field(
        ...,
        description="Description of the location",
    )
