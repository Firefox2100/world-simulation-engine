from fastapi import APIRouter, HTTPException
from starlette import status

from world_simulation_engine.model.connection_profile import LlmConnectionProfile, LlmConnectionCreate, \
    LlmConnectionProfilePatch
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


@connection_router.get("/llm/{connection_id}", response_model=LlmConnectionProfile)
async def get_llm_connection(connection_id: int,
                             db: db_dep,
                             ):
    """
    Get a LLM connection
    \f
    :param connection_id: The ID of the connection to retrieve
    :param db: The database connection
    :return: The LLM connection details
    """
    result = await db.connection.llm.get(connection_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection with ID {connection_id} not found"
        )

    return result


@connection_router.patch("/llm/{connection_id}", response_model=LlmConnectionProfile)
async def patch_llm_connection(connection_id: int,
                               connection: LlmConnectionProfilePatch,
                               db: db_dep,
                               ):
    """
    Update an existing LLM connection profile.
    \f
    :param connection_id: ID of the connection to update
    :param connection: The connection details
    :param db: The database connection
    :return: An updated connection details
    """
    await db.connection.llm.update(
        connection_id=connection_id,
        patched_data=connection.model_dump(mode="json", exclude_unset=True),
    )

    current_connection = await db.connection.llm.get(connection_id)

    return current_connection


@connection_router.delete("/llm/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_connection(connection_id: int,
                                db: db_dep,
                                ):
    """
    Delete an existing LLM connection profile.
    \f
    :param connection_id: ID of the connection to delete
    :param db: The database connection
    :return: An updated connection details
    """
    await db.connection.llm.delete(connection_id)
