from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import Turn
from .utils import db_dep


turn_router = APIRouter(
    tags=["Turn"],
)


class TurnCreate(BaseModel):
    sequence: int = Field(..., ge=1, description="The sequence number of the turn, starting at 1")
    type: TurnType = Field(..., description="The type of the turn")
    content: str = Field(..., min_length=1, description="The final, visible content of this turn")
    start_time: datetime = Field(..., description="The start time of the turn")


@turn_router.get("/turns", response_model=list[Turn])
async def list_turns(db: db_dep,
                     simulation_id: str = Query(
                         ...,
                         description="The simulation id of the simulation to get turns from",
                     ),
                     limit: int = Query(
                         10,
                         description="Maximum turns to return, default to 10",
                         ge=1,
                     ),
                     skip: int = Query(
                         0,
                         description="How many turns to skip, default to 0",
                         ge=0,
                     )
                     ):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return await db.turn.list_turns(
        source_id=simulation_id,
        limit=limit,
        skip=skip,
    )


@turn_router.post("/worlds/{world_id}/turns", response_model=Turn)
async def create_world_turn(world_id: str, turn_data: TurnCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    latest_turns = await db.turn.list_turns(source_id=world_id, limit=1)
    previous_turn = latest_turns[0] if latest_turns else None
    expected_sequence = previous_turn.sequence + 1 if previous_turn else 1
    if turn_data.sequence != expected_sequence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Turn sequence must be {expected_sequence}",
        )

    try:
        return await db.turn.create_turn(
            Turn(**turn_data.model_dump()),
            world_id,
            previous_turn_id=previous_turn.id if previous_turn else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@turn_router.get("/turns/{turn_id}", response_model=Turn)
async def get_turn(turn_id: str, db: db_dep):
    turn = await db.turn.get_turn(turn_id)
    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turn {turn_id} not found",
        )

    return turn


@turn_router.get("/simulations/{simulation_id}/turns/{sequence}", response_model=Turn)
async def get_turn_by_sequence(simulation_id: str, sequence: int, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    turn = await db.turn.get_turn_by_sequence(simulation_id, sequence)
    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turn {sequence} not found in simulation {simulation_id}",
        )

    return turn
