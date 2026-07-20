from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from world_simulation_engine.component.simulator.character_simulator import CharacterPerspective, CharacterSimulator
from world_simulation_engine.misc.enums import ActionType, MemoryStance, MemorySupportType, Salience, SupportedLanguage
from world_simulation_engine.model import ActionProposal, Character, CurrentActivity, Event, Location, MemoryAtom
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
            "actions": [
                {
                    "type": ActionType.OBSERVE,
                    "label": "inspect_notice_board",
                    "target_ids": ["landmark_notice_board"],
                    "utterance": None,
                    "intended_duration_seconds": 15,
                    "interruptible": True,
                    "interruption_triggers": [],
                    "required_preconditions": [],
                    "expected_effects": [],
                }
            ],
            "backup_proposals": [],
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


def make_character_perspective() -> CharacterPerspective:
    return CharacterPerspective(
        actor=Character(
            id="character_clara",
            name="Clara Whitlock",
            age=42,
            gender="female",
            appearance="Plain",
            description="The innkeeper",
            public_state="Behind the bar",
            private_state="Careful with what she says",
            current_activity=CurrentActivity(name="listening to Arthur"),
        ),
        world_time=datetime(1912, 9, 21, 19, 30, 0),
        location=Location(
            id="location_bar",
            name="Iron Stag Inn - Bar",
            description="A busy inn bar",
        ),
    )


async def test_character_simulator_repairs_speak_action_without_utterance():
    simulator = CharacterSimulator(database=Mock(), langfuse_handler=None)
    proposal = ActionProposal(
        actions=[
            {
                "type": ActionType.SPEAK,
                "label": "answer_room_occupancy_question",
                "target_ids": ["character_arthur"],
                "utterance": None,
                "intended_duration_seconds": 6,
                "interruptible": True,
                "expected_effects": ["Clara answers Arthur's question about Room 7."],
            }
        ],
        reasoning_summary="Clara can answer Arthur's question about Room 7.",
        memory_updates_suggested=["Room 7 was occupied before Director Harlan vanished."],
        next_review_hint_seconds=10,
    )
    llm = Mock()
    llm.invoke_text = AsyncMock(
        return_value="Yes, Arthur. Room 7 was occupied before Director Harlan vanished."
    )

    repaired = await simulator._ensure_speak_actions_have_utterance(
        proposal=proposal,
        perspective=make_character_perspective(),
        language=SupportedLanguage.ENGLISH,
        llm=llm,
        run_name="test.repair_speech",
    )

    assert repaired.actions[0].utterance == (
        "Yes, Arthur. Room 7 was occupied before Director Harlan vanished."
    )
    llm.invoke_text.assert_awaited_once()
    assert repaired.actions[0].label == proposal.actions[0].label
    assert repaired.reasoning_summary == proposal.reasoning_summary


async def test_character_simulator_sanitizes_plain_text_speech_repair():
    simulator = CharacterSimulator(database=Mock(), langfuse_handler=None)
    proposal = ActionProposal(
        actions=[
            {
                "type": ActionType.SPEAK,
                "label": "answer_room_occupancy_question",
                "target_ids": ["character_arthur"],
                "utterance": None,
                "intended_duration_seconds": 6,
                "interruptible": True,
                "expected_effects": ["Clara answers Arthur's question about Room 7."],
            }
        ],
        reasoning_summary="Clara can answer Arthur's question about Room 7.",
        next_review_hint_seconds=10,
    )
    llm = Mock()
    llm.invoke_text = AsyncMock(return_value='utterance: "Yes, Arthur."')

    repaired = await simulator._ensure_speak_actions_have_utterance(
        proposal=proposal,
        perspective=make_character_perspective(),
        language=SupportedLanguage.ENGLISH,
        llm=llm,
        run_name="test.repair_speech",
    )

    assert repaired.actions[0].utterance == "Yes, Arthur."


async def test_character_simulator_falls_back_when_speech_repair_llm_fails():
    simulator = CharacterSimulator(database=Mock(), langfuse_handler=None)
    proposal = ActionProposal(
        actions=[
            {
                "type": ActionType.SPEAK,
                "label": "answer_room_occupancy_question",
                "target_ids": ["character_arthur"],
                "utterance": None,
                "intended_duration_seconds": 6,
                "interruptible": True,
                "expected_effects": ["Clara answers Arthur's question about Room 7."],
            }
        ],
        reasoning_summary="Clara can answer Arthur's question about Room 7.",
        memory_updates_suggested=["Room 7 was occupied before Director Harlan vanished."],
        next_review_hint_seconds=10,
    )
    llm = Mock()
    llm.invoke_text = AsyncMock(side_effect=RuntimeError("bad local output"))

    repaired = await simulator._ensure_speak_actions_have_utterance(
        proposal=proposal,
        perspective=make_character_perspective(),
        language=SupportedLanguage.ENGLISH,
        llm=llm,
        run_name="test.repair_speech",
    )

    assert repaired.actions[0].utterance == "Room 7 was occupied before Director Harlan vanished."
