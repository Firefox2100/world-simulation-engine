import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import SimulationAuditCategory
from world_simulation_engine.model import SimulationAuditEvent
from world_simulation_engine.service.database.simulation_audit_store import SimulationAuditStore


def audit_node(**updates):
    node = {
        "id": "audit_1",
        "simulation_id": "simulation_1",
        "run_id": "run_1",
        "turn_id": "turn_1",
        "category": "scheduler",
        "origin": "code",
        "status": "completed",
        "stage": "actor_selection",
        "summary": "Selected one actor.",
        "actor_ids": ["character_1"],
        "entity_ids": [],
        "details_json": json.dumps({"selection_reason": "available"}),
        "simulation_time": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "recorded_at": datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    }
    node.update(updates)
    return node


async def test_create_event_serializes_safe_details_and_links_scope():
    driver = SimpleNamespace(execute_query=AsyncMock(
        return_value=SimpleNamespace(records=[{"audit": audit_node()}]),
    ))
    event = SimulationAuditEvent(
        id="audit_1",
        simulation_id="simulation_1",
        run_id="run_1",
        turn_id="turn_1",
        category=SimulationAuditCategory.SCHEDULER,
        stage="actor_selection",
        summary="Selected one actor.",
        actor_ids=["character_1"],
        details={"selection_reason": "available"},
        simulation_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        recorded_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )

    result = await SimulationAuditStore(driver).create_event(event)

    assert result == event
    params = driver.execute_query.await_args.kwargs["parameters_"]
    assert json.loads(params["details_json"]) == {"selection_reason": "available"}
    assert "HAS_AUDIT_EVENT" in driver.execute_query.await_args.args[0]


async def test_list_events_applies_author_filters_and_pagination():
    driver = SimpleNamespace(execute_query=AsyncMock(
        return_value=SimpleNamespace(records=[{"audit": audit_node()}]),
    ))

    result = await SimulationAuditStore(driver).list_events(
        "simulation_1",
        run_id="run_1",
        category="scheduler",
        actor_id="character_1",
        limit=20,
        skip=5,
    )

    assert len(result) == 1
    params = driver.execute_query.await_args.kwargs["parameters_"]
    assert params == {
        "simulation_id": "simulation_1",
        "run_id": "run_1",
        "turn_id": None,
        "category": "scheduler",
        "actor_id": "character_1",
        "limit": 20,
        "skip": 5,
    }

