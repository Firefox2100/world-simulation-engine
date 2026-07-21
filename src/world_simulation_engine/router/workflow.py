import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import WORKFLOW_NAMES, WORKFLOWS
from world_simulation_engine.model import WorkflowMediaFile
from .utils import db_dep, storage_dep


workflow_router = APIRouter(
    tags=["Workflow"],
)


class WorkflowWrite(BaseModel):
    workflow: dict[str, Any] = Field(
        ...,
        description="Workflow data using the package workflow JSON structure",
    )
    workflow_name: str = Field(
        ...,
        description="Name of the workflow in package workflow data",
    )
    title: Optional[str] = Field(
        None,
        description="Title of the workflow media file",
    )
    filename: Optional[str] = Field(
        None,
        description="Filename of the workflow media file, no format suffix",
    )


class WorkflowUpdate(BaseModel):
    workflow: Optional[dict[str, Any]] = Field(
        None,
        description="Workflow data using the package workflow JSON structure",
    )
    workflow_name: Optional[str] = Field(
        None,
        description="Name of the workflow in package workflow data",
    )
    title: Optional[str] = Field(
        None,
        description="Title of the workflow media file",
    )
    filename: Optional[str] = Field(
        None,
        description="Filename of the workflow media file, no format suffix",
    )


class WorkflowAssignmentUpdate(BaseModel):
    workflow_name: str = Field(..., description="Workflow usage to assign")
    media_id: Optional[str] = Field(None, description="Workflow media id, or null to clear the assignment")


class WorkflowAssignmentBatchUpdate(BaseModel):
    assignments: list[WorkflowAssignmentUpdate] = Field(
        default_factory=list,
        description="Workflow assignments to apply",
    )


class WorkflowAssignment(BaseModel):
    workflow_name: str
    workflow: Optional[WorkflowMediaFile] = None


def _validate_workflow_name(workflow_name: str) -> None:
    if workflow_name not in WORKFLOW_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported workflow name {workflow_name}",
        )


async def _validate_world(world_id: str, db: db_dep) -> None:
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


async def _validate_simulation(simulation_id: str, db: db_dep) -> None:
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


def _workflow_content(workflow: dict[str, Any]) -> bytes:
    return json.dumps(
        workflow,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


async def _delete_file_if_unreferenced(media: WorkflowMediaFile,
                                       db: db_dep,
                                       storage: storage_dep,
                                       ) -> None:
    deleted = await db.media.delete_media(media.id)
    if not deleted:
        return

    deleted_media, remaining_hash_references = deleted
    if remaining_hash_references == 0:
        await storage.delete(deleted_media.hash, missing_ok=True)


async def _list_workflow_assignments(source_id: str, db: db_dep) -> list[WorkflowAssignment]:
    workflows = await db.media.list_workflow_media(simulation_id=source_id)
    if not workflows:
        workflows = await db.media.list_workflow_media(world_id=source_id)

    return [
        WorkflowAssignment(
            workflow_name=workflow.workflow_name,
            workflow=workflow,
        )
        for workflow in workflows
    ]


async def _apply_workflow_assignments(source_id: str,
                                      assignments: list[WorkflowAssignmentUpdate],
                                      db: db_dep,
                                      ) -> None:
    for assignment in assignments:
        _validate_workflow_name(assignment.workflow_name)

        if assignment.media_id:
            media = await db.media.get_media(assignment.media_id)
            if not isinstance(media, WorkflowMediaFile):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow media {assignment.media_id} not found",
                )
            if media.workflow_name != assignment.workflow_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Workflow media {assignment.media_id} does not match requested assignment",
                )

            linked = await db.media.set_workflow_media(source_id, assignment.media_id)
            if not linked:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow source {source_id} or media {assignment.media_id} not found",
                )
        else:
            await db.media.remove_workflow_media(
                source_id=source_id,
                workflow_name=assignment.workflow_name,
                delete_media=False,
            )


@workflow_router.get("/workflows", response_model=list[WorkflowMediaFile])
async def list_workflows(
        db: db_dep,
        workflow_name: Optional[str] = Query(None, description="Optionally filter by workflow name"),
):
    if workflow_name is not None:
        _validate_workflow_name(workflow_name)

    return await db.media.list_workflow_media(
        workflow_name=workflow_name,
    )


@workflow_router.get("/workflows/builtin/{workflow_name}", response_model=dict[str, Any])
async def get_builtin_workflow(workflow_name: str):
    _validate_workflow_name(workflow_name)
    return WORKFLOWS[workflow_name]


