from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import SupportedLanguage


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


class WorldMetadata(BaseModel):
    """
    Human-facing provenance and notes for a world. Never passed to an LLM, purely for the
    benefit of whoever is browsing/managing worlds in the admin UI.
    """
    author: Optional[str] = Field(
        None,
        description="The original author/creator of the world's content (e.g. of the card it was imported from)",
    )
    author_url: Optional[str] = Field(
        None,
        description="A URL for the original author, e.g. their profile page",
    )
    resource_url: Optional[str] = Field(
        None,
        description="Where the world's content was originally downloaded from",
    )
    comment: Optional[str] = Field(
        None,
        description="Freeform human-readable notes about the world (usage tips, expectations, caveats). "
                    "Never included in LLM prompts.",
    )
    version: Optional[str] = Field(
        None,
        description="The content's own version string, as set by its original author",
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
    starting_time: datetime = Field(
        ...,
        description="The starting time for simulations created from the world",
    )

    version: int = Field(
        1,
        description="The version of the world, starting at 1",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the world",
    )
    language: SupportedLanguage = Field(
        ...,
        description="The language of the world",
    )

    metadata: WorldMetadata = Field(
        default_factory=WorldMetadata,
        description="Human-facing provenance/notes metadata for the world, all optional",
    )
    creation_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this world record was created. Always set automatically, never by user input.",
    )
