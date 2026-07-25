import json
from unittest.mock import Mock

from langchain.messages import AIMessage

from world_simulation_engine.misc.enums import MessageRole
from world_simulation_engine.model import (
    ActionProposal,
    ActionValidationResult,
    MemorySummaryProposal,
    PromptMessage,
    SceneCoordinationResult,
    StateCommitProposal,
)
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


def test_schema_guidance_message_lists_required_and_optional_fields_with_descriptions():
    content = LlmService._schema_guidance_text(ActionProposal)

    assert "Output schema field guide for ActionProposal" in content
    assert "- actions: list[ProposedAction] (required)" in content
    assert "- utterance: string | null (optional)" in content
    assert "Keep in-character" in content
    assert "- next_review_hint_seconds: integer (required)" in content


def test_schema_guidance_message_expands_a_repeated_ref_type_only_once():
    content = LlmService._schema_guidance_text(StateCommitProposal)

    # StateCommitEntityRef is referenced by many operation variants; it must be spelled out
    # (with its own sub-fields) but not re-expanded every time it recurs, or the guide would
    # blow past a useful size for a local model's context window.
    assert content.count("- id: string | null (optional) - Existing entity id") == 1
    for variant_type in ("create", "state_change", "promote", "relationship_change", "no_physical_change"):
        assert f"'{variant_type}'" in content
    assert len(content) < 4500


async def test_invoke_structured_with_repair_includes_schema_guidance_in_composed_messages():
    class FakeStructuredModel:
        def __init__(self, parsed):
            self.parsed = parsed
            self.received_messages = None

        async def ainvoke(self, messages, config=None):
            self.received_messages = messages
            return {"raw": AIMessage(content="{}"), "parsed": self.parsed, "parsing_error": None}

    class FakeChatModel:
        def __init__(self, parsed):
            self.structured_model = FakeStructuredModel(parsed)
            self.calls = []

        def with_structured_output(self, output_model, method=None, include_raw=False):
            self.calls.append({"output_model": output_model, "method": method, "include_raw": include_raw})
            return self.structured_model

    parsed = ActionValidationResult(validations=[], validator_notes=[])
    fake_model = FakeChatModel(parsed)
    service = LlmService(model_config=Mock(), connection_config=Mock())
    service._model = fake_model

    result = await service.invoke_structured_with_repair(
        output_model=ActionValidationResult,
        messages=[PromptMessage(role=MessageRole.USER, content="Validate this.")],
        data={},
        repair_instruction="Return valid JSON.",
        run_name="test_run",
    )

    assert result is parsed
    assert fake_model.calls[0]["method"] == "json_schema"
    assert fake_model.calls[0]["include_raw"] is True
    sent_messages = fake_model.structured_model.received_messages
    assert "Output schema field guide for ActionValidationResult" in sent_messages[-1].content


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
