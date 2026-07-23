from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from world_simulation_engine.misc.enums import (
    ActionType,
    EventInvolvement,
    IntentHorizon,
    IntentStatus,
    IntentType,
    MemoryStance,
    MemorySupportType,
    Salience,
    SceneCoordinationProblemType,
)
from world_simulation_engine.model import (
    ActionValidation,
    ActionValidationResult,
    AcceptedSceneAction,
    ActionProposal,
    InputInterpretation,
    Intent,
    MemorySummaryProposal,
    ProposedAction,
    SceneCoordinationResult,
    StateCommitProposal,
)


def make_action() -> ProposedAction:
    return ProposedAction(
        type=ActionType.LOOK,
        label="look_around",
        intended_duration_seconds=2,
    )


def test_action_proposal_accepts_primary_sequence_and_backup_sequences():
    primary_first = make_action()
    primary_second = ProposedAction(
        type=ActionType.SPEAK,
        label="answer_question",
        utterance="Yes.",
        intended_duration_seconds=2,
    )
    backup = ProposedAction(
        type=ActionType.WAIT,
        label="wait",
        intended_duration_seconds=3,
    )

    proposal = ActionProposal(
        actions=[primary_first, primary_second],
        backup_proposals=[[backup]],
        reasoning_summary="Act, then speak.",
        next_review_hint_seconds=5,
    )

    assert proposal.actions == [primary_first, primary_second]
    assert proposal.backup_proposals == [[backup]]


def test_action_proposal_wraps_flat_backup_actions_as_single_action_sequences():
    backup_first = ProposedAction(
        type=ActionType.WAIT,
        label="wait",
        intended_duration_seconds=3,
    )
    backup_second = ProposedAction(
        type=ActionType.MOVE,
        label="step_aside",
        intended_duration_seconds=3,
    )

    proposal = ActionProposal.model_validate(
        {
            "actions": [make_action().model_dump()],
            "backup_proposals": [
                backup_first.model_dump(),
                backup_second.model_dump(),
            ],
            "reasoning_summary": "Flat backup actions are single-action alternatives.",
            "next_review_hint_seconds": 5,
        }
    )

    assert proposal.backup_proposals == [[backup_first], [backup_second]]


def test_action_proposal_rejects_legacy_single_action_shape():
    action = make_action()
    backup = ProposedAction(
        type=ActionType.WAIT,
        label="wait",
        intended_duration_seconds=3,
    )

    with pytest.raises(ValidationError):
        ActionProposal.model_validate(
            {
                "chosen_action": action.model_dump(),
                "alternatives_considered": [backup.model_dump()],
                "reasoning_summary": "Legacy shape.",
                "next_review_hint_seconds": 5,
            }
        )


def test_action_validation_forbids_extra_fields_and_negative_indexes():
    with pytest.raises(ValidationError):
        ActionValidationResult.model_validate(
            {
                "validations": [
                    {
                        "action_index": -1,
                        "action": make_action().model_dump(),
                        "allowed": True,
                        "reason": "The action can start.",
                    }
                ],
                "unexpected": "not allowed",
            }
        )


def test_action_validation_result_accepts_single_llm_validation_object():
    result = ActionValidationResult.model_validate(
        {
            "action_index": 0,
            "action": make_action().model_dump(),
            "allowed": True,
            "reason": "The action can start.",
            "blocking_conditions": [],
            "warnings": [],
        }
    )

    assert len(result.validations) == 1
    assert result.validations[0].action_index == 0
    assert result.validations[0].action.label == "look_around"


@pytest.mark.parametrize("wrapper_key", ["action_validations", "validation_results", "results"])
def test_action_validation_result_accepts_known_llm_wrapper_keys(wrapper_key):
    result = ActionValidationResult.model_validate(
        {
            wrapper_key: [
                {
                    "action_index": 0,
                    "action": make_action().model_dump(),
                    "allowed": True,
                    "reason": "The action can start.",
                    "blocking_conditions": [],
                    "warnings": [],
                }
            ]
        }
    )

    assert len(result.validations) == 1
    assert result.validations[0].action_index == 0


def test_action_validation_schema_documents_precondition_gate():
    schema = ActionValidation.model_json_schema()

    assert "required_preconditions" in schema["properties"]["allowed"]["description"]
    assert "unmet required precondition" in schema["properties"]["blocking_conditions"]["description"]


def test_input_interpretation_filters_llm_self_correction_notes():
    result = InputInterpretation.model_validate(
        {
            "items": [
                {
                    "type": "action",
                    "action": make_action().model_dump(),
                    "source_text": "I look around.",
                }
            ],
            "unparsed_text": [],
            "parser_notes": [
                "Target is inferred from the visible room.",
                "Correction: I should produce two items.",
                "Re-evaluating: the examples say to split this.",
            ],
        }
    )

    assert result.parser_notes == ["Target is inferred from the visible room."]


