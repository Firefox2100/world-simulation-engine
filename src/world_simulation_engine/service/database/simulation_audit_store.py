import json

from neo4j import AsyncDriver

from world_simulation_engine.model import SimulationAuditEvent


def _native_datetime(value):
    return value.to_native() if hasattr(value, "to_native") else value


def _event_from_node(node) -> SimulationAuditEvent:
    return SimulationAuditEvent(
        id=node["id"],
        simulation_id=node["simulation_id"],
        run_id=node.get("run_id"),
        turn_id=node.get("turn_id"),
        category=node["category"],
        origin=node["origin"],
        status=node["status"],
        stage=node["stage"],
        summary=node["summary"],
        actor_ids=list(node.get("actor_ids") or []),
        entity_ids=list(node.get("entity_ids") or []),
        details=json.loads(node.get("details_json") or "{}"),
        simulation_time=_native_datetime(node.get("simulation_time")),
        recorded_at=_native_datetime(node.get("recorded_at")),
    )


class SimulationAuditStore:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    async def create_event(self, event: SimulationAuditEvent) -> SimulationAuditEvent:
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})
            CREATE (audit:SimulationAuditEvent {
                id: $id, simulation_id: $simulation_id, run_id: $run_id, turn_id: $turn_id,
                category: $category, origin: $origin, status: $status, stage: $stage,
                summary: $summary, actor_ids: $actor_ids, entity_ids: $entity_ids,
                details_json: $details_json, simulation_time: $simulation_time,
                recorded_at: $recorded_at
            })
            MERGE (simulation)-[:HAS_AUDIT_EVENT]->(audit)
            WITH audit
            OPTIONAL MATCH (job:GenerationJob {id: $run_id})
            FOREACH (_ IN CASE WHEN job IS NULL THEN [] ELSE [1] END |
                MERGE (job)-[:HAS_AUDIT_EVENT]->(audit))
            WITH audit
            OPTIONAL MATCH (turn:Turn {id: $turn_id})
            FOREACH (_ IN CASE WHEN turn IS NULL THEN [] ELSE [1] END |
                MERGE (turn)-[:HAS_AUDIT_EVENT]->(audit))
            RETURN audit
            """,
            parameters_={
                **event.model_dump(exclude={"details"}),
                "details_json": json.dumps(event.details, sort_keys=True),
            },
        )
        if not result.records:
            raise ValueError(f"Simulation {event.simulation_id} not found")
        return _event_from_node(result.records[0]["audit"])

    async def list_events(
            self,
            simulation_id: str,
            *,
            run_id: str | None = None,
            turn_id: str | None = None,
            category: str | None = None,
            actor_id: str | None = None,
            limit: int = 200,
            skip: int = 0,
    ) -> list[SimulationAuditEvent]:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_AUDIT_EVENT]->(audit:SimulationAuditEvent)
            WHERE ($run_id IS NULL OR audit.run_id = $run_id)
              AND ($turn_id IS NULL OR audit.turn_id = $turn_id)
              AND ($category IS NULL OR audit.category = $category)
              AND ($actor_id IS NULL OR $actor_id IN audit.actor_ids)
            RETURN audit
            ORDER BY audit.recorded_at DESC, audit.id DESC
            SKIP $skip LIMIT $limit
            """,
            parameters_={
                "simulation_id": simulation_id, "run_id": run_id, "turn_id": turn_id,
                "category": category, "actor_id": actor_id, "limit": limit, "skip": skip,
            },
        )
        return [_event_from_node(record["audit"]) for record in result.records]

