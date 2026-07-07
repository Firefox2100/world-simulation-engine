from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ConnectionType


class ConnectionConfig(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the connection",
    )
    type: ConnectionType = Field(
        ...,
        description="Type of the connection",
    )
    name: str = Field(
        ...,
        description="Name of the connection",
    )
    base_url: Optional[str] = Field(
        None,
        description="Base URL for the connection, can be None if using an official backend URL",
    )
    api_key: Optional[str] = Field(
        None,
        description="API key for the connection. Local or self-hosted connections may not have API key, leave "
                    "it empty in that case",
    )
