from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import WorldStateCheckpointType
from world_simulation_engine.model import WorldStateCheckpoint
from world_simulation_engine.service.database.world_state_checkpoint_store import WorldStateCheckpointStore


def _checkpoint_node(**overrides) -> dict:
    node = {
        "id": "checkpoint_1",
        "simulation_id": "simulation_1",
        "type": "before_user_input",
        "turn_id": None,
        "turn_sequence": None,
        "created_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "characters_json": "[]",
        "background_characters_json": "[]",
        "items_json": "[]",
        "item_stacks_json": "[]",
        "equipment_json": "[]",
        "containers_json": "[]",
        "variable_sets_json": "[]",
        "entity_relationships_json": "[]",
        "emotion_states_json": "[]",
        "subjective_entity_claims_json": "[]",
        "memories_json": "[]",
        "events_json": "[]",
    }
    node.update(overrides)
    return node


async def test_save_checkpoint_writes_every_captured_entity_type():
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(records=[{"checkpoint": _checkpoint_node(
                characters_json='[{"entity": {"id": "character_1"}}]',
            )}])
        )
    )
    store = WorldStateCheckpointStore(driver)

    result = await store.save_checkpoint(
        WorldStateCheckpoint(
            id="checkpoint_1",
            simulation_id="simulation_1",
            type=WorldStateCheckpointType.BEFORE_USER_INPUT,
            characters=[{"entity": {"id": "character_1"}}],
        )
    )

    assert result.characters == [{"entity": {"id": "character_1"}}]
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["type"] == WorldStateCheckpointType.BEFORE_USER_INPUT
    assert parameters["characters_json"] == '[{"entity": {"id": "character_1"}}]'
    assert parameters["items_json"] == "[]"


async def test_save_checkpoint_before_user_input_wipes_prior_checkpoints():
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            side_effect=[
                SimpleNamespace(records=[]),
                SimpleNamespace(records=[{"checkpoint": _checkpoint_node()}]),
            ]
        )
    )
    store = WorldStateCheckpointStore(driver)

    await store.save_checkpoint(
        WorldStateCheckpoint(
            simulation_id="simulation_1",
            type=WorldStateCheckpointType.BEFORE_USER_INPUT,
        )
    )

    assert driver.execute_query.await_count == 2
    delete_query = driver.execute_query.await_args_list[0].args[0]
    assert "DETACH DELETE checkpoint" in delete_query


async def test_get_checkpoint_by_turn_sequence_reads_requested_boundary():
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(records=[{"checkpoint": _checkpoint_node(
                type="after_user_input",
                turn_id="turn_41",
                turn_sequence=41,
            )}])
        )
    )
    store = WorldStateCheckpointStore(driver)

    result = await store.get_checkpoint_by_turn_sequence(
        simulation_id="simulation_1",
        turn_sequence=41,
    )

    assert result.turn_id == "turn_41"
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["turn_sequence"] == 41
    assert parameters["types"] == [
        WorldStateCheckpointType.AFTER_USER_INPUT,
        WorldStateCheckpointType.AFTER_CHARACTER_ROUND,
    ]


async def test_get_checkpoint_by_turn_sequence_returns_none_when_missing():
    driver = SimpleNamespace(execute_query=AsyncMock(return_value=SimpleNamespace(records=[])))
    store = WorldStateCheckpointStore(driver)

    assert await store.get_checkpoint_by_turn_sequence(
        simulation_id="simulation_1",
        turn_sequence=41,
    ) is None


async def test_get_checkpoint_returns_none_when_missing():
    driver = SimpleNamespace(execute_query=AsyncMock(return_value=SimpleNamespace(records=[])))
    store = WorldStateCheckpointStore(driver)

    assert await store.get_checkpoint(
        simulation_id="simulation_1",
        type=WorldStateCheckpointType.AFTER_CHARACTER_ROUND,
    ) is None


async def test_list_checkpoints_returns_every_saved_checkpoint():
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            return_value=SimpleNamespace(records=[
                {"checkpoint": _checkpoint_node(id="checkpoint_1")},
                {"checkpoint": _checkpoint_node(id="checkpoint_2", type="after_user_input", turn_sequence=1)},
            ])
        )
    )
    store = WorldStateCheckpointStore(driver)

    result = await store.list_checkpoints("simulation_1")

    assert [checkpoint.id for checkpoint in result] == ["checkpoint_1", "checkpoint_2"]