def test_scene_coordination_result_rejects_flat_accepted_action_fields():
    with pytest.raises(ValidationError):
        SceneCoordinationResult.model_validate(
            {
                "status": "complete",
                "accepted_actions": [
                    {
                        "actor_id": "character_1",
                        "proposal_index": 0,
                        "action_index": 0,
                        "start_offset_seconds": 0,
                        "end_offset_seconds": 4,
                        "summary": "Alex looks around.",
                        "type": "look",
                        "label": "look_around",
                        "target_ids": [],
                        "intended_duration_seconds": 4,
                        "interruptible": True,
                    }
                ],
                "pending_actions": [],
                "problem": None,
            }
        )


def test_scene_coordination_result_rejects_candidate_data_as_action():
    with pytest.raises(ValidationError):
        SceneCoordinationResult.model_validate(
            {
                "status": "complete",
                "accepted_actions": [
                    {
                        "actor_id": "character_1",
                        "proposal_index": 0,
                        "action_index": 0,
                        "start_offset_seconds": 0,
                        "end_offset_seconds": 2,
                        "summary": "Alex waits.",
                        "candidate_data": make_action().model_dump(),
                    }
                ],
                "pending_actions": [],
                "problem": None,
                "summary": "A single action was accepted.",
            }
        )


def test_scene_coordination_result_rejects_extra_labels_on_involved_action_references():
    with pytest.raises(ValidationError):
        SceneCoordinationResult.model_validate(
            {
                "status": "problem",
                "accepted_actions": [],
                "problem": {
                    "type": "exclusive_resource",
                    "time_offset_seconds": 0,
                    "involved_actor_ids": ["character_1", "character_2"],
                    "involved_actions": [
                        {
                            "actor_id": "character_1",
                            "proposal_index": 0,
                            "action_index": 0,
                            "label": "look_around",
                        }
                    ],
                    "description": "Two actors target the same object.",
                    "needs_user_decision": False,
                    "actors_to_react": ["character_1", "character_2"],
                    "resolver_required": True,
                },
                "pending_actions": [],
            }
        )


def test_scene_coordination_result_rejects_fractional_second_offsets_from_llm():
    with pytest.raises(ValidationError):
        SceneCoordinationResult.model_validate(
            {
                "status": "problem",
                "accepted_actions": [
                    {
                        "actor_id": "character_1",
                        "proposal_index": 0,
                        "action_index": 0,
                        "start_offset_seconds": 4.1,
                        "end_offset_seconds": 49.1,
                        "summary": "Alex looks around after another action.",
                        "action": make_action().model_dump(),
                    }
                ],
                "problem": {
                    "type": "mutually_incompatible",
                    "time_offset_seconds": 4.1,
                    "involved_actor_ids": ["character_1"],
                    "involved_actions": [
                        {
                            "actor_id": "character_1",
                            "proposal_index": 0,
                            "action_index": 0,
                        }
                    ],
                    "description": "The action overlaps another actor.",
                    "needs_user_decision": False,
                    "actors_to_react": ["character_1"],
                    "resolver_required": False,
                },
                "pending_actions": [],
            }
        )


def test_scene_coordination_result_rejects_interruption_alias_and_string_notes():
    with pytest.raises(ValidationError):
        SceneCoordinationResult.model_validate(
            {
                "status": "problem",
                "accepted_actions": [],
                "problem": {
                    "type": "simultaneous_interruption_contention",
                    "time_offset_seconds": 0,
                    "involved_actor_ids": ["character_1", "character_2"],
                    "involved_actions": [
                        {
                            "actor_id": "character_1",
                            "proposal_index": 0,
                            "action_index": 0,
                        },
                        {
                            "actor_id": "character_2",
                            "proposal_index": 0,
                            "action_index": 0,
                        },
                    ],
                    "description": "Two actors try to take conversational focus at the same time.",
                    "needs_user_decision": False,
                    "actors_to_react": ["character_2"],
                    "resolver_required": False,
                },
                "pending_actions": [],
                "coordinator_notes": "Both actors start speaking at t=0.",
            }
        )


def test_scene_coordination_schema_requires_nested_action_for_accepted_actions():
    schema = AcceptedSceneAction.model_json_schema()

    assert "action" in schema["required"]


def test_state_commit_proposal_rejects_unknown_operation_type():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "operations": [
                    {
                        "type": "delete",
                        "entity": {
                            "type": "item",
                            "id": "item_1",
                        },
                        "reason": "Deletion is intentionally outside this contract.",
                    }
                ]
            }
        )


def test_state_commit_proposal_accepts_current_state_change_shape():
    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "state_change",
                    "entity": {
                        "type": "character",
                        "id": "character_arthur_moore",
                    },
                    "field_changes": [
                        {
                            "field_path": "current_activity",
                            "old_value": "standing at the bar",
                            "new_value": "questioning Clara at the bar",
                            "reason": "Arthur starts questioning Clara.",
                        }
                    ],
                    "source_action_refs": ["accepted:0"],
                    "reason": "Arthur starts questioning Clara.",
                }
            ],
            "committer_notes": ["Uses the current StateCommitProposal shape."],
        }
    )

    assert len(proposal.operations) == 1
    operation = proposal.operations[0]
    assert operation.type == "state_change"
    assert operation.entity.id == "character_arthur_moore"
    assert operation.field_changes[0].field_path == "current_activity"


