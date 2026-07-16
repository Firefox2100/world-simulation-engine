from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Equipment
from .utils import db_dep


equipment_router = APIRouter(
    tags=["Equipment"],
)


class EquipmentCreate(BaseModel):
    """
    DTO model for creating equipment
    """

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
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the equipment is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position in the location",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Optional owner of the equipment",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Optional holder of the equipment",
    )
    equipped: bool = Field(
        False,
        description="Whether the holder equips the equipment",
    )
    equipped_position: Optional[str] = Field(
        None,
        description="If equipped, where the equipment is worn",
    )


class EquipmentUpdate(BaseModel):
    """
    DTO model for updating equipment
    """

    name: Optional[str] = Field(
        None,
        description="Name of the equipment",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the equipment",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the equipment",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the equipment is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position in the location",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Optional owner of the equipment",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Optional holder of the equipment",
    )
    equipped: Optional[bool] = Field(
        None,
        description="Whether the holder equips the equipment",
    )
    equipped_position: Optional[str] = Field(
        None,
        description="If equipped, where the equipment is worn",
    )


def validate_equipment_relationship_request(equipment_data: EquipmentCreate | EquipmentUpdate):
    if equipment_data.location_id and equipment_data.holder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Equipment cannot be placed in a location and held at the same time",
        )

    if equipment_data.equipped is not None and equipment_data.equipped and not equipment_data.holder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Equipment cannot be equipped without a holder",
        )


async def validate_equipment_relationships(equipment_data: EquipmentCreate | EquipmentUpdate, db: db_dep):
    validate_equipment_relationship_request(equipment_data)

    if equipment_data.location_id:
        location = await db.location.get_location(equipment_data.location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {equipment_data.location_id} not found",
            )

    if equipment_data.owner_id and not await db.item.entity_exists(equipment_data.owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Owner {equipment_data.owner_id} not found",
        )

    if equipment_data.holder_id:
        if equipment_data.equipped:
            holder = await db.character.get_character(equipment_data.holder_id)
            if not holder:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Character {equipment_data.holder_id} not found",
                )
        elif not await db.item.entity_exists(equipment_data.holder_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Holder {equipment_data.holder_id} not found",
            )


async def apply_equipment_relationships(
        equipment_id: str,
        equipment_data: EquipmentCreate | EquipmentUpdate,
        db: db_dep,
) -> Equipment:
    equipment = await db.equipment.get_equipment(equipment_id)

    if equipment_data.location_id:
        equipment = await db.equipment.place_equipment_in_location(
            equipment_id,
            equipment_data.location_id,
            equipment_data.position,
        )

    if equipment_data.owner_id:
        equipment = await db.equipment.change_owner(equipment_id, equipment_data.owner_id)

    if equipment_data.holder_id:
        equipment = await db.equipment.change_hold_state(
            equipment_id,
            equipment_data.holder_id,
            equipped=bool(equipment_data.equipped),
            equipped_position=equipment_data.equipped_position,
        )

    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found",
        )

    return equipment


@equipment_router.get("/equipment", response_model=list[Equipment])
async def list_equipment(
        db: db_dep,
        world_id: Optional[str] = Query(None, description="Optionally filter by world"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
        location_id: Optional[str] = Query(None, description="Optionally filter by location"),
        owner_id: Optional[str] = Query(None, description="Optionally filter by owner"),
        holder_id: Optional[str] = Query(None, description="Optionally filter by holder"),
):
    return await db.equipment.list_equipment(
        world_id=world_id,
        simulation_id=simulation_id,
        location_id=location_id,
        owner_id=owner_id,
        holder_id=holder_id,
    )


@equipment_router.get("/equipment/{equipment_id}", response_model=Equipment)
async def get_equipment(equipment_id: str, db: db_dep):
    equipment = await db.equipment.get_equipment(equipment_id)
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found",
        )

    return equipment


@equipment_router.patch("/equipment/{equipment_id}", response_model=Equipment)
async def update_equipment(equipment_id: str, equipment_data: EquipmentUpdate, db: db_dep):
    await validate_equipment_relationships(equipment_data, db)

    equipment = await db.equipment.update_equipment(
        equipment_id,
        equipment_data.model_dump(
            exclude_unset=True,
            exclude={"location_id", "position", "owner_id", "holder_id", "equipped", "equipped_position"},
        ),
    )
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found",
        )

    return await apply_equipment_relationships(equipment_id, equipment_data, db)


@equipment_router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment(equipment_id: str, db: db_dep):
    deleted = await db.equipment.delete_equipment(equipment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipment {equipment_id} not found",
        )


@equipment_router.post("/worlds/{world_id}/equipment", response_model=Equipment)
async def create_equipment_in_world(world_id: str, equipment_data: EquipmentCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    await validate_equipment_relationships(equipment_data, db)

    equipment = Equipment(
        name=equipment_data.name,
        description=equipment_data.description,
        quality=equipment_data.quality,
    )
    created_equipment = await db.equipment.create_equipment(
        equipment,
        world_id,
        location_id=equipment_data.location_id,
        position=equipment_data.position,
    )
    if not created_equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return await apply_equipment_relationships(created_equipment.id, equipment_data, db)


@equipment_router.post("/simulations/{simulation_id}/equipment", response_model=Equipment)
async def create_equipment_in_simulation(
        simulation_id: str,
        equipment_data: EquipmentCreate,
        db: db_dep,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    await validate_equipment_relationships(equipment_data, db)

    equipment = Equipment(
        name=equipment_data.name,
        description=equipment_data.description,
        quality=equipment_data.quality,
    )
    created_equipment = await db.equipment.create_equipment(
        equipment,
        simulation_id,
        location_id=equipment_data.location_id,
        position=equipment_data.position,
    )
    if not created_equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return await apply_equipment_relationships(created_equipment.id, equipment_data, db)
