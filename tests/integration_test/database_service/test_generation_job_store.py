from datetime import UTC, datetime

import pytest

from world_simulation_engine.misc.enums import GenerationJobStatus, SimulationGenerationRequestType
from world_simulation_engine.model import GenerationJob, Simulation
from world_simulation_engine.service.database.generation_job_store import GenerationJobStore
from world_simulation_engine.service.database.simulation_store import SimulationStore

from .helpers import create_world


async def test_generation_job_lifecycle_is_persisted(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await SimulationStore(clean_neo4j).create_simulation(
        Simulation(
            id="simulation_jobs",
            name="Job simulation",
            current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        world.id,
    )
    store = GenerationJobStore(clean_neo4j)
    job = GenerationJob(
        id="job_1",
        simulation_id=simulation.id,
        client_request_id="request_1",
        request_fingerprint="fingerprint",
        request_type=SimulationGenerationRequestType.USER_INPUT_GENERATION,
    )

    assert await store.create_job(job) == job
    assert await store.get_job_by_client_request_id(simulation.id, "request_1") == job
    assert (await store.get_active_job(simulation.id)).id == job.id
    with pytest.raises(RuntimeError, match="already has an active generation"):
        await store.create_job(GenerationJob(
            id="job_2",
            simulation_id=simulation.id,
            request_type=SimulationGenerationRequestType.CONTINUE_GENERATION,
        ))

    running = await store.mark_running(job.id, "input_interpreter")
    assert running.status == GenerationJobStatus.RUNNING
    assert running.started_at is not None

    completed = await store.mark_completed(job.id, "turn_1")
    assert completed.status == GenerationJobStatus.COMPLETED
    assert completed.final_turn_id == "turn_1"
    assert completed.completed_at is not None
    assert await store.get_active_job(simulation.id) is None
    assert await store.get_job(job.id, simulation.id) == completed
