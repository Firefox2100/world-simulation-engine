from contextlib import asynccontextmanager
from neo4j import AsyncGraphDatabase
from fastapi import FastAPI

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.storage_service import StorageService
from world_simulation_engine.component.prompt_loader import PromptLoader
from world_simulation_engine.component.simulator.world_simulator import WorldSimulator
from world_simulation_engine.router import author_router, background_character_router, character_router, \
    config_router, container_router, equipment_router, event_router, intent_router, item_router, landmark_router, \
    location_router, media_router, memory_router, prompt_router, simulation_router, turn_router, workflow_router, \
    world_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = DatabaseService(
        driver=AsyncGraphDatabase.driver(
            uri=CONFIG.neo4j_uri,
            auth=(CONFIG.neo4j_username, CONFIG.neo4j_password),
        )
    )
    storage = StorageService(CONFIG.data_folder)
    await storage.initialise()
    await database.generation_job.fail_incomplete_jobs(
        "Generation interrupted by application restart",
    )

    app.state.database = database
    app.state.storage = storage
    simulator = WorldSimulator(
        database=database,
        prompt_loader=PromptLoader(database=database, storage=storage),
    )
    app.state.world_simulator = simulator

    try:
        yield
    finally:
        await simulator.shutdown()
        await database.close()


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
    )

    app.include_router(author_router)
    app.include_router(background_character_router)
    app.include_router(character_router)
    app.include_router(config_router)
    app.include_router(container_router)
    app.include_router(equipment_router)
    app.include_router(event_router)
    app.include_router(intent_router)
    app.include_router(item_router)
    app.include_router(landmark_router)
    app.include_router(location_router)
    app.include_router(media_router)
    app.include_router(memory_router)
    app.include_router(prompt_router)
    app.include_router(simulation_router)
    app.include_router(turn_router)
    app.include_router(workflow_router)
    app.include_router(world_router)

    return app


app = create_app()
