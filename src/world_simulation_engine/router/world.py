from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import World
from .utils import db_dep


world_router = APIRouter(
    tags=["World"],
)


class WorldCreate(BaseModel):
    name: str = Field(
        ...,
        description="The name of the world",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the world",
    )
    starting_time: datetime = Field(
        ...,
        description="The starting time for simulations created from the world",
    )

    author_id: str = Field(
        ...,
        description="The author of the world",
    )
    version: int = Field(
        1,
        description="The version of the world, starting at 1",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the world",
    )
    language: SupportedLanguage = Field(
        ...,
        description="The language of the world",
    )


class WorldUpdate(BaseModel):
    """
    DTO model for updating a world data
    """

    name: Optional[str] = Field(
        None,
        description="The name of the world",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the world",
    )
    starting_time: Optional[datetime] = Field(
        None,
        description="The starting time for simulations created from the world",
    )
    version: Optional[int] = Field(
        None,
        description="The version of the world, starting at 1",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the world",
    )
    language: Optional[SupportedLanguage] = Field(
        None,
        description="The language of the world",
    )


@world_router.get("/worlds", response_model=list[World])
async def list_worlds(db: db_dep,
                      author_id: Optional[str] = Query(None, description="Optional filter by author"),
                      limit: Optional[int] = Query(None, ge=1, description="Maximum number of worlds to return"),
                      skip: int = Query(0, ge=0, description="Number of worlds to skip"),
                      ):
    return await db.world.list_worlds(
        author_id=author_id,
        limit=limit,
        skip=skip,
    )


@world_router.post("/worlds", response_model=World)
async def create_world(world_create: WorldCreate, db: db_dep):
    world = World(
        name=world_create.name,
        description=world_create.description,
        starting_time=world_create.starting_time,
        version=world_create.version,
        url=world_create.url,
        language=world_create.language,
    )
    created_world = await db.world.create_world(world, world_create.author_id)
    if not created_world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {world_create.author_id} not found",
        )

    return created_world


@world_router.get("/worlds/{world_id}", response_model=World)
async def get_world(world_id: str, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return world


@world_router.patch("/worlds/{world_id}", response_model=World)
async def update_world(world_id: str, world_update: WorldUpdate, db: db_dep):
    world = await db.world.update_world(
        world_id,
        world_update.model_dump(exclude_unset=True),
    )
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return world


@world_router.delete("/worlds/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world(world_id: str, db: db_dep):
    world = await db.world.delete_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
