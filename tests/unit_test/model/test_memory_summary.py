from world_simulation_engine.misc.enums import EventInvolvement, IntentHorizon, IntentStatus, IntentType, MemoryStance, \
    MemorySupportType, Salience
from world_simulation_engine.model import MemorySummaryProposal


def test_memory_summary_accepts_legacy_operation_name_discriminator():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "name": "create_event",
                    "summary": (
                        "Arthur Moore asks Clara Whitlock at the bar regarding whether Room 7 "
                        "was occupied before Director Harlan vanished."
                    ),
                    "reason": "The inquiry establishes an active investigative point.",
                    "proposed_id": "evt_78845e9_room7_inquiry",
                    "involved_characters": [
                        {
                            "character_id": "f7da6cbd-d538-4f4f-8a82-d3273858974f",
                            "involvement": "participate",
                        },
                        {
                            "character_id": "clara_whitlock",
                            "involvement": "participate",
                        },
                    ],
                },
                {
                    "name": "create_intent",
                    "summary": "Determine if Room 7 was occupied before Director Harlan vanished.",
                    "reason": "Arthur's question establishes the current investigative thread.",
                    "proposed_id": "int_auditing_room_7_status",
                    "involved_characters": [
                        {
                            "character_id": "f7da6cbd-d538-4f4f-8a82-d3273858974f",
                            "involvement": "participate",
                        }
                    ],
                },
                {
                    "name": "link_turn_to_event",
                    "summary": "",
                    "reason": "The current turn is the primary action driving this new event.",
                    "turn_ids": ["78845e9e-eff2-4e75-9c17-c8d01c66779c"],
                    "involved_characters": [],
                },
            ]
        }
    )

    assert [operation.type for operation in proposal.operations] == ["create_event", "create_intent"]

    event_operation = proposal.operations[0]
    assert event_operation.name.startswith("Arthur Moore asks Clara Whitlock")
    assert event_operation.turn_ids == ["78845e9e-eff2-4e75-9c17-c8d01c66779c"]
    assert event_operation.involved_characters[0].involvement == EventInvolvement.PARTICIPATE

    intent_operation = proposal.operations[1]
    assert intent_operation.character_id == "f7da6cbd-d538-4f4f-8a82-d3273858974f"
    assert intent_operation.intent_type == IntentType.QUEST
    assert intent_operation.status == IntentStatus.ACTIVE
    assert intent_operation.horizon == IntentHorizon.SHORT
    assert intent_operation.priority == 0.5
    assert intent_operation.urgency == 0.5
    assert intent_operation.created_by_event_id == "evt_78845e9_room7_inquiry"


def test_memory_summary_normalizes_legacy_create_memory_character_links():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "name": "create_event",
                    "summary": "Arthur asks Clara whether Room 7 was occupied before Director Harlan vanished.",
                    "reason": "Captures the specific investigative inquiry.",
                    "proposed_id": "evt_room7_inquiry_1912",
                    "involved_characters": [
                        {
                            "character_id": "2ef4fb84-71c2-4a71-8571-a5b86245569a",
                            "involvement": "infer",
                        }
                    ],
                },
                {
                    "name": "create_memory",
                    "summary": "Room 7's occupancy status before the director vanished is under investigation.",
                    "reason": "Directly supports Arthur's private investigation goals.",
                    "proposed_id": "mem_room7_preharlan_1912",
                    "involved_characters": [
                        {
                            "character_id": "2ef4fb84-71c2-4a71-8571-a5b86245569a",
                            "involvement": "participate",
                        }
                    ],
                },
                {
                    "name": "create_intent",
                    "summary": (
                        "Determine if Room 7's occupancy status provides clues about Director Harlan's "
                        "activities or secret research."
                    ),
                    "reason": "Establishes a focused investigative thread.",
                    "proposed_id": "int_investigate_room7_status",
                    "involved_characters": [
                        {
                            "character_id": "2ef4fb84-71c2-4a71-8571-a5b86245569a",
                            "involvement": "infer",
                        }
                    ],
                },
            ]
        }
    )

    assert [operation.type for operation in proposal.operations] == [
        "create_event",
        "create_memory",
        "create_intent",
    ]

    memory_operation = proposal.operations[1]
    assert memory_operation.event_id == "evt_room7_inquiry_1912"
    assert memory_operation.support_type == MemorySupportType.DIRECT
    assert memory_operation.character_links[0].character_id == "2ef4fb84-71c2-4a71-8571-a5b86245569a"
    assert memory_operation.character_links[0].confidence == 0.8
    assert memory_operation.character_links[0].salience == Salience.MEDIUM
    assert memory_operation.character_links[0].stance == MemoryStance.REMEMBER


