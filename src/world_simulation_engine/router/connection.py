from fastapi import APIRouter

from world_simulation_engine.model.connection_profile import LlmConnectionProfile, LlmConnectionCreate
from .utils import db_dep


connection_router = APIRouter(
    prefix="/connections",
    tags=["Connection"],
)


@connection_router.get("/llm", response_model=list[LlmConnectionProfile])
async def list_llm_connections(db: db_dep):
    """
    List all LLM connections
    \f
    :param db: The database connection
    :return: A list of all LLM connections
    """
    connections = await db.connection.llm.list()

    return connections


@connection_router.post("/llm", response_model=LlmConnectionProfile)
async def create_llm_connection(connection: LlmConnectionCreate,
                                db: db_dep,
                                ):
    """
    Create a new LLM connection
    \f
    :param connection: The connection details
    :param db: The database connection
    """
    result = await db.connection.llm.create(connection)

    return result
