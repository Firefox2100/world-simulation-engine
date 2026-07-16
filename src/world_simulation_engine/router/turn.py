from fastapi import APIRouter, HTTPException, Query, status

from world_simulation_engine.model import Turn
from .utils import db_dep


turn_router = APIRouter(
    tags=["Turn"],
)


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
