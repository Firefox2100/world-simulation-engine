import json

from langchain.messages import AIMessage

from world_simulation_engine.model import MemorySummaryProposal, SceneCoordinationResult
from world_simulation_engine.service.llm_service import LlmService


def test_truncate_for_repair_caps_large_error_text():
    text = "x" * 50

    result = LlmService._truncate_for_repair(text, 10)

    assert result == "x" * 10 + "... [truncated 40 chars]"


def test_truncate_for_repair_keeps_short_error_text():
    assert LlmService._truncate_for_repair("short", 10) == "short"


def test_parse_raw_with_output_model_uses_model_normalizers_after_parser_failure():
    payload = {
        "operations": [
            {
                "name": "Arthur Inquires About Room 7",
                "summary": (
                    "Arthur asks Clara at the Iron Stag Inn bar whether Room 7 was occupied "
                    "before Director Harlan's disappearance."
                ),
                "reason": "Captures the specific inquiry about Room 7 status.",
                "turn_ids": ["f497bcb7-1566-4c65-a52f-4ca978de616b"],
                "involved_characters": [
                    {
                        "character_id": "da3919d5-c6e0-4c90-98f7-36570e3fb4a6",
                        "involvement": "participate",
                    }
                ],
            },
            {
                "character_id": "da3919d5-c6e0-4c90-98f7-36570e3fb4a6",
                "intent_type": "quest",
                "name": "Investigate Harlan's Disappearance Clues",
                "description": "Gather evidence regarding Director Harlan's disappearance.",
                "priority": 0.6,
                "urgency": 0.5,
                "status": "active",
                "horizon": "short",
                "reason": "Arthur's ongoing investigation goal is formalized.",
            },
        ],
        "summarizer_notes": [],
    }
    raw = AIMessage(content=json.dumps(payload))

    parsed = LlmService._parse_raw_with_output_model(MemorySummaryProposal, raw)

    assert parsed is not None
    assert [operation.type for operation in parsed.operations] == ["create_event", "create_intent"]


def test_parse_raw_with_output_model_extracts_first_json_object_from_prose():
    raw = AIMessage(
        content=(
            "Here is the JSON:\n"
            '{"operations":[{"type":"no_abstract_change","reason":"No durable abstract change."}]}'
            "\nDone."
        )
    )

    parsed = LlmService._parse_raw_with_output_model(MemorySummaryProposal, raw)

    assert parsed is not None
    assert parsed.operations[0].type == "no_abstract_change"


def test_parse_raw_with_output_model_repairs_scene_coordination_action_bracket_slip():
    raw = AIMessage(
        content=(
            '{\n'
            '  "status": "complete",\n'
            '  "accepted_actions": [\n'
            '    {\n'
            '      "actor_id": "character_arthur_moore",\n'
            '      "proposal_index": 0,\n'
            '      "action_index": 0,\n'
            '      "start_offset_seconds": 0,\n'
            '      "end_offset_seconds": 3,\n'
            '      "summary": "Arthur moves.",\n'
            '      "action": {\n'
            '        "type": "move",\n'
            '        "label": "step_away",\n'
            '        "target_ids": [],\n'
            '        "utterance": null,\n'
            '        "intended_duration_seconds": 3,\n'
            '        "interruptible": true,\n'
            '        "interruption_triggers": [],\n'
            '        "required_preconditions": [],\n'
            '        "expected_effects": []\n'
            '      }\n'
            '    ]\n'
            '  },\n'
            '  "problem": null,\n'
            '  "pending_actions": [],\n'
            '  "stopped_reason": null,\n'
            '  "coordinator_notes": []\n'
            '}'
        )
    )

    parsed = LlmService._parse_raw_with_output_model(SceneCoordinationResult, raw)

    assert parsed is not None
    assert parsed.accepted_actions[0].action.label == "step_away"


def test_parse_raw_with_output_model_repairs_scene_coordination_final_action_bracket_slip():
    raw = AIMessage(
        content=(
            '{\n'
            '  "status": "complete",\n'
            '  "accepted_actions": [\n'
            '    {\n'
            '      "actor_id": "character_arthur_moore",\n'
            '      "proposal_index": 0,\n'
            '      "action_index": 0,\n'
            '      "start_offset_seconds": 0,\n'
            '      "end_offset_seconds": 3,\n'
            '      "summary": "Arthur moves.",\n'
            '      "action": {\n'
            '        "type": "move",\n'
            '        "label": "step_away",\n'
            '        "target_ids": [],\n'
            '        "utterance": null,\n'
            '        "intended_duration_seconds": 3,\n'
            '        "interruptible": true,\n'
            '        "interruption_triggers": [],\n'
            '        "required_preconditions": [],\n'
            '        "expected_effects": []\n'
            '      }\n'
            '    ]\n'
            '  ],\n'
            '  "problem": null,\n'
            '  "pending_actions": [],\n'
            '  "stopped_reason": null,\n'
            '  "coordinator_notes": []\n'
            '}'
        )
    )

    parsed = LlmService._parse_raw_with_output_model(SceneCoordinationResult, raw)

    assert parsed is not None
    assert parsed.accepted_actions[0].action.label == "step_away"