def test_memory_summary_prefers_legacy_name_discriminator_over_wrong_type():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "name": "create_event",
                    "summary": (
                        "Arthur inquires at the Iron Stag Inn bar about Room 7's occupancy status "
                        "prior to Director Harlan's disappearance."
                    ),
                    "reason": "Starts a focused investigative interaction.",
                },
                {
                    "name": "link_turn_to_event",
                    "summary": "Links current turn (e2ccf7ac-39ae-4958-992a-7bd05d376ee5) to the new event.",
                    "reason": "Turn captures the specific query that initiates the bar inquiry phase.",
                },
                {
                    "name": "create_memory",
                    "summary": (
                        "Arthur recalls: 'Asked Clara whether Room 7 was occupied before Director Harlan vanished.' "
                        "(scoped to Arthur, linked to event)"
                    ),
                    "reason": "Recall-worthy investigative lead regarding timing and the director's quarters.",
                    "type": "create_event",
                    "proposed_id": "evt_room7_inquiry_01",
                },
                {
                    "name": "create_intent",
                    "summary": "Arthur: Investigate Director Harlan's disappearance and payment terms.",
                    "reason": "Establishes Arthur's core investigative driver early on.",
                },
            ]
        }
    )

    assert [operation.type for operation in proposal.operations] == [
        "create_event",
        "no_abstract_change",
        "no_abstract_change",
    ]

    event_operation = proposal.operations[0]
    assert event_operation.proposed_id.startswith("evt_arthur_inquires")
    assert event_operation.turn_ids == ["e2ccf7ac-39ae-4958-992a-7bd05d376ee5"]

    skipped_memory = proposal.operations[1]
    assert skipped_memory.reason == "Recall-worthy investigative lead regarding timing and the director's quarters."

    skipped_intent = proposal.operations[2]
    assert skipped_intent.reason == "Establishes Arthur's core investigative driver early on."


def test_memory_summary_caps_normalized_operations_for_local_model_runaway():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "type": "no_abstract_change",
                    "reason": f"No durable abstract change {index}.",
                }
                for index in range(20)
            ]
        }
    )

    assert len(proposal.operations) == 12


def test_memory_summary_infers_create_event_when_type_is_missing_but_name_is_title():
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "name": "Arthur queries Room occupancy status before Harlan's disappearance",
                    "summary": (
                        "At the bar during the Founder's Festival, Arthur asks Clara whether Director Harlan's "
                        "room (Room 7) was occupied prior to his vanishing three weeks ago."
                    ),
                    "reason": (
                        "Captures a specific investigative step regarding Harlan's timeline and location that "
                        "persists as evidence for future deductions."
                    ),
                    "turn_ids": ["ef1a96a5-b884-4727-857f-c01e45641c8d"],
                    "involved_characters": [
                        {
                            "character_id": "Arthur Moore",
                            "involvement": "participate",
                        },
                        {
                            "character_id": "Clara",
                            "involvement": "participate",
                        },
                    ],
                }
            ],
            "summarizer_notes": [
                "Created an event for Arthur's inquiry into Room 7 occupancy.",
            ],
        }
    )

    assert len(proposal.operations) == 1
    event_operation = proposal.operations[0]
    assert event_operation.type == "create_event"
    assert event_operation.name == "Arthur queries Room occupancy status before Harlan's disappearance"
    assert event_operation.proposed_id.startswith("evt_at_the_bar_during")
    assert event_operation.turn_ids == ["ef1a96a5-b884-4727-857f-c01e45641c8d"]
