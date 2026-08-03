from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import EntityVariableSet, PhysicalEntityType, VariableDefinition
from .utils import db_dep


variable_router = APIRouter(
    tags=["Variable"],
)


class EntityVariableSetUpsert(BaseModel):
    """DTO model for replacing an entity's full set of tracked variables."""

    source_id: str = Field(..., description="The World or Simulation this entity belongs to")
    owner_type: PhysicalEntityType = Field(..., description="The kind of entity this variable set belongs to")
    variables: list[VariableDefinition] = Field(
        default_factory=list,
        description="The full replacement set of tracked variables for this entity",
    )


@variable_router.get("/entities/{owner_id}/variables", response_model=EntityVariableSet)
async def get_entity_variables(owner_id: str, db: db_dep):
    variable_set = await db.variable.get_variable_set(owner_id)
    if not variable_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {owner_id} has no tracked variables",
        )
    return variable_set


@variable_router.put("/entities/{owner_id}/variables", response_model=EntityVariableSet)
async def replace_entity_variables(owner_id: str, payload: EntityVariableSetUpsert, db: db_dep):
    if not await db.variable.owner_belongs_to_source(source_id=payload.source_id, owner_id=owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {owner_id} not found in {payload.source_id}",
        )

    existing = await db.variable.get_variable_set(owner_id)
    now = datetime.now(timezone.utc)
    if existing:
        candidate = existing.model_copy(update={
            "variables": payload.variables,
            "last_updated_at": now,
            "version": existing.version + 1,
        })
        stored = await db.variable.update_variable_set(candidate)
    else:
        candidate = EntityVariableSet(
            source_id=payload.source_id,
            owner_type=payload.owner_type,
            owner_id=owner_id,
            variables=payload.variables,
            last_updated_at=now,
        )
        stored = await db.variable.create_variable_set(candidate)

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Variable set changed concurrently; reload and retry",
        )
    return stored
