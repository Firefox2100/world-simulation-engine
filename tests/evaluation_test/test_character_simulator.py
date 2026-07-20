import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.component.simulator.scene_coordinator import SceneCoordinator
from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import ActionCandidateSet, CharacterActionPlan, ProposedAction


SYNTHETIC_CHARACTER_INPUT_CASES = [
    {
        "case_id": "clara_hears_room_7_question",
        "character_id": "character_clara_whitlock",
        "user_input": (
            "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied "
            "before Director Harlan vanished."
        ),
    },
    {
        "case_id": "clara_asked_for_ledger_access",
        "character_id": "character_clara_whitlock",
        "user_input": (
            "Arthur asks Clara to let him see the Visitor's Room Ledger and starts comparing "
            "the Room 7 entry against the dates around Harlan's disappearance."
        ),
    },
    {
        "case_id": "eleanor_notices_arthur_questioning",
        "character_id": "character_eleanor_graves",
        "user_input": (
            "Arthur lowers his voice while speaking to Clara and makes it clear he needs the truth "
            "about Harlan's disappearance."
        ),
    },
    {
        "case_id": "clara_sees_notice_board_search",
        "character_id": "character_clara_whitlock",
        "user_input": (
            "Arthur steps away from the bar and studies the Notice Board, looking under festival "
            "announcements for older papers."
        ),
    },
    {
        "case_id": "eleanor_sees_letter_signature",
        "character_id": "character_eleanor_graves",
        "user_input": (
            "If Clara seems willing to speak privately, Arthur shows her only the signature line "
            "of the anonymous letter and asks whether she recognizes the handwriting."
        ),
    },
]

INPUT_PIPELINE_CASES = [
    {
        "case_id": "ask_clara_room_7",
        "user_input": (
            "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied "
            "before Director Harlan vanished."
        ),
    },
    {
        "case_id": "inspect_ledger",
        "user_input": (
            "I ask Clara to let me see the Visitor's Room Ledger, then compare the Room 7 entry "
            "against the dates around Harlan's disappearance."
        ),
    },
    {
        "case_id": "mixed_speech_and_ooc",
        "user_input": (
            "Arthur lowers his voice and says, \"I am not here to embarrass the town, Miss Whitlock, "
            "but I do need the truth.\" [/OOC: Keep the interpretation focused on the attempted action.]"
        ),
    },
    {
        "case_id": "read_notice_board",
        "user_input": (
            "I step away from the bar for a moment and study the Notice Board, looking for older papers "
            "hidden underneath the festival announcements."
        ),
    },
    {
        "case_id": "reveal_letter_conditionally",
        "user_input": (
            "If Clara seems willing to speak privately, Arthur shows her only the signature line of the "
            "anonymous letter and asks whether she recognizes the handwriting."
        ),
    },
]


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


def _write_case_result(
    *,
    output_path: Path,
    world_id: str,
    simulation_id: str,
    case_order: list[dict],
    case_result: dict,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        output = {
            "world_id": world_id,
            "simulation_id": simulation_id,
            "cases": [],
        }

    cases_by_id = {
        case["case_id"]: case
        for case in output.get("cases", [])
    }
    cases_by_id[case_result["case_id"]] = case_result

    output.update(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "world_id": world_id,
            "simulation_id": simulation_id,
            "cases": [
                cases_by_id[case["case_id"]]
                for case in case_order
                if case["case_id"] in cases_by_id
            ],
        }
    )
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
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
    "case",
    SYNTHETIC_CHARACTER_INPUT_CASES,
    ids=[case["case_id"] for case in SYNTHETIC_CHARACTER_INPUT_CASES],
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
    "case",
    INPUT_PIPELINE_CASES,
    ids=[case["case_id"] for case in INPUT_PIPELINE_CASES],
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
    character_id = "character_arthur_moore"
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
