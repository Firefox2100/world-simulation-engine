from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import GenerationJobStatus, SimulationGenerationRequestType
from world_simulation_engine.model import GenerationJob
from world_simulation_engine.service.database.generation_job_store import GenerationJobStore


def job_node(**updates):
    node = {
        "id": "job_1",
        "simulation_id": "simulation_1",
        "client_request_id": "request_1",
        "request_fingerprint": "fingerprint",
        "request_type": "user_input_generation",
        "regenerate_turn_sequence": None,
        "status": "queued",
        "created_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    }
    node.update(updates)
    return node


async def test_create_generation_job_persists_request_identity():
    driver = SimpleNamespace(execute_query=AsyncMock(
        return_value=SimpleNamespace(records=[{"job": job_node()}]),
    ))
    store = GenerationJobStore(driver)
    job = GenerationJob(
        id="job_1",
        simulation_id="simulation_1",
        client_request_id="request_1",
        request_fingerprint="fingerprint",
        request_type=SimulationGenerationRequestType.USER_INPUT_GENERATION,
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    result = await store.create_job(job)

    assert result == job
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["client_request_id"] == "request_1"
    assert parameters["request_fingerprint"] == "fingerprint"


async def test_mark_completed_persists_final_turn_and_terminal_state():
    driver = SimpleNamespace(execute_query=AsyncMock(
        return_value=SimpleNamespace(records=[{
            "job": job_node(
                status="completed",
                stage="completed",
                final_turn_id="turn_4",
                completed_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
            ),
        }]),
    ))

    result = await GenerationJobStore(driver).mark_completed("job_1", "turn_4")

    assert result.status == GenerationJobStatus.COMPLETED
    assert result.final_turn_id == "turn_4"
    properties = driver.execute_query.await_args.kwargs["parameters_"]["properties"]
    assert properties["status"] == GenerationJobStatus.COMPLETED
    assert properties["final_turn_id"] == "turn_4"
