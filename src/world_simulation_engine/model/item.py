from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique ID for this conceptual item type",
    )
    name: str = Field(
        ...,
        description="Name of the conceptual item type",
    )
    description: str = Field(
        ...,
        description="Description of the conceptual item type",
    )
    unique: bool = Field(
        False,
        description="Whether or not the item is unique",
    )


class ItemStack(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique ID for this physical item stack",
    )
    quantity: int = Field(
        1,
        description="The quantity of the item in this stack",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the item in this stack",
    )
    item: Optional[Item] = Field(
        None,
        description="The conceptual item type this stack is of. Populated when the stack is read "
                    "back from storage; not required when constructing a stack for creation.",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Entity that owns the stack, if any. Populated when read back from storage.",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Entity that holds the stack, if any. Populated when read back from storage.",
    )
    location_id: Optional[str] = Field(
        None,
        description="Location the stack is present in, if not held by another entity. Populated when "
                    "read back from storage.",
    )
    position: Optional[str] = Field(
        None,
        description="Position of the stack in its location, if present in a location.",
    )


class InventoryStack(BaseModel):
    item_id: str = Field(
        ...,
        description="Unique ID for the item in the stack",
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
    stack_id: str = Field(
        ...,
        description="Unique ID for the stack",
    )
    quantity: int = Field(
        ...,
        description="The quantity of the item in this stack",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the item in this stack",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Owner of the stack",
    )
