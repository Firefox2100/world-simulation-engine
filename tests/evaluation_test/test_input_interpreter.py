import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter


EVALUATION_INPUTS = [
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


def _output_path() -> Path:
    return Path(
        os.getenv(
            "WSE_EVAL_INPUT_INTERPRETER_OUTPUT",
            "tests/evaluation_test/output/input_interpreter_results.json",
        )
    )


def _write_case_result(
    *,
    output_path: Path,
    world_id: str,
    simulation_id: str,
    character_id: str,
    case_result: dict,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        output = {
            "world_id": world_id,
            "simulation_id": simulation_id,
            "character_id": character_id,
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
            "character_id": character_id,
            "cases": [
                cases_by_id[case["case_id"]]
                for case in EVALUATION_INPUTS
                if case["case_id"] in cases_by_id
            ],
        }
    )
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "case",
    EVALUATION_INPUTS,
    ids=[case["case_id"] for case in EVALUATION_INPUTS],
)
async def test_evaluate_input_interpreter_outputs_result(
    case,
    evaluation_seeded_database,
    mock_graph_world_setup,
):
    interpreter = InputInterpreter(database=evaluation_seeded_database)
    character_id = "character_arthur_moore"

    interpretation = await interpreter.interpret(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        user_input=case["user_input"],
    )

    _write_case_result(
        output_path=_output_path(),
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        case_result={
            "case_id": case["case_id"],
            "user_input": case["user_input"],
            "interpretation": interpretation.model_dump(mode="json"),
        },
    )
