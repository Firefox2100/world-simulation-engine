from datetime import datetime, timedelta

import pytest

from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.misc.enums import ActionType, MemoryStance, MemorySupportType, Salience
from world_simulation_engine.model import ActionProposal, Event, MemoryAtom
from world_simulation_engine.service.database.memory_store import MemoryRecallRecord


def make_memory_record(
    *,
    memory_id: str = "memory_1",
    confidence: float = 0.8,
    ended_at: datetime | None = None,
) -> MemoryRecallRecord:
    return MemoryRecallRecord(
        memory=MemoryAtom(
            id=memory_id,
            summary="Alex saw the sealed door.",
            keywords=["door", "sealed"],
            embedding=[0.1, 0.2, 0.3],
        ),
        event=Event(
            id="event_1",
            name="Door discovery",
            summary="Alex discovered a sealed door.",
        ),
        event_ending_time=ended_at or datetime(2026, 1, 1, 12, 0, 0),
        support_type=MemorySupportType.DIRECT,
        confidence=confidence,
        salience=Salience.HIGH,
        behavioural_relevance="Avoid assuming the door is open.",
        stance=MemoryStance.REMEMBER,
    )


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ([1, 0], [1, 0], 1.0),
        ([1, 0], [0, 1], 0.0),
        ([1, 2, 3], [1, 2], 0.0),
        ([0, 0], [1, 2], 0.0),
        ([], [1, 2], 0.0),
    ],
)
def test_cosine_similarity_handles_normal_and_invalid_vectors(left, right, expected):
    assert CharacterSimulator._cosine_similarity(left, right) == pytest.approx(expected)


def test_decayed_confidence_halves_after_one_half_life():
    record = make_memory_record(
        confidence=0.8,
        ended_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    current_time = record.event_ending_time + timedelta(days=30)

    assert CharacterSimulator._decayed_confidence(record, current_time) == pytest.approx(0.4)


def test_decayed_confidence_does_not_penalize_future_records():
    record = make_memory_record(
        confidence=0.8,
        ended_at=datetime(2026, 1, 2, 12, 0, 0),
    )

    assert CharacterSimulator._decayed_confidence(record, datetime(2026, 1, 1, 12, 0, 0)) == 0.8


def test_recalled_memory_from_record_preserves_source_metadata():
    record = make_memory_record()

    recalled = CharacterSimulator._recalled_memory_from_record(
        record=record,
        current_time=record.event_ending_time,
        recall_sources=["recent_event", "embedding_match"],
        similarity=0.75,
    )

    assert recalled.memory.id == record.memory.id
    assert recalled.event_id == "event_1"
    assert recalled.confidence == 0.8
    assert recalled.decayed_confidence == 0.8
    assert recalled.recall_sources == ["recent_event", "embedding_match"]
    assert recalled.similarity == 0.75


def test_action_proposal_accepts_object_shaped_memory_update_suggestions():
    proposal = ActionProposal.model_validate(
        {
            "chosen_action": {
                "type": ActionType.OBSERVE,
                "label": "inspect_notice_board",
                "target_ids": ["landmark_notice_board"],
                "utterance": None,
                "intended_duration_seconds": 15,
                "interruptible": True,
                "interruption_triggers": [],
                "required_preconditions": [],
                "expected_effects": [],
            },
            "alternatives_considered": [],
            "reasoning_summary": "Clara wants to check the notices.",
            "risk_flags": [],
            "memory_updates_suggested": [
                {
                    "key": "notice_board_older_papers",
                    "value": "Found papers related to Harlan.",
                    "confidence": 0.8,
                    "type": "fact",
                }
            ],
            "next_review_hint_seconds": 20,
        }
    )

    assert proposal.memory_updates_suggested == [
        "notice_board_older_papers; Found papers related to Harlan.; confidence=0.8"
    ]
