from world_simulation_engine.misc.logging import log_event
from world_simulation_engine.model import SimulationAuditEvent


class AuditService:
    """Best-effort audit persistence which can never break simulation work."""
    def __init__(self, database):
        self._db = database

    async def record(self, event: SimulationAuditEvent) -> SimulationAuditEvent | None:
        log_event(
            "simulation_audit",
            simulation_id=event.simulation_id,
            run_id=event.run_id,
            turn_id=event.turn_id,
            category=event.category,
            origin=event.origin,
            status=event.status,
            stage=event.stage,
            summary=event.summary,
            actor_ids=event.actor_ids,
            entity_ids=event.entity_ids,
            details=event.details,
        )
        try:
            return await self._db.simulation_audit.create_event(event)
        except Exception as exc:
            log_event(
                "simulation_audit_persistence_failed",
                simulation_id=event.simulation_id,
                run_id=event.run_id,
                stage=event.stage,
                error_type=type(exc).__name__,
            )
            return None

