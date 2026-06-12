from contextlib import asynccontextmanager
from fastapi import FastAPI

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.component import TurnGenerator, WorkflowRunner
from world_simulation_engine.router import connection_router, simulation_router, world_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_service = DatabaseService(
        database_path=CONFIG.database_path,
    )

    turn_generator = TurnGenerator(
        database_service=database_service,
    )
    turn_generator_graph = turn_generator.build_graph()

    turn_runner = WorkflowRunner(
        graph=turn_generator_graph,
    )

    app.state.database_service = database_service
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
