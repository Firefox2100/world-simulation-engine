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
)
from world_simulation_engine.model import (
    ActionValidationResult,
    Intent,
    MemorySummaryProposal,
    ProposedAction,
    StateCommitProposal,
)


def make_action() -> ProposedAction:
    return ProposedAction(
        type=ActionType.LOOK,
        label="look_around",
        intended_duration_seconds=2,
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
