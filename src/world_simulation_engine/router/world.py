from fastapi import APIRouter

from world_simulation_engine.model.world import World, WorldCreate
from .utils import db_dep


world_router = APIRouter(
    prefix="/worlds",
    tags=["World"],
)


@world_router.get("", response_model=list[World])
async def list_worlds(db: db_dep):
    worlds = await db.world.list()

    return worlds


@world_router.post("", response_model=World)
async def create_world(world_create: WorldCreate,
                       db: db_dep,
                       ):
    result = await db.world.create(world_create)

    return result
