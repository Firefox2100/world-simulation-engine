from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import BackgroundCharacter
from .utils import db_dep


background_character_router = APIRouter(
    tags=["Background Character"],
)


class BackgroundCharacterCreate(BaseModel):
    """
    DTO model for creating a background character
    """

    name: str = Field(
        ...,
        description="Name of the background character",
    )
    description: str = Field(
        ...,
        description="Description of the background character",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the background character is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position in the location",
    )
    landmark_id: Optional[str] = Field(
        None,
        description="Optional landmark the background character is anchored to",
    )


class BackgroundCharacterUpdate(BaseModel):
    """
    DTO model for updating a background character
    """

    name: Optional[str] = Field(
        None,
        description="Name of the background character",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the background character",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the background character is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position in the location",
    )
    landmark_id: Optional[str] = Field(
        None,
        description="Optional landmark the background character is anchored to",
    )


class BackgroundCharacterLocationUpdate(BaseModel):
    location_id: str = Field(..., description="Location where the background character is present")
    position: Optional[str] = Field(None, description="Optional position in the location")


class BackgroundCharacterLandmarkUpdate(BaseModel):
    landmark_id: str = Field(..., description="Landmark the background character is anchored to")


async def validate_background_character_relationships(
        character_data: BackgroundCharacterCreate | BackgroundCharacterUpdate,
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


async def apply_background_character_relationships(
        character_id: str,
        character_data: BackgroundCharacterCreate | BackgroundCharacterUpdate,
        db: db_dep,
) -> BackgroundCharacter:
    character = await db.character.get_background_character(character_id)

    if character_data.location_id:
        character = await db.character.move_background_character_to_location(
            character_id,
            character_data.location_id,
            character_data.position,
        )

    if character_data.landmark_id:
        character = await db.character.anchor_background_character_to_landmark(
            character_id,
            character_data.landmark_id,
        )

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background character {character_id} not found",
        )

    return character


@background_character_router.get("/background-characters", response_model=list[BackgroundCharacter])
async def list_background_characters(
        db: db_dep,
        world_id: Optional[str] = Query(None, description="Optionally filter by world"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
        location_id: Optional[str] = Query(None, description="Optionally filter by location"),
):
    return await db.character.list_background_characters(
        world_id=world_id,
        simulation_id=simulation_id,
        location_id=location_id,
    )


@background_character_router.get("/background-characters/{character_id}", response_model=BackgroundCharacter)
async def get_background_character(character_id: str, db: db_dep):
    character = await db.character.get_background_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background character {character_id} not found",
        )

    return character


@background_character_router.patch("/background-characters/{character_id}", response_model=BackgroundCharacter)
async def update_background_character(
        character_id: str,
        character_data: BackgroundCharacterUpdate,
        db: db_dep,
):
    await validate_background_character_relationships(character_data, db)

    character = await db.character.update_background_character(
        character_id,
        character_data.model_dump(
            exclude_unset=True,
            exclude={"location_id", "position", "landmark_id"},
        ),
    )
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background character {character_id} not found",
        )

    return await apply_background_character_relationships(character_id, character_data, db)


@background_character_router.delete(
    "/background-characters/{character_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_background_character(character_id: str, db: db_dep):
    deleted = await db.character.delete_background_character(character_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background character {character_id} not found",
        )


@background_character_router.put("/background-characters/{character_id}/location", response_model=BackgroundCharacter)
async def set_background_character_location(
        character_id: str,
        location_data: BackgroundCharacterLocationUpdate,
        db: db_dep,
):
    if not await db.character.get_background_character(character_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Background character {character_id} not found")
    if not await db.location.get_location(location_data.location_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Location {location_data.location_id} not found")

    return await db.character.move_background_character_to_location(
        character_id,
        location_data.location_id,
        location_data.position,
    )


@background_character_router.delete(
    "/background-characters/{character_id}/location",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_background_character_location(character_id: str, db: db_dep):
    deleted = await db.character.remove_background_character_location(character_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Background character {character_id} not found")


@background_character_router.put("/background-characters/{character_id}/landmark", response_model=BackgroundCharacter)
async def set_background_character_landmark(
        character_id: str,
        landmark_data: BackgroundCharacterLandmarkUpdate,
        db: db_dep,
):
    if not await db.character.get_background_character(character_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Background character {character_id} not found")
    if not await db.location.get_landmark(landmark_data.landmark_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Landmark {landmark_data.landmark_id} not found")

    return await db.character.anchor_background_character_to_landmark(character_id, landmark_data.landmark_id)


@background_character_router.delete(
    "/background-characters/{character_id}/landmark",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_background_character_landmark(character_id: str, db: db_dep):
    deleted = await db.character.remove_background_character_landmark(character_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Background character {character_id} not found")


@background_character_router.post("/worlds/{world_id}/background-characters", response_model=BackgroundCharacter)
async def create_background_character_in_world(
        world_id: str,
        character_data: BackgroundCharacterCreate,
        db: db_dep,
):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    await validate_background_character_relationships(character_data, db)

    character = BackgroundCharacter(
        name=character_data.name,
        description=character_data.description,
    )
    created_character = await db.character.create_background_character(
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


@background_character_router.post(
    "/simulations/{simulation_id}/background-characters",
    response_model=BackgroundCharacter,
)
async def create_background_character_in_simulation(
        simulation_id: str,
        character_data: BackgroundCharacterCreate,
        db: db_dep,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    await validate_background_character_relationships(character_data, db)

    character = BackgroundCharacter(
        name=character_data.name,
        description=character_data.description,
    )
    created_character = await db.character.create_background_character(
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
