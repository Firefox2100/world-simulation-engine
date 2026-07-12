from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from world_simulation_engine.service.database.simulation_store import SimulationStore


async def test_update_current_time_returns_updated_simulation():
    updated_time = datetime(2026, 1, 1, 12, 0, 2, tzinfo=UTC)
    simulation_node = {
        "id": "simulation_1",
        "name": "Simulation",
        "description": "A simulation",
        "current_time": updated_time,
    }
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(
                records=[
                    {
                        "s": simulation_node,
                    }
                ]
            )
        )
    )
    store = SimulationStore(driver)

    result = await store.update_current_time(
        simulation_id="simulation_1",
        current_time=updated_time,
    )

    assert result.current_time == updated_time
    assert driver.execute_query.await_args.kwargs["parameters_"] == {
        "id": "simulation_1",
        "current_time": updated_time,
    }


async def test_update_current_time_raises_when_simulation_is_missing():
    driver = SimpleNamespace(
        execute_query=AsyncMock(return_value=SimpleNamespace(records=[]))
    )
    store = SimulationStore(driver)

    with pytest.raises(ValueError, match="Simulation missing_simulation not found"):
        await store.update_current_time(
            simulation_id="missing_simulation",
            current_time=datetime(2026, 1, 1, 12, tzinfo=UTC),
        )
