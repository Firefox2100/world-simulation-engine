from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import GraphStateSnapshotType
from world_simulation_engine.model import GraphStateSnapshot
from world_simulation_engine.service.database.graph_state_snapshot_store import GraphStateSnapshotStore


async def test_save_snapshot_writes_limited_regeneration_boundary():
    created_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    snapshot_node = {
        "id": "snapshot_1",
        "simulation_id": "simulation_1",
        "type": "before_user_input",
        "turn_id": "turn_40",
        "turn_sequence": 40,
        "state_json": '{"user_input": "Look around."}',
        "created_at": created_at,
    }
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(
                records=[
                    {
                        "snapshot": snapshot_node,
                    }
                ]
            )
        )
    )
    store = GraphStateSnapshotStore(driver)

    result = await store.save_snapshot(
        GraphStateSnapshot(
            id="snapshot_1",
            simulation_id="simulation_1",
            type=GraphStateSnapshotType.BEFORE_USER_INPUT,
            turn_id="turn_40",
            turn_sequence=40,
            state={"user_input": "Look around."},
            created_at=created_at,
        )
    )

    assert result.state == {"user_input": "Look around."}
    assert result.type == GraphStateSnapshotType.BEFORE_USER_INPUT
    assert driver.execute_query.await_args.kwargs["parameters_"]["type"] == GraphStateSnapshotType.BEFORE_USER_INPUT
    assert driver.execute_query.await_args.kwargs["parameters_"]["state_json"] == '{"user_input": "Look around."}'


async def test_get_snapshot_returns_none_when_missing():
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(records=[])
        )
    )
    store = GraphStateSnapshotStore(driver)

    assert await store.get_snapshot(
        simulation_id="simulation_1",
        type=GraphStateSnapshotType.AFTER_USER_INPUT,
    ) is None


async def test_get_latest_generation_base_snapshot_reads_accumulated_round_base():
    snapshot_node = {
        "id": "snapshot_2",
        "simulation_id": "simulation_1",
        "type": "after_character_round",
        "turn_id": "turn_42",
        "turn_sequence": 42,
        "state_json": '{"user_input": null}',
        "created_at": datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    }
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(
                records=[
                    {
                        "snapshot": snapshot_node,
                    }
                ]
            )
        )
    )
    store = GraphStateSnapshotStore(driver)

    result = await store.get_latest_generation_base_snapshot("simulation_1")

    assert result.turn_sequence == 42
    assert result.type == GraphStateSnapshotType.AFTER_CHARACTER_ROUND
    assert driver.execute_query.await_args.kwargs["parameters_"]["types"] == [
        GraphStateSnapshotType.AFTER_USER_INPUT,
        GraphStateSnapshotType.AFTER_CHARACTER_ROUND,
    ]


async def test_get_generation_base_snapshot_by_turn_sequence_reads_requested_base():
    snapshot_node = {
        "id": "snapshot_1",
        "simulation_id": "simulation_1",
        "type": "after_user_input",
        "turn_id": "turn_41",
        "turn_sequence": 41,
        "state_json": '{"user_input": "Look around."}',
        "created_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    }
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(
                records=[
                    {
                        "snapshot": snapshot_node,
                    }
                ]
            )
        )
    )
    store = GraphStateSnapshotStore(driver)

    result = await store.get_generation_base_snapshot_by_turn_sequence(
        simulation_id="simulation_1",
        turn_sequence=41,
    )

    assert result.turn_id == "turn_41"
    assert driver.execute_query.await_args.kwargs["parameters_"]["turn_sequence"] == 41
