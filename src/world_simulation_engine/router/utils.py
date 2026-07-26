from typing import Annotated
from fastapi import Depends, Request

from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.storage_service import StorageService
from world_simulation_engine.component.prompt_loader import PromptLoader
from world_simulation_engine.component.workflow_loader import WorkflowLoader
from world_simulation_engine.component.simulator.world_simulator import WorldSimulator


def get_database_service(request: Request) -> DatabaseService:
    return request.app.state.database


def get_world_simulator(request: Request) -> WorldSimulator:
    return request.app.state.world_simulator


def get_storage_service(request: Request) -> StorageService:
    return request.app.state.storage


def get_prompt_loader(request: Request) -> PromptLoader:
    return request.app.state.prompt_loader


def get_workflow_loader(request: Request) -> WorkflowLoader:
    return request.app.state.workflow_loader


db_dep = Annotated[DatabaseService, Depends(get_database_service)]
storage_dep = Annotated[StorageService, Depends(get_storage_service)]
simulator_dep = Annotated[WorldSimulator, Depends(get_world_simulator)]
prompt_loader_dep = Annotated[PromptLoader, Depends(get_prompt_loader)]
workflow_loader_dep = Annotated[WorkflowLoader, Depends(get_workflow_loader)]
