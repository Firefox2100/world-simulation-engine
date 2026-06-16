from contextlib import asynccontextmanager
from fastapi import FastAPI
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.service import DatabaseService, StorageService
from world_simulation_engine.component import TurnGenerator, WorkflowRunner
from world_simulation_engine.router import connection_router, simulation_router, world_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_service = DatabaseService(
        database_path=CONFIG.database_path,
    )
    storage_service = StorageService(
        base_path=CONFIG.data_folder,
    )

    turn_generator = TurnGenerator(
        database_service=database_service,
    )
    turn_generator_graph = turn_generator.build_graph()

    _ = Langfuse()
    langfuse_handler = CallbackHandler()

    turn_runner = WorkflowRunner(
        graph=turn_generator_graph,
        langfuse_handler=langfuse_handler,
        callback=turn_generator.persist_state_to_database,
    )

    app.state.database_service = database_service
    app.state.storage_service = storage_service
    app.state.turn_runner = turn_runner

    try:
        await database_service.init()

        yield
    finally:
        await database_service.close()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    app.include_router(connection_router)
    app.include_router(simulation_router)
    app.include_router(world_router)

    return app


app = create_app()
