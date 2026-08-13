import os
from pathlib import Path

import pytest

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.component.simulator.scene_coordinator import SceneCoordinator
from world_simulation_engine.misc.enums import ComponentType, SceneCoordinationStatus
from world_simulation_engine.model import ActionCandidateSet, CharacterActionPlan, ProposedAction

from workflow_helpers import (
    ACTION_VALIDATOR_EVALUATION_CASES as EVALUATION_CASES,
    INPUT_PIPELINE_CASES,
    USER_COORDINATION_CASES,
    case_ids,
    write_case_result,
)


def _output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_ACTION_VALIDATOR_OUTPUT",
            "tests/evaluation_test/output/action_validator_results.json",
        )
    )


def _validator_from_input_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_ACTION_VALIDATOR_FROM_INPUT_OUTPUT",
            "tests/evaluation_test/output/action_validator_from_input_results.json",
        )
    )


def _user_coordination_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_USER_ACTION_COORDINATOR_OUTPUT",
            "tests/evaluation_test/output/user_action_coordination_results.json",
        )
    )


def _input_to_coordination_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_INPUT_TO_COORDINATOR_OUTPUT",
            "tests/evaluation_test/output/input_to_coordinator_results.json",
        )
    )


def _character_action_validator_from_input_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_CHARACTER_ACTION_VALIDATOR_FROM_INPUT_OUTPUT",
            "tests/evaluation_test/output/character_action_validator_from_input_results.json",
        )
    )


def _character_action_coordination_from_input_output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_CHARACTER_ACTION_COORDINATION_FROM_INPUT_OUTPUT",
            "tests/evaluation_test/output/character_action_coordination_from_input_results.json",
        )
    )


