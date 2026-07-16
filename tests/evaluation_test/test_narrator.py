import os
from pathlib import Path

import pytest

from world_simulation_engine.component.simulator.narrator import Narrator
from world_simulation_engine.misc.enums import ComponentType

from workflow_helpers import (
    INPUT_PIPELINE_CASES,
    SYNTHETIC_COORDINATION_CASES,
    build_character_coordination_from_input,
    link_chat_components,
    synthetic_coordination,
    write_case_result,
)


def _synthetic_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_NARRATOR_OUTPUT",
            "tests/evaluation_test/output/narrator_results.json",
        )
    )


def _pipeline_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_INPUT_TO_NARRATOR_OUTPUT",
            "tests/evaluation_test/output/input_to_narrator_results.json",
        )
    )


@pytest.mark.parametrize(
    "case",
    SYNTHETIC_COORDINATION_CASES,
    ids=[case["case_id"] for case in SYNTHETIC_COORDINATION_CASES],
)
async def test_evaluate_narrator_outputs_text(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[ComponentType.NARRATOR],
    )
    narrator = Narrator(database=evaluation_seeded_database)
    coordination = synthetic_coordination(case)

    narration = await narrator.narrate_turn(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        coordination_result=coordination,
        user_input=case["user_input"],
    )

    assert narration.strip()
    assert "accepted_actions" not in narration
    assert "coordination_result" not in narration

    _write_narration_result(
        output_path=_synthetic_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=SYNTHETIC_COORDINATION_CASES,
        case_result={
            "case_id": case["case_id"],
            "source": case["source"],
            "user_input": case["user_input"],
            "coordination": coordination.model_dump(mode="json"),
            "narration": narration,
        },
    )


@pytest.mark.parametrize(
    "case",
    INPUT_PIPELINE_CASES,
    ids=[case["case_id"] for case in INPUT_PIPELINE_CASES],
)
async def test_evaluate_input_to_narrator_outputs_text(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[
            ComponentType.ACTION_VALIDATOR,
            ComponentType.SCENE_COORDINATOR,
            ComponentType.CHARACTER_SIMULATOR,
            ComponentType.PERSPECTIVE_RESOLVER,
            ComponentType.NARRATOR,
        ],
    )
    character_id = "character_arthur_moore"
    pipeline = await build_character_coordination_from_input(
        database=evaluation_seeded_database,
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        user_character_id=character_id,
        user_input=case["user_input"],
    )
    narrator = Narrator(database=evaluation_seeded_database)

    narration = await narrator.narrate_turn(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        coordination_result=pipeline["character_coordination"],
        user_input=case["user_input"],
    )

    assert narration.strip()
    assert "accepted_actions" not in narration
    assert "coordination_result" not in narration

    _write_narration_result(
        output_path=_pipeline_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=INPUT_PIPELINE_CASES,
        case_result={
            "case_id": case["case_id"],
            "actor_id": character_id,
            "user_input": case["user_input"],
            "interpretation": pipeline["interpretation"].model_dump(mode="json"),
            "user_actions": [
                action.model_dump(mode="json")
                for action in pipeline["user_actions"]
            ],
            "user_validation": pipeline["user_validation"].model_dump(mode="json"),
            "allowed_user_actions": [
                action.model_dump(mode="json")
                for action in pipeline["allowed_user_actions"]
            ],
            "user_coordination": pipeline["user_coordination"].model_dump(mode="json"),
            "fanout_character_ids": pipeline["fanout_character_ids"],
            "character_validations": [
                {
                    "character_id": record["character_id"],
                    "proposal": record["proposal"].model_dump(mode="json"),
                    "validation": record["validation"].model_dump(mode="json"),
                }
                for record in pipeline["character_validation_records"]
            ],
            "character_action_plans": [
                plan.model_dump(mode="json")
                for plan in pipeline["character_action_plans"]
            ],
            "character_coordination": pipeline["character_coordination"].model_dump(mode="json"),
            "narration": narration,
        },
    )


def _write_narration_result(
    *,
    output_path: Path,
    world_id: str,
    simulation_id: str,
    case_order: list[dict],
    case_result: dict,
):
    write_case_result(
        output_path=output_path,
        world_id=world_id,
        simulation_id=simulation_id,
        case_order=case_order,
        case_result=case_result,
    )
