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
