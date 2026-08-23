from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import TriggerEffectKind, TriggerStatus
from world_simulation_engine.model import GateEffect, Trigger, TriggerCondition, TriggerEffectPayload
from .utils import db_dep


trigger_router = APIRouter(
    tags=["Trigger"],
)


class TriggerCreate(BaseModel):
    """DTO model for creating a trigger. Runtime-state fields (status, last_condition_result,
    last_fired_turn_id, last_evaluated_turn_id) are server-managed and not accepted here."""

    source_id: str = Field(..., description="The World or Simulation this trigger belongs to")
    name: str = Field(..., min_length=1, description="Author-facing label, never shown to any LLM")
    description: str = Field("", description="Author-facing notes, never shown to any LLM")
    condition: TriggerCondition
    effect_kind: TriggerEffectKind
    effects: list[TriggerEffectPayload] = Field(default_factory=list, max_length=3)
    gate_effect: Optional[GateEffect] = None
    chance: Optional[float] = Field(None, ge=0, le=1)
    repeatable: bool = False
    cooldown_turns: Optional[int] = Field(None, ge=1)
    reversible: bool = True


class TriggerUpdate(BaseModel):
    """DTO model for replacing a trigger's authored definition. Runtime-state fields are left
    untouched by this endpoint - use the (future) status-only endpoints for those."""

    name: str = Field(..., min_length=1)
    description: str = ""
    condition: TriggerCondition
    effect_kind: TriggerEffectKind
    effects: list[TriggerEffectPayload] = Field(default_factory=list, max_length=3)
    gate_effect: Optional[GateEffect] = None
    chance: Optional[float] = Field(None, ge=0, le=1)
    repeatable: bool = False
    cooldown_turns: Optional[int] = Field(None, ge=1)
    reversible: bool = True


@trigger_router.get("/triggers", response_model=list[Trigger])
async def list_triggers(
        db: db_dep,
        source_id: Optional[str] = Query(None, description="Optionally filter by owning World/Simulation"),
        status_filter: Optional[TriggerStatus] = Query(None, alias="status", description="Optionally filter by status"),
):
    return await db.trigger.list_triggers(source_id=source_id, status=status_filter)


@trigger_router.get("/triggers/{trigger_id}", response_model=Trigger)
async def get_trigger(trigger_id: str, db: db_dep):
    trigger = await db.trigger.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found",
        )
    return trigger


@trigger_router.post("/triggers", response_model=Trigger)
async def create_trigger(trigger_data: TriggerCreate, db: db_dep):
    if not await db.world.get_world(trigger_data.source_id) and not await db.simulation.get_simulation(trigger_data.source_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World or Simulation {trigger_data.source_id} not found",
        )

    trigger = Trigger(**trigger_data.model_dump())
    created = await db.trigger.create_trigger(trigger)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World or Simulation {trigger_data.source_id} not found",
        )
    return created


@trigger_router.put("/triggers/{trigger_id}", response_model=Trigger)
async def update_trigger(trigger_id: str, trigger_data: TriggerUpdate, db: db_dep):
    existing = await db.trigger.get_trigger(trigger_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found",
        )

    # Trigger.model_copy() does not re-run validators, so build via model_validate() instead -
    # otherwise an update that violates _validate_effect_shape (e.g. a GATE trigger with non-empty
    # effects) would silently bypass that check.
    candidate = Trigger.model_validate({**existing.model_dump(mode="json"), **trigger_data.model_dump(mode="json")})
    updated = await db.trigger.update_trigger(candidate)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found",
        )
    return updated


@trigger_router.patch("/triggers/{trigger_id}/status", response_model=Trigger)
async def set_trigger_status(trigger_id: str, trigger_status: TriggerStatus, db: db_dep):
    """Manually arm/disable a trigger without touching its definition or condition history."""
    existing = await db.trigger.get_trigger(trigger_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found",
        )

    updated = await db.trigger.update_trigger_runtime_state(
        trigger_id=trigger_id,
        status=trigger_status,
        last_condition_result=existing.last_condition_result,
        last_evaluated_turn_id=existing.last_evaluated_turn_id,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found",
        )
    return updated


@trigger_router.delete("/triggers/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(trigger_id: str, db: db_dep):
    deleted = await db.trigger.delete_trigger(trigger_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trigger {trigger_id} not found",
        )
