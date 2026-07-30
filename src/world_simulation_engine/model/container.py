from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ContainerState


class Container(BaseModel):
    """
    A container is an entity that can hold item or equipment. It is a first class entity, because
    it has special state and relationship that needs to be checked deterministically.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="The unique identifier of the container",
    )
    name: str = Field(
        ...,
        description="The name of the container",
    )
    description: str = Field(
        ...,
        description="The description of the container",
    )
    state: ContainerState = Field(
        ...,
        description="The current state of the container",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Entity that owns the container, if any. Populated when read back from storage.",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Entity that holds the container, if any. Populated when read back from storage.",
    )
    location_id: Optional[str] = Field(
        None,
        description="Location the container is present in, if not held by another entity. Populated when "
                    "read back from storage.",
    )
    position: Optional[str] = Field(
        None,
        description="Position of the container in its location, if present in a location.",
    )
