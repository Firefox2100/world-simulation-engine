from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience
from world_simulation_engine.model import MemoryAtom
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink
from .utils import db_dep


memory_router = APIRouter(
    tags=["Memory"],
)


class MemoryCharacterLinkCreate(BaseModel):
    character_id: str = Field(..., description="Character that remembers the memory")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in the memory")
    salience: Salience = Field(..., description="Memory salience")
    behavioural_relevance: Optional[str] = Field(None, description="Why the memory matters behaviourally")
    stance: MemoryStance = Field(..., description="How the character treats the memory")


class MemoryCreate(BaseModel):
    summary: str = Field(..., description="A brief summary of the memory content")
    keywords: list[str] = Field(..., description="Keywords associated with the memory")
    embedding: Optional[list[float]] = Field(None, description="Optional embedding of the keywords")
    event_id: str = Field(..., description="Event that supports this memory")
    support_type: MemorySupportType = Field(..., description="How the event supports this memory")
    character_links: list[MemoryCharacterLinkCreate] = Field(
        ...,
        description="Characters that remember this memory",
    )


class MemoryUpdate(BaseModel):
    summary: Optional[str] = Field(None, description="A brief summary of the memory content")
    keywords: Optional[list[str]] = Field(None, description="Keywords associated with the memory")
    embedding: Optional[list[float]] = Field(None, description="Optional embedding of the keywords")


class MemoryEventUpdate(BaseModel):
    event_id: str = Field(..., description="Event that supports this memory")
    support_type: MemorySupportType = Field(..., description="How the event supports this memory")


class MemoryCharacterRelationshipUpdate(BaseModel):
    character_links: list[MemoryCharacterLinkCreate] = Field(
        ...,
        description="Characters that remember this memory",
    )


class MemoryCharacterRelationshipDelete(BaseModel):
    character_ids: list[str] = Field(..., description="Character ids to unlink from the memory")


def _to_memory_links(character_links: list[MemoryCharacterLinkCreate]) -> list[CharacterMemoryLink]:
    return [
        CharacterMemoryLink(**character_link.model_dump())
        for character_link in character_links
    ]


async def _validate_event(event_id: str, db: db_dep):
    if not await db.event.get_event(event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )


async def _validate_character_links(character_links: list[MemoryCharacterLinkCreate], db: db_dep):
    if not character_links:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory must be attached to at least one character",
        )

    for character_link in character_links:
        if not await db.character.get_character(character_link.character_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character {character_link.character_id} not found",
            )


@memory_router.get("/memories", response_model=list[MemoryAtom])
async def list_memories(
        db: db_dep,
        character_id: Optional[str] = Query(None, description="Optionally filter by character"),
        event_id: Optional[str] = Query(None, description="Optionally filter by event"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
):
    return await db.memory.list_memories(
        character_id=character_id,
        event_id=event_id,
        simulation_id=simulation_id,
    )


@memory_router.get("/memories/{memory_id}", response_model=MemoryAtom)
async def get_memory(memory_id: str, db: db_dep):
    memory = await db.memory.get_memory(memory_id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return memory


@memory_router.post("/memories", response_model=MemoryAtom)
async def create_memory(memory_data: MemoryCreate, db: db_dep):
    await _validate_event(memory_data.event_id, db)
    await _validate_character_links(memory_data.character_links, db)

    memory = MemoryAtom(
        summary=memory_data.summary,
        keywords=memory_data.keywords,
        embedding=memory_data.embedding,
    )
    try:
        return await db.memory.create_memory_atom(
            memory=memory,
            event_id=memory_data.event_id,
            support_type=memory_data.support_type,
            character_links=_to_memory_links(memory_data.character_links),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@memory_router.patch("/memories/{memory_id}", response_model=MemoryAtom)
async def update_memory(memory_id: str, memory_data: MemoryUpdate, db: db_dep):
    memory = await db.memory.update_memory(
        memory_id,
        memory_data.model_dump(exclude_unset=True),
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return memory


@memory_router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(memory_id: str, db: db_dep):
    deleted = await db.memory.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )


@memory_router.put("/memories/{memory_id}/event", response_model=MemoryAtom)
async def set_memory_event(memory_id: str, event_data: MemoryEventUpdate, db: db_dep):
    if not await db.memory.get_memory(memory_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    await _validate_event(event_data.event_id, db)

    memory = await db.memory.link_memory_event(
        memory_id,
        event_data.event_id,
        event_data.support_type,
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return memory


@memory_router.put("/memories/{memory_id}/characters", response_model=MemoryAtom)
async def set_memory_characters(
        memory_id: str,
        character_data: MemoryCharacterRelationshipUpdate,
        db: db_dep,
):
    if not await db.memory.get_memory(memory_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    await _validate_character_links(character_data.character_links, db)

    try:
        memory = await db.memory.replace_character_memories(
            memory_id,
            _to_memory_links(character_data.character_links),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )

    return memory


@memory_router.delete("/memories/{memory_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_characters(
        memory_id: str,
        character_data: MemoryCharacterRelationshipDelete,
        db: db_dep,
):
    if not await db.memory.get_memory(memory_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory {memory_id} not found",
        )
    for character_id in character_data.character_ids:
        if not await db.character.get_character(character_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character {character_id} not found",
            )

    deleted = await db.memory.remove_character_memories(memory_id, character_data.character_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory must be attached to at least one character",
        )
