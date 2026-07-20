from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import IntentHorizon, IntentStatus, IntentType
from world_simulation_engine.model import Intent
from .utils import db_dep


intent_router = APIRouter(
    tags=["Intent"],
)


class IntentCreate(BaseModel):
    """
    DTO model for creating an intent
    """

    type: IntentType = Field(
        ...,
        description="Type of the intent",
    )
    name: str = Field(
        ...,
        description="Name of the intent",
    )
    description: str = Field(
        ...,
        description="Description of the intent",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="A list of keywords for this intent",
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="A list of embeddings for this intent",
    )
    priority: float = Field(
        ...,
        description="Priority of the intent",
        ge=0,
        le=1,
    )
    urgency: float = Field(
        ...,
        description="Urgency of the intent",
        ge=0,
        le=1,
    )
    status: IntentStatus = Field(
        ...,
        description="Current status of the intent",
    )
    desired_state: Optional[str] = Field(
        None,
        description="The state that this intent is trying to achieve",
    )
    success_conditions: list[str] = Field(
        default_factory=list,
        description="The criteria to consider this intent successful",
    )
    failure_conditions: list[str] = Field(
        default_factory=list,
        description="The criteria to consider this intent failed",
    )
    maintenance_conditions: list[str] = Field(
        default_factory=list,
        description="The conditions to maintain this intent",
    )
    deadline: Optional[datetime] = Field(
        None,
        description="The deadline for this intent",
    )
    horizon: IntentHorizon = Field(
        ...,
        description="The horizon for this intent",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints for this intent",
    )
    current_plan: list[str] = Field(
        default_factory=list,
        description="The current plan to achieve this intent",
    )
    next_action_biases: list[str] = Field(
        default_factory=list,
        description="Likely next actions for this intent",
    )
    blockers: list[str] = Field(
        default_factory=list,
        description="Blockers for this intent",
    )
    open_threads: list[str] = Field(
        default_factory=list,
        description="Open threads for this intent",
    )
    created_by_event_id: Optional[str] = Field(
        None,
        description="Optional event that created this intent",
    )
    contributing_event_ids: list[str] = Field(
        default_factory=list,
        description="Optional events that contribute to this intent",
    )


class IntentUpdate(BaseModel):
    """
    DTO model for updating an intent
    """

    type: Optional[IntentType] = Field(None, description="Type of the intent")
    name: Optional[str] = Field(None, description="Name of the intent")
    description: Optional[str] = Field(None, description="Description of the intent")
    keywords: Optional[list[str]] = Field(None, description="A list of keywords for this intent")
    embedding: Optional[list[float]] = Field(None, description="A list of embeddings for this intent")
    priority: Optional[float] = Field(None, description="Priority of the intent", ge=0, le=1)
    urgency: Optional[float] = Field(None, description="Urgency of the intent", ge=0, le=1)
    status: Optional[IntentStatus] = Field(None, description="Current status of the intent")
    desired_state: Optional[str] = Field(None, description="The state that this intent is trying to achieve")
    success_conditions: Optional[list[str]] = Field(None, description="Success criteria")
    failure_conditions: Optional[list[str]] = Field(None, description="Failure criteria")
    maintenance_conditions: Optional[list[str]] = Field(None, description="Maintenance conditions")
    deadline: Optional[datetime] = Field(None, description="The deadline for this intent")
    horizon: Optional[IntentHorizon] = Field(None, description="The horizon for this intent")
    constraints: Optional[list[str]] = Field(None, description="Constraints for this intent")
    current_plan: Optional[list[str]] = Field(None, description="The current plan")
    next_action_biases: Optional[list[str]] = Field(None, description="Likely next actions")
    blockers: Optional[list[str]] = Field(None, description="Blockers for this intent")
    open_threads: Optional[list[str]] = Field(None, description="Open threads for this intent")
    created_by_event_id: Optional[str] = Field(None, description="Optional event that created this intent")
    contributing_event_ids: Optional[list[str]] = Field(None, description="Events contributing to this intent")


class IntentCharacterRelationshipUpdate(BaseModel):
    character_id: str = Field(..., description="Character that holds the intent")


class IntentCreatedByRelationshipUpdate(BaseModel):
    event_id: str = Field(..., description="Event that created the intent")


class IntentContributingEventsRelationshipUpdate(BaseModel):
    event_ids: list[str] = Field(..., description="Events that contribute to the intent")


async def validate_intent_events(
        created_by_event_id: str | None,
        contributing_event_ids: list[str] | None,
        db: db_dep,
):
    event_ids = []
    if created_by_event_id:
        event_ids.append(created_by_event_id)
    event_ids.extend(contributing_event_ids or [])

    for event_id in dict.fromkeys(event_ids):
        event = await db.event.get_event(event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found",
            )


