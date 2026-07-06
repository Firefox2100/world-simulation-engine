from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Author(BaseModel):
    """
    An author who created the world configuration
    """
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the author",
    )
    name: str = Field(
        ...,
        description="The name of the author",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the author",
    )


class World(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the world",
    )
    name: str = Field(
        ...,
        description="The name of the world",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the world",
    )

    version: int = Field(
        1,
        description="The version of the world, starting at 1",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the world",
    )