@workflow_router.get("/workflows/{media_id}", response_model=WorkflowMediaFile)
async def get_workflow(media_id: str, db: db_dep):
    media = await db.media.get_media(media_id)
    if not isinstance(media, WorkflowMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow media {media_id} not found",
        )

    return media


@workflow_router.get("/workflows/{media_id}/data", response_model=dict[str, Any])
async def get_workflow_data(media_id: str, db: db_dep, storage: storage_dep):
    media = await db.media.get_media(media_id)
    if not isinstance(media, WorkflowMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow media {media_id} not found",
        )

    content = await storage.get_bytes(media.hash)
    return json.loads(content.decode("utf-8"))


@workflow_router.post("/workflows", response_model=WorkflowMediaFile, status_code=status.HTTP_201_CREATED)
async def create_workflow(workflow: WorkflowWrite, db: db_dep, storage: storage_dep):
    _validate_workflow_name(workflow.workflow_name)
    stored = await storage.save_bytes(_workflow_content(workflow.workflow))
    media = WorkflowMediaFile(
        title=workflow.title,
        hash=stored.digest,
        filename=workflow.filename or workflow.workflow_name,
        workflow_name=workflow.workflow_name,
    )
    return await db.media.create_media(media)


@workflow_router.patch("/workflows/{media_id}", response_model=WorkflowMediaFile)
async def update_workflow(media_id: str, workflow: WorkflowUpdate, db: db_dep, storage: storage_dep):
    existing = await db.media.get_media(media_id)
    if not isinstance(existing, WorkflowMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow media {media_id} not found",
        )

    properties = workflow.model_dump(
        exclude_unset=True,
        exclude={"workflow"},
    )
    if "workflow_name" in properties:
        _validate_workflow_name(properties["workflow_name"])

    previous_hash = existing.hash
    if workflow.workflow is not None:
        stored = await storage.save_bytes(_workflow_content(workflow.workflow))
        properties["hash"] = stored.digest

    updated = await db.media.update_media(media_id, properties)
    if not isinstance(updated, WorkflowMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow media {media_id} not found",
        )

    if workflow.workflow is not None and previous_hash != updated.hash:
        still_used = await db.media.list_media(media_type=None)
        if not any(media.hash == previous_hash for media in still_used):
            await storage.delete(previous_hash, missing_ok=True)

    return updated


@workflow_router.delete("/workflows/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(media_id: str, db: db_dep, storage: storage_dep):
    media = await db.media.get_media(media_id)
    if not isinstance(media, WorkflowMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow media {media_id} not found",
        )

    await _delete_file_if_unreferenced(media, db, storage)


@workflow_router.get("/worlds/{world_id}/workflow-connections", response_model=list[WorkflowAssignment])
async def list_world_workflow_connections(world_id: str, db: db_dep):
    await _validate_world(world_id, db)
    return await _list_workflow_assignments(world_id, db)


@workflow_router.put("/worlds/{world_id}/workflow-connections", response_model=list[WorkflowAssignment])
async def set_world_workflow_connections(
        world_id: str,
        workflow_update: WorkflowAssignmentBatchUpdate,
        db: db_dep,
):
    await _validate_world(world_id, db)
    await _apply_workflow_assignments(world_id, workflow_update.assignments, db)
    return await _list_workflow_assignments(world_id, db)


@workflow_router.get("/simulations/{simulation_id}/workflow-connections", response_model=list[WorkflowAssignment])
async def list_simulation_workflow_connections(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)
    return await _list_workflow_assignments(simulation_id, db)


@workflow_router.put("/simulations/{simulation_id}/workflow-connections", response_model=list[WorkflowAssignment])
async def set_simulation_workflow_connections(
        simulation_id: str,
        workflow_update: WorkflowAssignmentBatchUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)
    await _apply_workflow_assignments(simulation_id, workflow_update.assignments, db)
    return await _list_workflow_assignments(simulation_id, db)


@workflow_router.get("/simulations/{simulation_id}/workflows/{workflow_name}", response_model=dict[str, Any])
async def get_simulation_workflow(
        simulation_id: str,
        workflow_name: str,
        db: db_dep,
        storage: storage_dep,
):
    await _validate_simulation(simulation_id, db)
    _validate_workflow_name(workflow_name)

    media = await db.media.get_workflow_media(
        simulation_id=simulation_id,
        workflow_name=workflow_name,
    )
    if media:
        content = await storage.get_bytes(media.hash)
        return json.loads(content.decode("utf-8"))

    return WORKFLOWS[workflow_name]
