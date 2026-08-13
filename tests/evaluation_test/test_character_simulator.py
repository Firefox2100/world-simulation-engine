import os
from pathlib import Path

import pytest

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.component.simulator.scene_coordinator import SceneCoordinator
from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import ActionCandidateSet, CharacterActionPlan, ProposedAction

from workflow_helpers import (
    CHARACTER_SIMULATOR_CASES as SYNTHETIC_CHARACTER_INPUT_CASES,
    INPUT_PIPELINE_CASES,
    case_ids,
    write_case_result as _write_case_result,
)


def _synthetic_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_CHARACTER_SIMULATOR_OUTPUT",
            "tests/evaluation_test/output/character_simulator_results.json",
        )
    )


def _pipeline_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_INPUT_TO_CHARACTER_SIMULATOR_OUTPUT",
            "tests/evaluation_test/output/input_to_character_simulator_results.json",
        )
    )


async def _link_chat_components(
    *,
    database,
    simulation_id: str,
    config_id: str,
    components: list[ComponentType],
):
    for component in components:
        await database.config.link_chat(
            source_id=simulation_id,
            config_id=config_id,
            component=component,
        )


def _actions_from_interpretation(interpretation) -> list[ProposedAction]:
    return [
        item.action
        for item in interpretation.items
        if item.type == "action"
    ]


def _allowed_actions_from_validation(validation) -> list[ProposedAction]:
    return [
        item.action
        for item in validation.validations
        if item.allowed
    ]


def _action_plan(actor_id: str, actions: list[ProposedAction]) -> CharacterActionPlan:
    return CharacterActionPlan(
        actor_id=actor_id,
        actions=actions,
        candidate_sets=[
            ActionCandidateSet(
                proposal_index=0,
                actions=actions,
            )
        ] if actions else [],
    )


async def _nearby_non_user_character_ids(database, simulation_id: str) -> list[str]:
    user_character = await database.character.get_user_character_by_simulation(simulation_id)
    if not user_character:
        raise ValueError(f"Simulation {simulation_id} has no user character")

    location = await database.location.get_location_by_character(user_character.id)
    if not location:
        return []

    nearby_characters = await database.get_characters_in_location(location.id)
    return [
        character.id
        for character, _, _, _ in nearby_characters
        if not character.user_controlled
    ]


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    SYNTHETIC_CHARACTER_INPUT_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(SYNTHETIC_CHARACTER_INPUT_CASES),
)
async def test_evaluate_character_simulator_outputs_action_proposal(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await _link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[
            ComponentType.CHARACTER_SIMULATOR,
            ComponentType.PERSPECTIVE_RESOLVER,
        ],
    )
    simulator = CharacterSimulator(
        database=evaluation_seeded_database,
        langfuse_handler=None,
    )

    proposal = await simulator.propose_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=case["character_id"],
        user_input=case["user_input"],
    )

    assert proposal.actions[0].label
    assert proposal.actions[0].intended_duration_seconds >= 1
    assert proposal.next_review_hint_seconds >= 1

    _write_case_result(
        output_path=_synthetic_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=SYNTHETIC_CHARACTER_INPUT_CASES,
        case_result={
            "case_id": case["case_id"],
            "character_id": case["character_id"],
            "user_input": case["user_input"],
            "proposal": proposal.model_dump(mode="json"),
        },
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    INPUT_PIPELINE_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(INPUT_PIPELINE_CASES),
)
async def test_evaluate_input_to_character_simulator_fanout_outputs_action_proposals(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await _link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[
            ComponentType.ACTION_VALIDATOR,
            ComponentType.SCENE_COORDINATOR,
            ComponentType.CHARACTER_SIMULATOR,
            ComponentType.PERSPECTIVE_RESOLVER,
        ],
    )
    character_id = case["user_character_id"]
    interpreter = InputInterpreter(database=evaluation_seeded_database)
    validator = ActionValidator(database=evaluation_seeded_database)
    coordinator = SceneCoordinator(database=evaluation_seeded_database)
    character_simulator = CharacterSimulator(
        database=evaluation_seeded_database,
        langfuse_handler=None,
    )

    interpretation = await interpreter.interpret(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        user_input=case["user_input"],
    )
    actions = _actions_from_interpretation(interpretation)
    assert actions

    validation = await validator.validate_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        actions=actions,
    )
    allowed_actions = _allowed_actions_from_validation(validation)

    user_coordination = await coordinator.coordinate_scene(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        action_plans=[_action_plan(character_id, allowed_actions)],
    )

    fanout_character_ids = await _nearby_non_user_character_ids(
        evaluation_seeded_database,
        mock_graph_world_setup.simulation.id,
    )
    assert fanout_character_ids

    character_proposals = []
    for fanout_character_id in fanout_character_ids:
        proposal = await character_simulator.propose_actions(
            world_id=mock_graph_world_setup.world.id,
            simulation_id=mock_graph_world_setup.simulation.id,
            character_id=fanout_character_id,
            user_input=case["user_input"],
        )
        character_proposals.append(
            {
                "character_id": fanout_character_id,
                "proposal": proposal.model_dump(mode="json"),
            }
        )

    assert len(character_proposals) == len(fanout_character_ids)

    _write_case_result(
        output_path=_pipeline_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=INPUT_PIPELINE_CASES,
        case_result={
            "case_id": case["case_id"],
            "actor_id": character_id,
            "user_input": case["user_input"],
            "interpretation": interpretation.model_dump(mode="json"),
            "actions": [action.model_dump(mode="json") for action in actions],
            "validation": validation.model_dump(mode="json"),
            "allowed_actions": [action.model_dump(mode="json") for action in allowed_actions],
            "user_coordination": user_coordination.model_dump(mode="json"),
            "fanout_character_ids": fanout_character_ids,
            "character_proposals": character_proposals,
        },
    )
