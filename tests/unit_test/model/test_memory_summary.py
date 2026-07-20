import pytest
from pydantic import ValidationError

from world_simulation_engine.misc.enums import EventInvolvement, IntentHorizon, IntentStatus, IntentType, MemoryStance, \
    MemorySupportType, Salience
from world_simulation_engine.model import MemorySummaryProposal


def test_memory_summary_rejects_legacy_operation_name_discriminator():
    with pytest.raises(ValidationError):
        MemorySummaryProposal.model_validate(
            {
                "operations": [
                    {
                        "name": "create_event",
                        "summary": "Arthur asks Clara whether Room 7 was occupied.",
                        "reason": "The inquiry establishes an active investigative point.",
                    },
                ]
            }
        )


def test_memory_summary_rejects_legacy_create_memory_character_links():
    with pytest.raises(ValidationError):
        MemorySummaryProposal.model_validate(
            {
                "operations": [
                    {
                        "type": "create_memory",
                        "event_id": "evt_room7_inquiry_1912",
                        "summary": "Room 7's occupancy status before the director vanished is under investigation.",
                        "support_type": MemorySupportType.DIRECT,
                        "involved_characters": [
                            {
                                "character_id": "2ef4fb84-71c2-4a71-8571-a5b86245569a",
                                "involvement": "participate",
                            }
                        ],
                        "reason": "Directly supports Arthur's private investigation goals.",
                    },
                ]
            }
        )


def test_memory_summary_uses_type_discriminator_as_authoritative():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "type": "create_event",
                    "proposed_id": "evt_room7_inquiry_01",
                    "name": "Arthur recalls asking Clara about Room 7.",
                    "summary": "Arthur recalls asking Clara about Room 7.",
                    "reason": "The type discriminator is authoritative.",
                },
            ]
        }
    )

    assert proposal.operations[0].type == "create_event"


def test_memory_summary_accepts_current_operation_shape():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "type": "create_event",
                    "proposed_id": "evt_room7_inquiry",
                    "name": "Arthur asks about Room 7",
                    "summary": "Arthur asks Clara whether Room 7 was occupied before Director Harlan vanished.",
                    "turn_ids": ["turn_1"],
                    "involved_characters": [
                        {
                            "character_id": "character_arthur",
                            "involvement": EventInvolvement.PARTICIPATE,
                        }
                    ],
                    "reason": "The inquiry is a durable event.",
                },
                {
                    "type": "create_memory",
                    "event_id": "evt_room7_inquiry",
                    "summary": "Arthur remembers asking Clara about Room 7 occupancy.",
                    "keywords": ["Room 7", "Clara"],
                    "support_type": MemorySupportType.DIRECT,
                    "character_links": [
                        {
                            "character_id": "character_arthur",
                            "confidence": 0.8,
                            "salience": Salience.MEDIUM,
                            "stance": MemoryStance.REMEMBER,
                        },
                    ],
                    "reason": "The actor should remember this inquiry.",
                },
                {
                    "type": "create_intent",
                    "character_id": "character_arthur",
                    "intent_type": IntentType.QUEST,
                    "name": "Investigate Room 7",
                    "description": "Find out how Room 7 relates to Harlan's disappearance.",
                    "priority": 0.5,
                    "urgency": 0.5,
                    "status": IntentStatus.ACTIVE,
                    "horizon": IntentHorizon.SHORT,
                    "created_by_event_id": "evt_room7_inquiry",
                    "reason": "The inquiry creates a focused investigative thread.",
                },
            ],
            "summarizer_notes": [
                "Created event, memory, and intent.",
            ],
        }
    )

    assert [operation.type for operation in proposal.operations] == [
        "create_event",
        "create_memory",
        "create_intent",
    ]
    event_operation = proposal.operations[0]
    assert event_operation.turn_ids == ["turn_1"]
    memory_operation = proposal.operations[1]
    assert memory_operation.character_links[0].stance == MemoryStance.REMEMBER
    intent_operation = proposal.operations[2]
    assert intent_operation.status == IntentStatus.ACTIVE
