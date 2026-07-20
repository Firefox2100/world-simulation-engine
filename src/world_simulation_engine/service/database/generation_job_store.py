from datetime import UTC, datetime

from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import GenerationJobStatus
from world_simulation_engine.model import GenerationJob


def _datetime_from_node(node, key: str):
    value = node.get(key)
    if hasattr(value, "to_native"):
        return value.to_native()
    return value


def _generation_job_from_node(node) -> GenerationJob:
    return GenerationJob(
        id=node["id"],
        simulation_id=node["simulation_id"],
        client_request_id=node.get("client_request_id"),
        request_fingerprint=node.get("request_fingerprint"),
        request_type=node["request_type"],
        regenerate_turn_sequence=node.get("regenerate_turn_sequence"),
        status=node["status"],
        stage=node.get("stage"),
        created_at=_datetime_from_node(node, "created_at"),
        started_at=_datetime_from_node(node, "started_at"),
        completed_at=_datetime_from_node(node, "completed_at"),
        error=node.get("error"),
        final_turn_id=node.get("final_turn_id"),
    )


class GenerationJobStore:
    """Store generation lifecycle state and enforce one active run per simulation."""

    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    async def create_job(self, job: GenerationJob) -> GenerationJob:
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})
            SET simulation._generation_job_lock = randomUUID()
            WITH simulation
            OPTIONAL MATCH (simulation)-[:HAS_GENERATION_JOB]->(active:GenerationJob)
            WHERE active.status IN $active_statuses
            WITH simulation, count(active) AS active_count
            REMOVE simulation._generation_job_lock
            WITH simulation, active_count
            WHERE active_count = 0
            CREATE (job:GenerationJob {
                id: $id,
                simulation_id: $simulation_id,
                client_request_id: $client_request_id,
                request_fingerprint: $request_fingerprint,
                request_type: $request_type,
                regenerate_turn_sequence: $regenerate_turn_sequence,
                status: $status,
                created_at: $created_at
            })
            MERGE (simulation)-[:HAS_GENERATION_JOB]->(job)
            RETURN job
            """,
            parameters_={
                "id": job.id,
                "simulation_id": job.simulation_id,
                "client_request_id": job.client_request_id,
                "request_fingerprint": job.request_fingerprint,
                "request_type": job.request_type,
                "regenerate_turn_sequence": job.regenerate_turn_sequence,
                "status": job.status,
                "created_at": job.created_at,
                "active_statuses": [GenerationJobStatus.QUEUED, GenerationJobStatus.RUNNING],
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            simulation_result = await self._driver.execute_query(
                "MATCH (simulation:Simulation {id: $simulation_id}) RETURN simulation LIMIT 1",
                parameters_={"simulation_id": job.simulation_id},
            )
            if not simulation_result.records:
                raise ValueError(f"Simulation {job.simulation_id} not found")
            raise RuntimeError(f"Simulation {job.simulation_id} already has an active generation")
        return _generation_job_from_node(record["job"])

    async def get_job(self, job_id: str, simulation_id: str | None = None) -> GenerationJob | None:
        if simulation_id is None:
            match = "MATCH (job:GenerationJob {id: $job_id})"
        else:
            match = (
                "MATCH (:Simulation {id: $simulation_id})-[:HAS_GENERATION_JOB]->"
                "(job:GenerationJob {id: $job_id})"
            )
        result = await self._driver.execute_query(
            match + " RETURN job LIMIT 1",
            parameters_={"job_id": job_id, "simulation_id": simulation_id},
        )
        record = result.records[0] if result.records else None
        return _generation_job_from_node(record["job"]) if record else None

    async def get_job_by_client_request_id(
            self,
            simulation_id: str,
            client_request_id: str,
    ) -> GenerationJob | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GENERATION_JOB]->(
                job:GenerationJob {client_request_id: $client_request_id}
            )
            RETURN job
            ORDER BY job.created_at ASC
            LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "client_request_id": client_request_id,
            },
        )
        record = result.records[0] if result.records else None
        return _generation_job_from_node(record["job"]) if record else None

    async def get_active_job(self, simulation_id: str) -> GenerationJob | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GENERATION_JOB]->(job:GenerationJob)
            WHERE job.status IN $statuses
            RETURN job
            ORDER BY job.created_at DESC
            LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "statuses": [GenerationJobStatus.QUEUED, GenerationJobStatus.RUNNING],
            },
        )
        record = result.records[0] if result.records else None
        return _generation_job_from_node(record["job"]) if record else None

    async def update_job(self, job_id: str, properties: dict) -> GenerationJob:
        result = await self._driver.execute_query(
            """
            MATCH (job:GenerationJob {id: $job_id})
            SET job += $properties
            RETURN job
            """,
            parameters_={"job_id": job_id, "properties": properties},
        )
        record = result.records[0] if result.records else None
        if not record:
            raise ValueError(f"Generation job {job_id} not found")
        return _generation_job_from_node(record["job"])

    async def mark_running(self, job_id: str, stage: str | None = None) -> GenerationJob:
        return await self.update_job(job_id, {
            "status": GenerationJobStatus.RUNNING,
            "stage": stage,
            "started_at": datetime.now(tz=UTC),
        })

    async def mark_completed(
            self,
            job_id: str,
            final_turn_id: str | None,
            stage: str | None = "completed",
    ) -> GenerationJob:
        return await self.update_job(job_id, {
            "status": GenerationJobStatus.COMPLETED,
            "stage": stage,
            "completed_at": datetime.now(tz=UTC),
            "final_turn_id": final_turn_id,
            "error": None,
        })

    async def mark_failed(self, job_id: str, error: str) -> GenerationJob:
        return await self.update_job(job_id, {
            "status": GenerationJobStatus.FAILED,
            "stage": "failed",
            "completed_at": datetime.now(tz=UTC),
            "error": error,
        })

    async def fail_incomplete_jobs(self, error: str) -> int:
        result = await self._driver.execute_query(
            """
            MATCH (job:GenerationJob)
            WHERE job.status IN $statuses
            SET job.status = $failed_status,
                job.stage = 'failed',
                job.completed_at = $completed_at,
                job.error = $error
            RETURN count(job) AS failed_count
            """,
            parameters_={
                "statuses": [GenerationJobStatus.QUEUED, GenerationJobStatus.RUNNING],
                "failed_status": GenerationJobStatus.FAILED,
                "completed_at": datetime.now(tz=UTC),
                "error": error,
            },
        )
        record = result.records[0] if result.records else None
        return record["failed_count"] if record else 0
"""Neo4j persistence for durable simulator generation jobs."""
