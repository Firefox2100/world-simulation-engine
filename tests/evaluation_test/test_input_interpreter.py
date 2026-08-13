import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter

from workflow_helpers import INPUT_PIPELINE_CASES as EVALUATION_INPUTS, case_ids


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
                for _, case in EVALUATION_INPUTS
                if case["case_id"] in cases_by_id
            ],
        }
    )
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    EVALUATION_INPUTS,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(EVALUATION_INPUTS),
)
async def test_evaluate_input_interpreter_outputs_result(
    case,
    evaluation_seeded_database,
    mock_graph_world_setup,
):
    interpreter = InputInterpreter(database=evaluation_seeded_database)
    character_id = case["user_character_id"]

    interpretation = await interpreter.interpret(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=character_id,
        user_input=case["user_input"],
    )

    # Every case describes an in-character attempt, so at least one item must be produced and
    # at least one of them must be a "action" (not every case dumped entirely into unparsed_text
    # or reduced to only an OOC command).
    assert interpretation.items, f"No items were parsed for case {case['case_id']!r}"
    action_items = [item for item in interpretation.items if item.type == "action"]
    ooc_items = [item for item in interpretation.items if item.type == "ooc"]
    assert action_items, f"No action item was parsed for case {case['case_id']!r}"

    # source_text is documented as "the exact source span"; it must actually come from the
    # original input, not be a paraphrase or hallucinated span.
    for item in interpretation.items:
        assert item.source_text.strip()
        assert item.source_text in case["user_input"], (
            f"source_text {item.source_text!r} is not a literal span of the case input"
        )

    if case["case_id"] == "mixed_speech_and_ooc":
        # This input contains an unambiguous, syntactically self-contained OOC marker
        # ("[/OOC: Keep the interpretation focused on the attempted action.]"), separate from
        # the in-character speech that precedes it - the interpreter must not merge the two.
        assert ooc_items, "The explicit [/OOC: ...] marker was not extracted as an OOCCommand"
        assert ooc_items[0].command_text == "Keep the interpretation focused on the attempted action."

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
