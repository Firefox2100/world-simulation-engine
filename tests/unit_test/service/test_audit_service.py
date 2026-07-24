from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import SimulationAuditCategory
from world_simulation_engine.model import SimulationAuditEvent
from world_simulation_engine.service.audit_service import AuditService


async def test_audit_persistence_failure_never_breaks_simulation():
    database = SimpleNamespace(
        simulation_audit=SimpleNamespace(create_event=AsyncMock(side_effect=RuntimeError("offline"))),
    )
    event = SimulationAuditEvent(
        simulation_id="simulation_1",
        category=SimulationAuditCategory.GENERATION,
        stage="starting",
        summary="Started.",
    )

    assert await AuditService(database).record(event) is None

