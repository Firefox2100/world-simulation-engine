from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Equipment(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier of the equipment",
    )
    name: str = Field(
        ...,
        description="Name of the equipment",
    )
    description: str = Field(
        ...,
        description="Description of the equipment",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the equipment",
    )
