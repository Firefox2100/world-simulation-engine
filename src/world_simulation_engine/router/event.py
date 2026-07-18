from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import EventInvolvement
from world_simulation_engine.model import Event
from .utils import db_dep


event_router = APIRouter(
    tags=["Event"],
)


class EventCharacterInvolvement(BaseModel):
    character_id: str = Field(
        ...,
        description="The character involved in the event",
    )
    involvement: EventInvolvement = Field(
        ...,
        description="How the character is involved in the event",
    )


class EventCreate(BaseModel):
    """
    DTO model for creating an event
    """

    name: str = Field(
        ...,
        description="The name of the event",
    )
    summary: str = Field(
        ...,
        description="The summary of the event",
    )
    turn_ids: list[str] = Field(
        ...,
        description="Turns this event is part of",
    )
    involved_characters: list[EventCharacterInvolvement] = Field(
        default_factory=list,
        description="Characters involved in the event",
    )


class EventUpdate(BaseModel):
    """
    DTO model for updating an event
    """

    name: Optional[str] = Field(
        None,
        description="The name of the event",
    )
    summary: Optional[str] = Field(
        None,
        description="The summary of the event",
    )
    turn_ids: Optional[list[str]] = Field(
        None,
        description="Additional turns this event is part of",
    )
    involved_characters: Optional[list[EventCharacterInvolvement]] = Field(
        None,
        description="Additional or updated character involvement records",
    )


class EventTurnRelationshipUpdate(BaseModel):
    turn_ids: list[str] = Field(..., description="Turns this event is part of")


class EventCharacterRelationshipUpdate(BaseModel):
    involved_characters: list[EventCharacterInvolvement] = Field(
        ...,
        description="Characters involved in the event",
    )


class EventCharacterRelationshipDelete(BaseModel):
    character_ids: list[str] = Field(..., description="Character ids to remove from the event")


async def validate_event_relationships(
        turn_ids: list[str] | None,
        involved_characters: list[EventCharacterInvolvement] | None,
        db: db_dep,
):
    for turn_id in turn_ids or []:
        turn = await db.turn.get_turn(turn_id)
        if not turn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Turn {turn_id} not found",
            )

    for involvement in involved_characters or []:
        character = await db.character.get_character(involvement.character_id)
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character {involvement.character_id} not found",
            )


async def apply_event_relationships(
        event_id: str,
        turn_ids: list[str] | None,
        involved_characters: list[EventCharacterInvolvement] | None,
        db: db_dep,
) -> Event:
    event = await db.event.get_event(event_id)

    for turn_id in turn_ids or []:
        event = await db.event.add_turn_to_event(event_id, turn_id)

    for involvement in involved_characters or []:
        event = await db.event.add_character_involvement(
            event_id,
            involvement.character_id,
            involvement.involvement,
        )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    return event


async def validate_event_exists(event_id: str, db: db_dep):
    if not await db.event.get_event(event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )


@event_router.get("/events", response_model=list[Event])
async def list_events(
        db: db_dep,
        character_id: Optional[str] = Query(None, description="Optionally filter by character"),
        turn_id: Optional[str] = Query(None, description="Optionally filter by turn"),
):
    return await db.event.list_events(
        character_id=character_id,
        turn_id=turn_id,
    )


@event_router.get("/events/{event_id}", response_model=Event)
async def get_event(event_id: str, db: db_dep):
    event = await db.event.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    return event


@event_router.put("/events/{event_id}/turns", response_model=Event)
async def set_event_turns(
        event_id: str,
        turn_data: EventTurnRelationshipUpdate,
        db: db_dep,
):
    if not turn_data.turn_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event must be attached to at least one turn",
        )
    await validate_event_exists(event_id, db)
    await validate_event_relationships(turn_data.turn_ids, None, db)

    event = await db.event.replace_event_turns(event_id, turn_data.turn_ids)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    return event


@event_router.delete("/events/{event_id}/turns", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_turns(
        event_id: str,
        turn_data: EventTurnRelationshipUpdate,
        db: db_dep,
):
    await validate_event_exists(event_id, db)
    await validate_event_relationships(turn_data.turn_ids, None, db)

    deleted = await db.event.remove_event_turns(event_id, turn_data.turn_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event must be attached to at least one turn",
        )


@event_router.put("/events/{event_id}/characters", response_model=Event)
async def set_event_characters(
        event_id: str,
        character_data: EventCharacterRelationshipUpdate,
        db: db_dep,
):
    await validate_event_exists(event_id, db)
    await validate_event_relationships(None, character_data.involved_characters, db)

    event = await db.event.replace_character_involvements(
        event_id,
        [
            involvement.model_dump()
            for involvement in character_data.involved_characters
        ],
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    return event


@event_router.delete("/events/{event_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_characters(
        event_id: str,
        character_data: EventCharacterRelationshipDelete,
        db: db_dep,
):
    await validate_event_exists(event_id, db)
    for character_id in character_data.character_ids:
        character = await db.character.get_character(character_id)
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character {character_id} not found",
            )

    deleted = await db.event.remove_character_involvements(event_id, character_data.character_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )


@event_router.post("/events", response_model=Event)
async def create_event(event_data: EventCreate, db: db_dep):
    if not event_data.turn_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event must be attached to at least one turn",
        )

    await validate_event_relationships(
        event_data.turn_ids,
        event_data.involved_characters,
        db,
    )

    event = Event(
        name=event_data.name,
        summary=event_data.summary,
    )
    created_event = await db.event.create_event(event, event_data.turn_ids)
    if not created_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more turns were not found",
        )

    return await apply_event_relationships(
        created_event.id,
        None,
        event_data.involved_characters,
        db,
    )


@event_router.patch("/events/{event_id}", response_model=Event)
async def update_event(event_id: str, event_data: EventUpdate, db: db_dep):
    await validate_event_relationships(
        event_data.turn_ids,
        event_data.involved_characters,
        db,
    )

    event = await db.event.update_event(
        event_id,
        name=event_data.name,
        summary=event_data.summary,
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )

    return await apply_event_relationships(
        event_id,
        event_data.turn_ids,
        event_data.involved_characters,
        db,
    )


@event_router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: str, db: db_dep):
    deleted = await db.event.delete_event(event_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )
