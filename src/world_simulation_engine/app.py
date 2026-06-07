from contextlib import asynccontextmanager
from fastapi import FastAPI

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.service import DatabaseService


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_service = DatabaseService(
        database_path=CONFIG.database_path,
    )

    app.state.database_service = database_service

    try:
        await database_service.init()

        yield
    finally:
        await database_service.close()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    return app


app = create_app()
