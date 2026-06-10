from fastapi import APIRouter

from world_simulation_engine.model import Simulation
from .utils import db_dep


simulation_router = APIRouter(
    prefix="/simulations",
    tags=["Simulation"],
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
