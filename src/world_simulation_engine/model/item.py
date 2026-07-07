from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique ID for this item",
    )
    name: str = Field(
        ...,
        description="Name of the item",
    )
    description: str = Field(
        ...,
        description="Description of the item",
    )
    unique: bool = Field(
        False,
        description="Whether or not the item is unique",
    )


class ItemStack(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique ID for this stack",
    )
    quantity: int = Field(
        1,
        description="The quantity of the item in this stack",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the item in this stack",
    )
