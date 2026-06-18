from typing import Annotated
from fastapi import Request, Depends

from world_simulation_engine.service import DatabaseService, StorageService
from world_simulation_engine.component import WorkflowRunner, SillyTavernImporter


def get_database_service(request: Request) -> DatabaseService:
    return request.app.state.database_service


def get_storage_service(request: Request) -> StorageService:
    return request.app.state.storage_service


def get_turn_runner(request: Request) -> WorkflowRunner:
    return request.app.state.turn_runner


def get_silly_tavern_importer(request: Request) -> SillyTavernImporter:
    return request.app.state.silly_tavern_importer


db_dep = Annotated[DatabaseService, Depends(get_database_service)]
storage_dep = Annotated[StorageService, Depends(get_storage_service)]
turn_runner_dep = Annotated[WorkflowRunner, Depends(get_turn_runner)]
st_importer_dep = Annotated[SillyTavernImporter, Depends(get_silly_tavern_importer)]
