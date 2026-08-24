from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.model import TurnVersion
from world_simulation_engine.service.database.turn_version_store import TurnVersionStore


def _version_node(**overrides) -> dict:
    node = {
        "id": "version_1",
        "simulation_id": "simulation_1",
        "turn_sequence": 42,
        "turn_json": '{"id": "turn_42"}',
        "presentation_blocks_json": "[]",
        "user_input": "I look around.",
        "checkpoint_id": "checkpoint_1",
        "created_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    }
    node.update(overrides)
    return node


async def test_archive_version_writes_the_turn_and_presentation_json():
    driver = SimpleNamespace(
        execute_query=AsyncMock(return_value=SimpleNamespace(records=[{"version": _version_node()}]))
    )
    store = TurnVersionStore(driver)

    result = await store.archive_version(TurnVersion(
        id="version_1",
        simulation_id="simulation_1",
        turn_sequence=42,
        turn={"id": "turn_42"},
        user_input="I look around.",
        checkpoint_id="checkpoint_1",
    ))

    assert result.turn == {"id": "turn_42"}
    assert result.user_input == "I look around."
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["turn_json"] == '{"id": "turn_42"}'
    assert parameters["turn_sequence"] == 42


async def test_list_versions_orders_most_recent_first():
    driver = SimpleNamespace(
        execute_query=AsyncMock(return_value=SimpleNamespace(records=[
            {"version": _version_node(id="version_2")},
            {"version": _version_node(id="version_1")},
        ]))
    )
    store = TurnVersionStore(driver)

    result = await store.list_versions(simulation_id="simulation_1", turn_sequence=42)

    assert [version.id for version in result] == ["version_2", "version_1"]


async def test_get_version_returns_none_when_missing():
    driver = SimpleNamespace(execute_query=AsyncMock(return_value=SimpleNamespace(records=[])))
    store = TurnVersionStore(driver)

    assert await store.get_version("missing") is None