def _write_case_result(
    *,
    output_path: Path,
    world_id: str,
    simulation_id: str,
    case_result: dict,
    case_order: list[tuple[Path, dict]] | None = None,
):
    write_case_result(
        output_path=output_path,
        world_id=world_id,
        simulation_id=simulation_id,
        case_order=case_order or EVALUATION_CASES,
        case_result=case_result,
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


def _assert_validation_is_internally_consistent(validation, actions: list[ProposedAction]) -> None:
    """Check the structural/semantic contract of an ActionValidationResult, not just its shape.

    This is deliberately generic (no assumption about which specific actions were supplied) so it
    applies to both the fixed EVALUATION_CASES and the free-text-derived INPUT_PIPELINE_CASES: the
    validator must echo back the exact action it judged, and its allowed/blocking_conditions/reason
    fields must not contradict each other, regardless of what the action actually was.
    """
    assert len(validation.validations) == len(actions)
    assert [entry.action_index for entry in validation.validations] == list(range(len(actions)))
    for entry, original_action in zip(validation.validations, actions):
        assert entry.action.type == original_action.type
        assert entry.action.label == original_action.label
        assert entry.action.target_ids == original_action.target_ids
        assert entry.reason.strip(), (
            f"Action {entry.action_index} ({original_action.label}) has no reason stated"
        )
        if entry.allowed:
            assert not entry.blocking_conditions, (
                f"Action {entry.action_index} ({original_action.label}) was allowed but still "
                f"listed blocking_conditions: {entry.blocking_conditions}"
            )
        else:
            assert entry.blocking_conditions, (
                f"Action {entry.action_index} ({original_action.label}) was blocked but stated "
                "no blocking_conditions"
            )


def _assert_coordination_is_internally_consistent(coordination, actor_id: str, action_count: int) -> None:
    """Check SceneCoordinationResult beyond `status`, which is a StrEnum and therefore always
    truthy - `assert coordination.status` alone can never fail regardless of outcome.
    """
    for accepted in coordination.accepted_actions:
        assert accepted.actor_id == actor_id
        assert 0 <= accepted.action_index < action_count
        assert accepted.summary.strip()
    for pending in coordination.pending_actions:
        assert pending.actor_id == actor_id
        assert 0 <= pending.action_index < action_count
        assert pending.reason.strip()
    if coordination.status == SceneCoordinationStatus.PROBLEM:
        assert coordination.problem is not None
        assert coordination.problem.description.strip()
    elif coordination.status == SceneCoordinationStatus.STOPPED:
        assert coordination.stopped_reason


def _assert_multi_actor_coordination_is_internally_consistent(coordination, action_plans) -> None:
    """Same contract as `_assert_coordination_is_internally_consistent`, for a coordination call
    that covers several actors' plans at once (so actor_id can't be pinned to a single value).
    """
    known_actor_ids = {plan.actor_id for plan in action_plans}
    for accepted in coordination.accepted_actions:
        assert accepted.actor_id in known_actor_ids
        assert accepted.action_index >= 0
        assert accepted.summary.strip()
    for pending in coordination.pending_actions:
        assert pending.actor_id in known_actor_ids
        assert pending.reason.strip()
    if coordination.status == SceneCoordinationStatus.PROBLEM:
        assert coordination.problem is not None
        assert coordination.problem.description.strip()
    elif coordination.status == SceneCoordinationStatus.STOPPED:
        assert coordination.stopped_reason


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


def _proposal_candidates(proposal) -> list[ProposedAction]:
    return [
        action
        for sequence in [proposal.actions, *proposal.backup_proposals]
        for action in sequence
    ]


def _character_action_plans_from_validation_records(records: list[dict]) -> list[CharacterActionPlan]:
    plans_by_actor: dict[str, CharacterActionPlan] = {}
    for record in records:
        validations = record.get("proposal_validations") or [record["validation"]]
        proposal_sequences = [record["proposal"].actions, *record["proposal"].backup_proposals]
        valid_sequences = [
            (proposal_index, proposal_sequences[proposal_index])
            for proposal_index, validation in enumerate(validations)
            if proposal_index < len(proposal_sequences)
            and validation.validations
            and all(item.allowed for item in validation.validations)
        ]
        if not valid_sequences:
            continue

        plan = plans_by_actor.setdefault(
            record["character_id"],
            CharacterActionPlan(
                actor_id=record["character_id"],
                actions=valid_sequences[0][1],
            ),
        )
        plan.action_proposals.append(record["proposal"])
        for proposal_index, sequence in valid_sequences:
            plan.candidate_sets.append(
                ActionCandidateSet(
                    proposal_index=proposal_index,
                    actions=sequence,
                )
            )

    return list(plans_by_actor.values())


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


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    EVALUATION_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(EVALUATION_CASES),
)
async def test_evaluate_action_validator_outputs_result(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await _link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[ComponentType.ACTION_VALIDATOR],
    )
    validator = ActionValidator(database=evaluation_seeded_database)
    actions = [
        ProposedAction.model_validate(action)
        for action in case["actions"]
    ]

    validation = await validator.validate_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=case["actor_id"],
        actions=actions,
    )

    _assert_validation_is_internally_consistent(validation, actions)
    assert validation.validations[0].allowed == case["expected_allowed"], (
        f"Expected allowed={case['expected_allowed']} for case {case['case_id']!r}, got "
        f"allowed={validation.validations[0].allowed} (reason: {validation.validations[0].reason!r})"
    )

    _write_case_result(
        output_path=_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_result={
            "case_id": case["case_id"],
            "origin": case["origin"],
            "actor_id": case["actor_id"],
            "actions": [action.model_dump(mode="json") for action in actions],
            "validation": validation.model_dump(mode="json"),
        },
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    INPUT_PIPELINE_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(INPUT_PIPELINE_CASES),
)
async def test_evaluate_input_to_character_action_validation_outputs_result(
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
    user_actions = _actions_from_interpretation(interpretation)
    assert user_actions

    user_validation = await validator.validate_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        actions=user_actions,
    )
    allowed_user_actions = _allowed_actions_from_validation(user_validation)

    user_coordination = await coordinator.coordinate_scene(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        action_plans=[_action_plan(character_id, allowed_user_actions)],
    )

    fanout_character_ids = await _nearby_non_user_character_ids(
        evaluation_seeded_database,
        mock_graph_world_setup.simulation.id,
    )
    assert fanout_character_ids

    character_validation_records = []
    for fanout_character_id in fanout_character_ids:
        proposal = await character_simulator.propose_actions(
            world_id=mock_graph_world_setup.world.id,
            simulation_id=mock_graph_world_setup.simulation.id,
            character_id=fanout_character_id,
            user_input=case["user_input"],
        )
        proposed_actions = _proposal_candidates(proposal)
        validation = await validator.validate_actions(
            world_id=mock_graph_world_setup.world.id,
            simulation_id=mock_graph_world_setup.simulation.id,
            character_id=fanout_character_id,
            actions=proposed_actions,
        )

        _assert_validation_is_internally_consistent(validation, proposed_actions)
        character_validation_records.append(
            {
                "character_id": fanout_character_id,
                "proposal": proposal,
                "proposed_actions": proposed_actions,
                "validation": validation,
            }
        )

    _write_case_result(
        output_path=_character_action_validator_from_input_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=INPUT_PIPELINE_CASES,
        case_result={
            "case_id": case["case_id"],
            "actor_id": character_id,
            "user_input": case["user_input"],
            "interpretation": interpretation.model_dump(mode="json"),
            "user_actions": [action.model_dump(mode="json") for action in user_actions],
            "user_validation": user_validation.model_dump(mode="json"),
            "allowed_user_actions": [action.model_dump(mode="json") for action in allowed_user_actions],
            "user_coordination": user_coordination.model_dump(mode="json"),
            "fanout_character_ids": fanout_character_ids,
            "character_validations": [
                {
                    "character_id": record["character_id"],
                    "proposal": record["proposal"].model_dump(mode="json"),
                    "proposed_actions": [
                        action.model_dump(mode="json")
                        for action in record["proposed_actions"]
                    ],
                    "validation": record["validation"].model_dump(mode="json"),
                }
                for record in character_validation_records
            ],
        },
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    INPUT_PIPELINE_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(INPUT_PIPELINE_CASES),
)
async def test_evaluate_input_to_character_action_coordination_outputs_result(
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
    user_actions = _actions_from_interpretation(interpretation)
    assert user_actions

    user_validation = await validator.validate_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        actions=user_actions,
    )
    allowed_user_actions = _allowed_actions_from_validation(user_validation)

    user_coordination = await coordinator.coordinate_scene(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        action_plans=[_action_plan(character_id, allowed_user_actions)],
    )

    fanout_character_ids = await _nearby_non_user_character_ids(
        evaluation_seeded_database,
        mock_graph_world_setup.simulation.id,
    )
    assert fanout_character_ids

    character_validation_records = []
    for fanout_character_id in fanout_character_ids:
        proposal = await character_simulator.propose_actions(
            world_id=mock_graph_world_setup.world.id,
            simulation_id=mock_graph_world_setup.simulation.id,
            character_id=fanout_character_id,
            user_input=case["user_input"],
        )
        proposed_actions = _proposal_candidates(proposal)
        validation = await validator.validate_actions(
            world_id=mock_graph_world_setup.world.id,
            simulation_id=mock_graph_world_setup.simulation.id,
            character_id=fanout_character_id,
            actions=proposed_actions,
        )
        character_validation_records.append(
            {
                "character_id": fanout_character_id,
                "proposal": proposal,
                "proposed_actions": proposed_actions,
                "validation": validation,
            }
        )

    character_action_plans = _character_action_plans_from_validation_records(character_validation_records)
    assert character_action_plans

    character_coordination = await coordinator.coordinate_scene(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        action_plans=character_action_plans,
    )

    _assert_multi_actor_coordination_is_internally_consistent(character_coordination, character_action_plans)

    _write_case_result(
        output_path=_character_action_coordination_from_input_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=INPUT_PIPELINE_CASES,
        case_result={
            "case_id": case["case_id"],
            "actor_id": character_id,
            "user_input": case["user_input"],
            "interpretation": interpretation.model_dump(mode="json"),
            "user_actions": [action.model_dump(mode="json") for action in user_actions],
            "user_validation": user_validation.model_dump(mode="json"),
            "allowed_user_actions": [action.model_dump(mode="json") for action in allowed_user_actions],
            "user_coordination": user_coordination.model_dump(mode="json"),
            "fanout_character_ids": fanout_character_ids,
            "character_validations": [
                {
                    "character_id": record["character_id"],
                    "proposal": record["proposal"].model_dump(mode="json"),
                    "proposed_actions": [
                        action.model_dump(mode="json")
                        for action in record["proposed_actions"]
                    ],
                    "validation": record["validation"].model_dump(mode="json"),
                }
                for record in character_validation_records
            ],
            "character_action_plans": [
                plan.model_dump(mode="json")
                for plan in character_action_plans
            ],
            "character_coordination": character_coordination.model_dump(mode="json"),
        },
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    INPUT_PIPELINE_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(INPUT_PIPELINE_CASES),
)
async def test_evaluate_action_validator_from_input_outputs_result(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await _link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[ComponentType.ACTION_VALIDATOR],
    )
    character_id = case["user_character_id"]
    interpreter = InputInterpreter(database=evaluation_seeded_database)
    validator = ActionValidator(database=evaluation_seeded_database)

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

    _assert_validation_is_internally_consistent(validation, actions)

    _write_case_result(
        output_path=_validator_from_input_output_path(),
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
        },
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    USER_COORDINATION_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(USER_COORDINATION_CASES),
)
async def test_evaluate_user_action_coordination_outputs_result(
    case,
    evaluation_seeded_database,
    evaluation_chat_model_config,
    mock_graph_world_setup,
):
    await _link_chat_components(
        database=evaluation_seeded_database,
        simulation_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        components=[ComponentType.SCENE_COORDINATOR],
    )
    coordinator = SceneCoordinator(database=evaluation_seeded_database)
    actions = [
        ProposedAction.model_validate(action)
        for action in case["actions"]
    ]

    coordination = await coordinator.coordinate_scene(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        action_plans=[_action_plan(case["actor_id"], actions)],
    )

    _assert_coordination_is_internally_consistent(coordination, case["actor_id"], len(actions))

    _write_case_result(
        output_path=_user_coordination_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        case_order=USER_COORDINATION_CASES,
        case_result={
            "case_id": case["case_id"],
            "actor_id": case["actor_id"],
            "actions": [action.model_dump(mode="json") for action in actions],
            "coordination": coordination.model_dump(mode="json"),
        },
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    INPUT_PIPELINE_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(INPUT_PIPELINE_CASES),
)
async def test_evaluate_input_to_user_action_coordination_outputs_result(
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
        ],
    )
    character_id = case["user_character_id"]
    interpreter = InputInterpreter(database=evaluation_seeded_database)
    validator = ActionValidator(database=evaluation_seeded_database)
    coordinator = SceneCoordinator(database=evaluation_seeded_database)

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

    coordination = await coordinator.coordinate_scene(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        action_plans=[_action_plan(character_id, allowed_actions)],
    )

    _assert_validation_is_internally_consistent(validation, actions)
    _assert_coordination_is_internally_consistent(coordination, character_id, len(allowed_actions))

    _write_case_result(
        output_path=_input_to_coordination_output_path(),
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
            "coordination": coordination.model_dump(mode="json"),
        },
    )