async def apply_intent_event_relationships(
        intent_id: str,
        created_by_event_id: str | None,
        contributing_event_ids: list[str] | None,
        db: db_dep,
) -> Intent:
    intent = await db.intent.get_intent(intent_id)

    if created_by_event_id:
        intent = await db.intent.add_event_creation(created_by_event_id, intent_id)

    for event_id in contributing_event_ids or []:
        intent = await db.intent.add_event_contribution(event_id, intent_id)

    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )

    return intent


async def validate_intent_exists(intent_id: str, db: db_dep):
    if not await db.intent.get_intent(intent_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )


@intent_router.get("/intents", response_model=list[Intent])
async def list_intents(
        db: db_dep,
        character_id: Optional[str] = Query(None, description="Optionally filter by character"),
        event_id: Optional[str] = Query(None, description="Optionally filter by event"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
):
    return await db.intent.list_intents(
        character_id=character_id,
        event_id=event_id,
        simulation_id=simulation_id,
    )


@intent_router.get("/intents/{intent_id}", response_model=Intent)
async def get_intent(intent_id: str, db: db_dep):
    intent = await db.intent.get_intent(intent_id)
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )

    return intent


@intent_router.put("/intents/{intent_id}/character", response_model=Intent)
async def set_intent_character(
        intent_id: str,
        character_data: IntentCharacterRelationshipUpdate,
        db: db_dep,
):
    await validate_intent_exists(intent_id, db)
    if not await db.character.get_character(character_data.character_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_data.character_id} not found",
        )

    intent = await db.intent.move_intent_to_character(intent_id, character_data.character_id)
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )

    return intent


@intent_router.put("/intents/{intent_id}/created-by", response_model=Intent)
async def set_intent_created_by(
        intent_id: str,
        event_data: IntentCreatedByRelationshipUpdate,
        db: db_dep,
):
    await validate_intent_exists(intent_id, db)
    await validate_intent_events(event_data.event_id, None, db)

    intent = await db.intent.add_event_creation(event_data.event_id, intent_id)
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )

    return intent


@intent_router.delete("/intents/{intent_id}/created-by", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intent_created_by(intent_id: str, db: db_dep):
    await validate_intent_exists(intent_id, db)
    deleted = await db.intent.remove_event_creation(intent_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )


@intent_router.put("/intents/{intent_id}/contributing-events", response_model=Intent)
async def set_intent_contributing_events(
        intent_id: str,
        event_data: IntentContributingEventsRelationshipUpdate,
        db: db_dep,
):
    await validate_intent_exists(intent_id, db)
    await validate_intent_events(None, event_data.event_ids, db)

    intent = await db.intent.replace_event_contributions(intent_id, event_data.event_ids)
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )

    return intent


@intent_router.delete("/intents/{intent_id}/contributing-events", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intent_contributing_events(
        intent_id: str,
        event_data: IntentContributingEventsRelationshipUpdate,
        db: db_dep,
):
    await validate_intent_exists(intent_id, db)
    await validate_intent_events(None, event_data.event_ids, db)

    deleted = await db.intent.remove_event_contributions(intent_id, event_data.event_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )


@intent_router.post("/characters/{character_id}/intents", response_model=Intent)
async def create_intent(character_id: str, intent_data: IntentCreate, db: db_dep):
    character = await db.character.get_character(character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    await validate_intent_events(
        intent_data.created_by_event_id,
        intent_data.contributing_event_ids,
        db,
    )

    intent = Intent(
        **intent_data.model_dump(
            exclude={
                "created_by_event_id",
                "contributing_event_ids",
            }
        )
    )
    created_intent = await db.intent.create_intent(intent, character_id)
    if not created_intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    return await apply_intent_event_relationships(
        created_intent.id,
        intent_data.created_by_event_id,
        intent_data.contributing_event_ids,
        db,
    )


@intent_router.patch("/intents/{intent_id}", response_model=Intent)
async def update_intent(intent_id: str, intent_data: IntentUpdate, db: db_dep):
    await validate_intent_events(
        intent_data.created_by_event_id,
        intent_data.contributing_event_ids,
        db,
    )

    properties = intent_data.model_dump(
        exclude_unset=True,
        exclude={"created_by_event_id", "contributing_event_ids"},
    )
    if properties:
        intent = await db.intent.update_intent(
            intent_id=intent_id,
            properties=properties,
        )
    else:
        intent = await db.intent.get_intent(intent_id)
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )

    return await apply_intent_event_relationships(
        intent_id,
        intent_data.created_by_event_id,
        intent_data.contributing_event_ids,
        db,
    )


@intent_router.delete("/intents/{intent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intent(intent_id: str, db: db_dep):
    deleted = await db.intent.delete_intent(intent_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent {intent_id} not found",
        )
