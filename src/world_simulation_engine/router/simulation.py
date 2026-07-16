from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Simulation
from .utils import db_dep


simulation_router = APIRouter(
    tags=["Simulation"],
)


class SimulationUpdate(BaseModel):
    """
    DTO model for updating a simulation
    """
    name: Optional[str] = Field(
        None,
        description="Name of the simulation",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the simulation",
    )
    current_time: Optional[datetime] = Field(
        None,
        description="Current time of the simulation",
    )


@simulation_router.get("/simulations", response_model=list[Simulation])
async def list_simulations(db: db_dep,
                           author_id: Optional[str] = Query(None, description="Optionally filter by author"),
                           world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                           ):
    return await db.simulation.list_simulations(
        author_id=author_id,
        world_id=world_id,
    )


@simulation_router.get("/simulations/{simulation_id}", response_model=Simulation)
async def get_simulation(simulation_id: str, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return simulation


@simulation_router.patch("/simulations/{simulation_id}", response_model=Simulation)
async def update_simulation(simulation_id: str, simulation_update: SimulationUpdate, db: db_dep):
    simulation = await db.simulation.update_simulation(
        simulation_id,
        simulation_update.model_dump(exclude_unset=True),
    )
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return simulation


@simulation_router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation(simulation_id: str, db: db_dep):
    deleted = await db.simulation.delete_simulation(simulation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@simulation_router.post("/worlds/{world_id}/simulations", response_model=Simulation)
async def create_simulation(world_id: str, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    simulation = Simulation(
        name=world.name,
        description=world.description,
        current_time=world.starting_time,
    )
    created_simulation = await db.simulation.create_simulation(simulation, world_id)
    if not created_simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
    _, location_pairs, landmark_pairs = await db.location.copy_locations(
        world_id,
        created_simulation.id,
    )
    _, character_pairs = await db.character.copy_characters(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        landmark_pairs=landmark_pairs,
        return_pairs=True,
    )
    _, background_character_pairs = await db.character.copy_background_characters(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        landmark_pairs=landmark_pairs,
    )
    await db.equipment.copy_equipment(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        entity_pairs=character_pairs + background_character_pairs,
    )

    return created_simulation
