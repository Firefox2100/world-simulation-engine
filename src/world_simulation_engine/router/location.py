from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.component.image_generator import LocationImageGenerator, \
    schedule_cover_image_generation
from world_simulation_engine.model import Location
from .utils import db_dep, prompt_loader_dep, storage_dep, workflow_loader_dep


location_router = APIRouter(
    tags=["Location"],
)


class LocationCreate(BaseModel):
    """
    DTO model for creating a location
    """

    name: str = Field(
        ...,
        description="Name of the location",
    )
    description: str = Field(
        ...,
        description="Description of the location",
    )


class LocationUpdate(BaseModel):
    """
    DTO model for updating a location
    """

    name: Optional[str] = Field(
        None,
        description="Name of the location",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the location",
    )


@location_router.get("/locations", response_model=list[Location])
async def list_locations(db: db_dep,
                         world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                         simulation_id: Optional[str] = Query(
                             None,
                             description="Optionally filter by simulation"
                         ),
                         region_id: Optional[str] = Query(
                             None,
                             description="Optionally filter by larger locations"
                         )):
    return await db.location.list_locations(
        world_id=world_id,
        simulation_id=simulation_id,
        region_id=region_id,
    )


@location_router.get("/locations/{location_id}", response_model=Location)
async def get_location(location_id: str, db: db_dep):
    location = await db.location.get_location(location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    return location


@location_router.patch("/locations/{location_id}", response_model=Location)
async def update_location(location_id: str, location_data: LocationUpdate, db: db_dep):
    location = await db.location.update_location(
        location_id,
        location_data.model_dump(exclude_unset=True),
    )
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    return location


@location_router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(location_id: str, db: db_dep):
    deleted = await db.location.delete_location(location_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )


@location_router.post("/worlds/{world_id}/locations", response_model=Location)
async def create_location_in_world(
        world_id: str,
        location_data: LocationCreate,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
        background_tasks: BackgroundTasks,
):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    location = Location(**location_data.model_dump())
    created_location = await db.location.create_location(location, world_id)
    if not created_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    schedule_cover_image_generation(
        background_tasks,
        generator=LocationImageGenerator(
            database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
        ),
        source_id=world_id,
        entity_id=created_location.id,
    )

    return created_location


@location_router.post("/simulations/{simulation_id}/locations", response_model=Location)
async def create_location_in_simulation(
        simulation_id: str,
        location_data: LocationCreate,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
        background_tasks: BackgroundTasks,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    location = Location(**location_data.model_dump())
    created_location = await db.location.create_location(location, simulation_id)
    if not created_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    schedule_cover_image_generation(
        background_tasks,
        generator=LocationImageGenerator(
            database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
        ),
        source_id=simulation_id,
        entity_id=created_location.id,
    )

    return created_location


@location_router.post("/locations/{location_id}/locations", response_model=Location)
async def create_sub_location(location_id: str, location_data: LocationCreate, db: db_dep):
    parent = await db.location.get_location(location_id)
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    location = Location(**location_data.model_dump())
    created_location = await db.location.create_sub_location(location, location_id)
    if not created_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    return created_location
