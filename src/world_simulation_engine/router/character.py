from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Character, CurrentActivity
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


@character_router.get("/characters", response_model=list[Character])
async def list_characters(db: db_dep,
                          world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                          simulation_id: Optional[str] = Query(
                              None,
                              description="Optionally filter by simulation"
                          )):
    return await db.character.list_characters(
        world_id=world_id,
        simulation_id=simulation_id,
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
    character = await db.character.update_character(
        character_id,
        character_data.model_dump(exclude_unset=True),
    )
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    return character


@character_router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(character_id: str, db: db_dep):
    deleted = await db.character.delete_character(character_id)
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

    character = Character(**character_data.model_dump())
    created_character = await db.character.create_character(character, world_id)
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

    character = Character(**character_data.model_dump())
    created_character = await db.character.create_character(character, simulation_id)
    if not created_character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return created_character
