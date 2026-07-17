from typing import Annotated
from fastapi import Depends, Request

from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.storage_service import StorageService
from world_simulation_engine.component.simulator.world_simulator import WorldSimulator


def get_database_service(request: Request) -> DatabaseService:
    return request.app.state.database


def get_world_simulator(request: Request) -> WorldSimulator:
    return request.app.state.world_simulator


def get_storage_service(request: Request) -> StorageService:
    return request.app.state.storage


db_dep = Annotated[DatabaseService, Depends(get_database_service)]
storage_dep = Annotated[StorageService, Depends(get_storage_service)]
simulator_dep = Annotated[WorldSimulator, Depends(get_world_simulator)]
