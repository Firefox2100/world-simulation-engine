from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Character, Container, CurrentActivity, InventoryEquipment, InventoryStack
from .utils import db_dep


character_router = APIRouter(
    tags=["Character"],
)


class CharacterCreate(BaseModel):
    """
    DTO model for creating a character
    """

    user_controlled: bool = Field(
        False,
        description="Whether the user controls the character",
    )
    name: str = Field(
        ...,
        description="Name of the character",
    )
    age: int = Field(
        ...,
        description="Age of the character",
    )
    gender: str = Field(
        ...,
        description="Gender of the character",
    )
    appearance: str = Field(
        ...,
        description="Appearance of the character",
    )
    description: str = Field(
        ...,
        description="Description of the character",
    )

    public_state: str = Field(
        ...,
        description="Public state of the character, i.e. what he is appeared to be doing",
    )
    private_state: str = Field(
        ...,
        description="Private state of the character, i.e. what he is thinking or secretly doing",
    )
    current_activity: CurrentActivity = Field(
        ...,
        description="Current activity of the character",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the character is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position in the location",
    )
    landmark_id: Optional[str] = Field(
        None,
        description="Optional landmark the character is anchored to",
    )


class CharacterUpdate(BaseModel):
    """
    DTO model for updating a character
    """

    user_controlled: Optional[bool] = Field(
        None,
        description="Whether the user controls the character",
    )
    name: Optional[str] = Field(
        None,
        description="Name of the character",
    )
    age: Optional[int] = Field(
        None,
        description="Age of the character",
    )
    gender: Optional[str] = Field(
        None,
        description="Gender of the character",
    )
    appearance: Optional[str] = Field(
        None,
        description="Appearance of the character",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the character",
    )
    public_state: Optional[str] = Field(
        None,
        description="Public state of the character, i.e. what he is appeared to be doing",
    )
    private_state: Optional[str] = Field(
        None,
        description="Private state of the character, i.e. what he is thinking or secretly doing",
    )
    current_activity: Optional[CurrentActivity] = Field(
        None,
        description="Current activity of the character",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the character is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position in the location",
    )
    landmark_id: Optional[str] = Field(
        None,
        description="Optional landmark the character is anchored to",
    )


class CharacterLocationUpdate(BaseModel):
    location_id: str = Field(..., description="Location where the character is present")
    position: Optional[str] = Field(None, description="Optional position in the location")


class CharacterLandmarkUpdate(BaseModel):
    landmark_id: str = Field(..., description="Landmark the character is anchored to")


class CharacterInventory(BaseModel):
    stacks: list[InventoryStack] = Field(
        default_factory=list,
        description="Physical item stacks held by the character",
    )
    equipment: list[InventoryEquipment] = Field(
        default_factory=list,
        description="Equipment held or equipped by the character",
    )
    containers: list[Container] = Field(
        default_factory=list,
        description="Containers held by the character",
    )


async def validate_character_relationships(
        character_data: CharacterCreate | CharacterUpdate,
        db: db_dep,
):
    if character_data.location_id:
        location = await db.location.get_location(character_data.location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {character_data.location_id} not found",
            )

    if character_data.landmark_id:
        landmark = await db.location.get_landmark(character_data.landmark_id)
        if not landmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Landmark {character_data.landmark_id} not found",
            )


async def apply_character_relationships(
        character_id: str,
        character_data: CharacterCreate | CharacterUpdate,
        db: db_dep,
) -> Character:
    character = await db.character.get_character(character_id)

    if character_data.location_id:
        character = await db.character.move_to_location(
            character_id,
            character_data.location_id,
            character_data.position,
        )

    if character_data.landmark_id:
        character = await db.character.anchor_to_landmark(
            character_id,
            character_data.landmark_id,
        )

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    return character


@character_router.get("/characters/{character_id}/inventory", response_model=CharacterInventory)
async def get_character_inventory(character_id: str, db: db_dep):
    if not await db.character.get_character(character_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    return CharacterInventory(
        stacks=await db.item.get_inventory(character_id),
        equipment=await db.equipment.get_equipment_inventory(character_id),
        containers=await db.container.list_containers(holder_id=character_id),
    )


@character_router.get("/characters", response_model=list[Character])
async def list_characters(db: db_dep,
                          world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                          simulation_id: Optional[str] = Query(
                              None,
                              description="Optionally filter by simulation"
                          ),
                          location_id: Optional[str] = Query(
                              None,
                              description="Optionally filter by location",
                          )):
    return await db.character.list_characters(
        world_id=world_id,
        simulation_id=simulation_id,
        location_id=location_id,
    )


@character_router.get("/characters/{character_id}", response_model=Character)
async def get_character(character_id: str, db: db_dep):
    character = await db.character.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    return character


@character_router.patch("/characters/{character_id}", response_model=Character)
async def update_character(character_id: str, character_data: CharacterUpdate, db: db_dep):
    await validate_character_relationships(character_data, db)

    character = await db.character.update_character(
        character_id,
        character_data.model_dump(
            exclude_unset=True,
            exclude={"location_id", "position", "landmark_id"},
        ),
    )
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    return await apply_character_relationships(character_id, character_data, db)


@character_router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(character_id: str, db: db_dep):
    deleted = await db.character.delete_character(character_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )


@character_router.put("/characters/{character_id}/location", response_model=Character)
async def set_character_location(character_id: str, location_data: CharacterLocationUpdate, db: db_dep):
    if not await db.character.get_character(character_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )
    if not await db.location.get_location(location_data.location_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_data.location_id} not found",
        )

    return await db.character.move_to_location(character_id, location_data.location_id, location_data.position)


@character_router.delete("/characters/{character_id}/location", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_location(character_id: str, db: db_dep):
    deleted = await db.character.remove_character_location(character_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )


@character_router.put("/characters/{character_id}/landmark", response_model=Character)
async def set_character_landmark(character_id: str, landmark_data: CharacterLandmarkUpdate, db: db_dep):
    if not await db.character.get_character(character_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )
    if not await db.location.get_landmark(landmark_data.landmark_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Landmark {landmark_data.landmark_id} not found",
        )

    return await db.character.anchor_to_landmark(character_id, landmark_data.landmark_id)


@character_router.delete("/characters/{character_id}/landmark", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_landmark(character_id: str, db: db_dep):
    deleted = await db.character.remove_character_landmark(character_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )


@character_router.post("/worlds/{world_id}/characters", response_model=Character)
async def create_character_in_world(world_id: str, character_data: CharacterCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    await validate_character_relationships(character_data, db)

    character = Character(**character_data.model_dump(exclude={"location_id", "position", "landmark_id"}))
    created_character = await db.character.create_character(
        character,
        world_id,
        location_id=character_data.location_id,
        position=character_data.position,
        landmark_id=character_data.landmark_id,
    )
    if not created_character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return created_character


@character_router.post("/simulations/{simulation_id}/characters", response_model=Character)
async def create_character_in_simulation(simulation_id: str, character_data: CharacterCreate, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    await validate_character_relationships(character_data, db)

    character = Character(**character_data.model_dump(exclude={"location_id", "position", "landmark_id"}))
    created_character = await db.character.create_character(
        character,
        simulation_id,
        location_id=character_data.location_id,
        position=character_data.position,
        landmark_id=character_data.landmark_id,
    )
    if not created_character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return created_character
