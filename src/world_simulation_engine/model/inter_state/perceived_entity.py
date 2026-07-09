from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import Visibility, Salience
from ..character import Character, BackgroundCharacter
from ..item import Item, ItemStack
from ..equipment import Equipment, InventoryEquipment
from ..location import Landmark
from ..container import Container


class PerceivedEntity(BaseModel):
    visibility: Visibility = Field(
        ...,
        description="The visibility of the entity"
    )
    distance_hint: Optional[str] = Field(
        None,
        description="Describing the distance between the observer and the entity, like near, across the room, "
                    "same location, behind counter, unknown, etc."
    )
    affordances: list[str] = Field(
        default_factory=list,
        description="Actions this actor currently believes are possible with this entity."
    )
    salience: Salience = Field(
        Salience.MEDIUM,
        description="The salience of the entity"
    )
    notes: Optional[str] = Field(
        None,
        description="A note about the perceived entity"
    )


class PerceivedCharacter(PerceivedEntity):
    character: Character = Field(
        ...,
        description="The character being perceived"
    )
    relation_to_actor: Optional[str] = Field(
        None,
        description="The relationship between character and observer"
    )
    visible_equipment: list[InventoryEquipment] = Field(
        default_factory=list,
        description="Equipment visibly equipped by this character"
    )


class PerceivedBackgroundCharacter(PerceivedEntity):
    character: BackgroundCharacter = Field(
        ...,
        description="The background character being perceived"
    )
    relation_to_actor: Optional[str] = Field(
        None,
        description="The relationship between the background character and observer"
    )


class PerceivedItem(PerceivedEntity):
    item: Item = Field(
        ...,
        description="The item being perceived"
    )
    stack: ItemStack = Field(
        ...,
        description="The stack of items"
    )
    owned_by_actor: bool = Field(
        ...,
        description="Whether the actor owns the item stack"
    )


class PerceivedEquipment(PerceivedEntity):
    equipment: Equipment = Field(
        ...,
        description="The equipment being perceived"
    )
    owned_by_actor: bool = Field(
        ...,
        description="Whether the actor owns the equipment"
    )


class PerceivedLandmark(PerceivedEntity):
    landmark: Landmark = Field(
        ...,
        description="The landmark being perceived"
    )


class PerceivedContainer(PerceivedEntity):
    container: Container = Field(
        ...,
        description="The container being perceived"
    )
    owned_by_actor: bool = Field(
        ...,
        description="Whether the actor owns the container"
    )
