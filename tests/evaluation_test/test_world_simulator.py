from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from world_simulation_engine.component.simulator.world_simulator import (
    OffSceneGenerationStatus,
    WorldSimulator,
    WorldSimulatorState,
)
from world_simulation_engine.misc.enums import TurnType

from workflow_helpers import WORLD_SIMULATOR_CASES, case_ids


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    WORLD_SIMULATOR_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(WORLD_SIMULATOR_CASES),
)
async def test_evaluate_world_simulator_off_scene_conflict_detection(
        case,
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
        actor_ids=case["off_scene_actor_ids"],
    )
    simulator._off_scene_generations[generation.id] = generation
    simulator.wait_for_off_scene_activity = AsyncMock()
    state = WorldSimulatorState(
        world=mock_graph_world_setup.world,
        simulation=mock_graph_world_setup.simulation,
        user_input=case["user_input"],
    )

    await simulator.interpret_user_input(state)

    assert simulator.wait_for_off_scene_activity.await_count == int(case["expects_wait"])
