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


class InventoryEquipment(Equipment):
    equipped: bool = Field(
        ...,
        description="Whether the equipment is equipped or not",
    )
    equipped_position: Optional[str] = Field(
        None,
        description="If equipped, where is it being worn"
    )
