from datetime import UTC, datetime

from world_simulation_engine.misc.enums import SimulationAuditCategory
from world_simulation_engine.model import SimulationAuditEvent


def test_audit_details_remove_sensitive_fields_and_bound_values():
    event = SimulationAuditEvent(
        simulation_id="simulation_1",
        category=SimulationAuditCategory.RETRIEVAL,
        stage="context",
        summary="Context selected.",
        details={
            "selected_memory_ids": ["memory_1"],
            "prompt": "private prompt",
            "raw_response": "private output",
            "nested": {"api_key": "secret", "safe": "yes"},
            "simulation_time": datetime(2026, 1, 1, tzinfo=UTC),
        },
    )

    assert event.details["selected_memory_ids"] == ["memory_1"]
    assert "prompt" not in event.details
    assert "raw_response" not in event.details
    assert event.details["nested"] == {"safe": "yes"}
    assert event.details["simulation_time"] == "2026-01-01T00:00:00+00:00"

