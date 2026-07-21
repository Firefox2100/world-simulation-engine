from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from world_simulation_engine.component.simulator.world_simulator import (
    OffSceneGenerationStatus,
    WorldSimulator,
    WorldSimulatorState,
)
from world_simulation_engine.misc.enums import TurnType


@pytest.mark.parametrize(
    ("user_input", "expects_wait"),
    [
        ("I telephone Marcus Reed and ask what he found in the director's office.", True),
        ("I go to the director's office to find Marcus Reed.", True),
        ("I quietly inspect the Visitor's Room Ledger at the bar.", False),
    ],
    ids=["contact_off_scene_actor", "move_to_off_scene_actor", "unrelated_action"],
)
async def test_evaluate_world_simulator_off_scene_conflict_detection(
        user_input,
        expects_wait,
        evaluation_seeded_database,
        mock_graph_world_setup,
):
    simulator = WorldSimulator(database=evaluation_seeded_database)
    generation = OffSceneGenerationStatus(
        simulation_id=mock_graph_world_setup.simulation.id,
        trigger_turn_id="evaluation_background_turn",
        trigger_turn_type=TurnType.USER_INPUT,
        simulation_time=datetime.now(UTC),
        status="running",
        stage="proposing_actions",
        actor_ids=["character_marcus_reed"],
    )
    simulator._off_scene_generations[generation.id] = generation
    simulator.wait_for_off_scene_activity = AsyncMock()
    state = WorldSimulatorState(
        world=mock_graph_world_setup.world,
        simulation=mock_graph_world_setup.simulation,
        user_input=user_input,
    )

    await simulator.interpret_user_input(state)

    assert simulator.wait_for_off_scene_activity.await_count == int(expects_wait)
