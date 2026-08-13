import json
from unittest.mock import Mock

import pytest
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


def test_parse_raw_with_output_model_repairs_state_commit_missing_operation_types():
    # Reproduces a live failure: a local model's structured output for StateCommitProposal
    # dropped the "type" discriminator on every operation, which previously failed the whole
    # turn after exhausting all retries. The first operation also wraps a relationship_change
    # in a promote-shaped container with no promote-specific fields, which must be unwrapped
    # rather than accepted as an actual promotion (that would create a spurious entity).
    payload = {
        "operations": [
            {
                "source_entity": {"type": "character", "id": "f6c11ed5-1e5c-473c-9ef4-67894a9fe9a0"},
                "target_entity_type": "character",
                "reason": "Arthur approaches and directly engages with Clara at the bar.",
                "relationship_changes": [
                    {
                        "relationship_type": "interacting_with",
                        "subject": {"type": "character", "id": "f6c11ed5-1e5c-473c-9ef4-67894a9fe9a0"},
                        "reason": "Arthur approaches and directly engages with Clara at the bar.",
                        "object": {"type": "character", "id": "343ced70-96dd-405a-8832-040107b9d013"},
                        "old_object": None,
                        "properties": {},
                        "ended": False,
                        "source_action_refs": ["accepted:0"],
                    }
                ],
                "source_action_refs": ["accepted:0"],
            },
            {
                "reason": "Speech only; Arthur's current activity, location, and public state remain consistent.",
                "source_action_refs": ["accepted:1"],
            },
        ],
        "unchanged_action_refs": [],
        "committer_notes": [
            "Arthur is already at the bar with Clara behind it; approach confirms interaction.",
            "Room rental query and history are abstract dialogue updates, not physical changes.",
        ],
    }
    raw = AIMessage(content=json.dumps(payload))

    parsed = LlmService._parse_raw_with_output_model(StateCommitProposal, raw)

    assert parsed is not None
    assert [operation.type for operation in parsed.operations] == [
        "relationship_change",
        "no_physical_change",
    ]
    relationship_operation = parsed.operations[0]
    assert relationship_operation.relationship_type == "interacting_with"
    assert relationship_operation.object.id == "343ced70-96dd-405a-8832-040107b9d013"


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


async def test_invoke_structured_with_repair_retries_when_validate_result_rejects_output():
    # validate_result lets a caller reject a schema-valid-but-cross-referentially-wrong result
    # (e.g. state_committer checking every accepted action index is accounted for) and feed the
    # same repair-and-retry loop a parsing/validation failure would - it must not be treated as
    # success just because the shape parsed fine.
    class FakeStructuredModel:
        def __init__(self, parsed_sequence):
            self.parsed_sequence = list(parsed_sequence)
            self.call_count = 0

        async def ainvoke(self, messages, config=None):
            parsed = self.parsed_sequence[self.call_count]
            self.call_count += 1
            return {"raw": AIMessage(content="{}"), "parsed": parsed, "parsing_error": None}

    class FakeChatModel:
        def __init__(self, structured_model):
            self.structured_model = structured_model

        def with_structured_output(self, output_model, method=None, include_raw=False):
            return self.structured_model

    incomplete = ActionValidationResult(validations=[], validator_notes=["missing"])
    complete = ActionValidationResult(validations=[], validator_notes=["ok"])
    structured_model = FakeStructuredModel([incomplete, complete])
    fake_model = FakeChatModel(structured_model)
    service = LlmService(model_config=Mock(), connection_config=Mock())
    service._model = fake_model

    def validate_result(result: ActionValidationResult) -> None:
        if result.validator_notes != ["ok"]:
            raise ValueError("not ok yet")

    result = await service.invoke_structured_with_repair(
        output_model=ActionValidationResult,
        messages=[PromptMessage(role=MessageRole.USER, content="Validate this.")],
        data={},
        repair_instruction="Return valid JSON.",
        run_name="test_run",
        validate_result=validate_result,
    )

    assert result is complete
    assert structured_model.call_count == 2


async def test_invoke_structured_with_repair_raises_after_max_attempts_when_validate_result_never_passes():
    class FakeStructuredModel:
        def __init__(self, parsed):
            self.parsed = parsed
            self.call_count = 0

        async def ainvoke(self, messages, config=None):
            self.call_count += 1
            return {"raw": AIMessage(content="{}"), "parsed": self.parsed, "parsing_error": None}

    class FakeChatModel:
        def __init__(self, structured_model):
            self.structured_model = structured_model

        def with_structured_output(self, output_model, method=None, include_raw=False):
            return self.structured_model

    always_incomplete = ActionValidationResult(validations=[], validator_notes=["missing"])
    structured_model = FakeStructuredModel(always_incomplete)
    fake_model = FakeChatModel(structured_model)
    service = LlmService(model_config=Mock(), connection_config=Mock())
    service._model = fake_model

    def validate_result(result: ActionValidationResult) -> None:
        raise ValueError("never satisfied")

    with pytest.raises(RuntimeError, match="test_run failed after 3 attempts"):
        await service.invoke_structured_with_repair(
            output_model=ActionValidationResult,
            messages=[PromptMessage(role=MessageRole.USER, content="Validate this.")],
            data={},
            repair_instruction="Return valid JSON.",
            run_name="test_run",
            validate_result=validate_result,
        )

    assert structured_model.call_count == 3


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
