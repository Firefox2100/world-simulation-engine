from contextlib import asynccontextmanager
from neo4j import AsyncGraphDatabase
from fastapi import FastAPI

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.service import DatabaseService


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = DatabaseService(
        driver=AsyncGraphDatabase.driver(
            uri=CONFIG.neo4j_uri,
            auth=(CONFIG.neo4j_username, CONFIG.neo4j_password),
        )
    )

    app.state.database = database

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
    )

    return app


app = create_app()
