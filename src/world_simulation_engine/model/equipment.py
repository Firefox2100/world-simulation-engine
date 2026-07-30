from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class Equipment(BaseModel):
    """
    A piece of equipment that character can wear. Only wearable items are considered equipment.

    The equipment does not have a wearable slot on purpose, so that it can be put on anywhere. The system will
    check for conflictions
    """

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
    owner_id: Optional[str] = Field(
        None,
        description="Entity that owns the equipment, if any. Populated when read back from storage.",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Entity that holds or wears the equipment, if any. Populated when read back from storage.",
    )
    location_id: Optional[str] = Field(
        None,
        description="Location the equipment is present in, if not held by another entity. Populated when "
                    "read back from storage.",
    )
    position: Optional[str] = Field(
        None,
        description="Position of the equipment in its location, if present in a location.",
    )


class InventoryEquipment(Equipment):
    equipped: bool = Field(
        ...,
        description="Whether the equipment is equipped or not",
    )
    equipped_position: Optional[str] = Field(
        None,
        description="If equipped, where is it being worn"
    )