def test_state_commit_proposal_rejects_legacy_wrapper_shape():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "state_commit_proposal": {
                    "operations": [
                        {
                            "type": "no_physical_change",
                            "source_action_refs": ["accepted:0"],
                            "reason": "No change.",
                        }
                    ]
                }
            }
        )


def test_state_commit_proposal_rejects_legacy_operation_keys():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "operations": [
                    {
                        "op": "relationship_change",
                        "entity_id": "item_room_7_cash_receipt",
                        "field_path": "held_by",
                        "new_value": "character_arthur_moore",
                        "source_action_refs": ["accepted:0"],
                    }
                ]
            }
        )


def test_state_commit_proposal_accepts_current_relationship_shape():
    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "relationship_change",
                    "relationship_type": "held_by",
                    "subject": {
                        "type": "item",
                        "id": "item_room_7_cash_receipt",
                    },
                    "object": {
                        "type": "character",
                        "id": "character_arthur_moore",
                    },
                    "old_object": None,
                    "properties": {},
                    "ended": False,
                    "source_action_refs": ["accepted:0"],
                    "reason": "The receipt changes hands.",
                }
            ],
            "committer_notes": [
                "The receipt changes hands.",
            ],
        }
    )

    assert len(proposal.operations) == 1
    operation = proposal.operations[0]
    assert operation.type == "relationship_change"
    assert operation.relationship_type == "held_by"
    assert operation.subject.id == "item_room_7_cash_receipt"
    assert operation.object
    assert operation.object.id == "character_arthur_moore"


def test_state_commit_relationship_change_requires_known_relationship_type():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "operations": [
                    {
                        "type": "relationship_change",
                        "relationship_type": "teleported_to",
                        "subject": {
                            "type": "character",
                            "id": "character_1",
                        },
                        "object": {
                            "type": "location",
                            "id": "location_1",
                        },
                        "reason": "Unknown relationship types should be rejected.",
                    }
                ]
            }
        )


def test_memory_summary_proposal_accepts_full_abstract_operation_mix():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "type": "create_event",
                    "proposed_id": "event_1",
                    "name": "Door Opened",
                    "summary": "Alex opened the sealed door.",
                    "turn_ids": ["turn_1"],
                    "involved_characters": [
                        {
                            "character_id": "character_1",
                            "involvement": EventInvolvement.PARTICIPATE,
                        }
                    ],
                    "reason": "A notable scene event occurred.",
                },
                {
                    "type": "create_memory",
                    "event_id": "event_1",
                    "summary": "Alex opened the sealed door.",
                    "keywords": ["door", "opened"],
                    "support_type": MemorySupportType.DIRECT,
                    "character_links": [
                        {
                            "character_id": "character_1",
                            "confidence": 1,
                            "salience": Salience.HIGH,
                            "stance": MemoryStance.REMEMBER,
                        }
                    ],
                    "reason": "The actor should remember this.",
                },
                {
                    "type": "create_intent",
                    "character_id": "character_1",
                    "intent_type": IntentType.QUEST,
                    "name": "Explore beyond the door",
                    "description": "Find out what lies beyond the door.",
                    "priority": 0.8,
                    "urgency": 0.4,
                    "status": IntentStatus.ACTIVE,
                    "deadline": datetime(2026, 1, 2, 12, tzinfo=UTC),
                    "horizon": IntentHorizon.SHORT,
                    "reason": "The event opened a new thread.",
                },
                {
                    "type": "update_intent",
                    "intent_id": "intent_1",
                    "status": IntentStatus.PAUSED,
                    "event_id": "event_1",
                    "event_relationship": "contributes_to",
                    "reason": "The event changes the current plan.",
                },
                {
                    "type": "no_abstract_change",
                    "reason": "No additional abstract records are needed.",
                },
            ]
        }
    )

    assert [operation.type for operation in proposal.operations] == [
        "create_event",
        "create_memory",
        "create_intent",
        "update_intent",
        "no_abstract_change",
    ]


def test_memory_summary_rejects_physical_state_operations_and_invalid_confidence():
    with pytest.raises(ValidationError):
        MemorySummaryProposal.model_validate(
            {
                "operations": [
                    {
                        "type": "state_change",
                        "reason": "Physical state belongs to StateCommitProposal.",
                    }
                ]
            }
        )

    with pytest.raises(ValidationError):
        MemorySummaryProposal.model_validate(
            {
                "operations": [
                    {
                        "type": "create_memory",
                        "event_id": "event_1",
                        "summary": "Alex saw the door.",
                        "support_type": MemorySupportType.DIRECT,
                        "character_links": [
                            {
                                "character_id": "character_1",
                                "confidence": 1.1,
                                "salience": Salience.MEDIUM,
                                "stance": MemoryStance.REMEMBER,
                            }
                        ],
                        "reason": "Confidence must be bounded.",
                    }
                ]
            }
        )


def test_intent_priority_and_urgency_are_bounded():
    with pytest.raises(ValidationError):
        Intent(
            type=IntentType.AGENDA,
            name="Overbounded intent",
            description="Invalid scores should not pass.",
            priority=1.2,
            urgency=-0.1,
            status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.SHORT,
        )
