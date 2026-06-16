from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from world_simulation_engine.model import Simulation
from .utils import db_dep, turn_runner_dep


simulation_router = APIRouter(
    prefix="/simulations",
    tags=["Simulation"],
)


class RunSimulationRequest(BaseModel):
    user_input: Optional[str] = Field(
        None,
        description="The user input of this turn."
    )


class RunSimulationResponse(BaseModel):
    run_id: str = Field(
        ...,
        description="The run id of this turn, used to retrieve the result of the turn."
    )


@simulation_router.get("", response_model=list[Simulation])
async def list_simulations(db: db_dep):
    """
    List all simulations in the database
    \f
    :param db: The database dependency to fetch simulations
    :return: A list of simulations
    """
    simulations = await db.simulation.list()

    return simulations


@simulation_router.post("/runs/{run_id}/events")
async def stream_run_events(run_id: str,
                            turn_runner: turn_runner_dep,
                            ):
    if not turn_runner.has_run(run_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with id {run_id} not found",
        )

    return StreamingResponse(
        turn_runner.events(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@simulation_router.get("/{simulation_id}", response_model=Simulation)
async def get_simulation(simulation_id: int,
                         db: db_dep,
                         ):
    simulation = await db.simulation.get(simulation_id)

    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation with id {simulation_id} not found",
        )

    return simulation


@simulation_router.post("/{simulation_id}/input", response_model=RunSimulationResponse)
async def run_simulation(simulation_id: int,
                         run_request: RunSimulationRequest,
                         turn_runner: turn_runner_dep
                         ):
    run_id = await turn_runner.start(
        input_data={
            "simulation_id": simulation_id,
            "user_input": run_request.user_input,
        },
        run_name="turn_generator",
        metadata={
            "simulation_id": simulation_id,
        },
        tags=["turn-generator", "simulation"],
    )

    return RunSimulationResponse(
        run_id=run_id,
    )
