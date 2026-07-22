from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from world_simulation_engine.component.simulator.emotion_updater import EmotionUpdater
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import (
    Character,
    CurrentActivity,
    EmotionState,
    EmotionUpdateProposal,
    EmotionVector,
    MemoryAtom,
    ProposedEmotionChange,
    Simulation,
    World,
)
from world_simulation_engine.service.database.emotion_store import EmotionStore


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_database(*, enabled=True, existing=None):
    database = Mock()
    database.simulation.get_simulation = AsyncMock(return_value=Simulation(
        id="simulation_1",
        name="Simulation",
        current_time=NOW,
        emotion_enabled=enabled,
    ))
    database.character.get_character = AsyncMock(return_value=Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="Actor",
        public_state="Present",
        private_state="Reflecting",
        current_activity=CurrentActivity(name="idle"),
    ))
    database.world.get_world_by_simulation = AsyncMock(return_value=World(
        id="world_1",
        name="World",
        description="World",
        starting_time=NOW,
        version=1,
        language=SupportedLanguage.ENGLISH,
    ))
    database.memory.get_memory = AsyncMock(return_value=MemoryAtom(
        id="memory_1",
        summary="Blair threatened Alex.",
        keywords=["threat"],
        embedding=None,
    ))
    database.emotion.get_state = AsyncMock(return_value=existing)
    database.emotion.validate_memory_evidence = AsyncMock(return_value=True)
    database.emotion.decay_state = EmotionStore.decay_state
    database.emotion.combined_vector = EmotionStore.combined_vector
    database.emotion.create_state = AsyncMock(side_effect=lambda state: state)
    database.emotion.update_state = AsyncMock(side_effect=lambda state: state)
    database.emotion.create_change_audit = AsyncMock(side_effect=lambda audit: audit)
    return database


async def test_emotion_update_is_bounded_and_audited():
    database = make_database()
    updater = EmotionUpdater(database=database)
    updater._prepare_prompt = AsyncMock(return_value=[])
    updater._prepare_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(return_value=EmotionUpdateProposal(
            change=ProposedEmotionChange(
                immediate_delta=EmotionVector(
                    valence=-1,
                    arousal=1,
                    dominance=-1,
                    dimensions={"fear": 1, "surprise": 1},
                ),
                baseline_delta=EmotionVector(valence=-1),
                evidence_memory_ids=["memory_1"],
                reason="A direct threat causes distress.",
            ),
        )),
    ))

    result = await updater.update_from_memories(
        simulation_id="simulation_1",
        character_id="character_1",
        turn_id="turn_1",
        memory_ids=["memory_1"],
    )

    stored = database.emotion.create_state.await_args.args[0]
    assert result.applied is True
    assert stored.immediate.valence == -0.35
    assert stored.immediate.arousal == 0.35
    assert stored.immediate.dominance == -0.35
    assert stored.immediate.dimensions == {"fear": 0.35}
    assert stored.baseline.valence == -0.05
    audit = database.emotion.create_change_audit.await_args.args[0]
    assert audit.turn_id == "turn_1"
    assert audit.evidence_memory_ids == ["memory_1"]


async def test_emotion_update_rejects_memory_not_committed_for_this_pass():
    database = make_database()
    updater = EmotionUpdater(database=database)
    updater._prepare_prompt = AsyncMock(return_value=[])
    updater._prepare_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(return_value=EmotionUpdateProposal(
            change=ProposedEmotionChange(
                immediate_delta=EmotionVector(arousal=0.2),
                evidence_memory_ids=["old_memory"],
                reason="Unsupported.",
            ),
        )),
    ))

    result = await updater.update_from_memories(
        simulation_id="simulation_1",
        character_id="character_1",
        turn_id="turn_1",
        memory_ids=["memory_1"],
    )

    assert result.applied is False
    database.emotion.create_state.assert_not_awaited()
    database.emotion.create_change_audit.assert_not_awaited()


async def test_disabled_emotion_preserves_workflow_without_llm_or_storage():
    database = make_database(enabled=False)
    updater = EmotionUpdater(database=database)
    updater._prepare_llm_service = AsyncMock()

    result = await updater.update_from_memories(
        simulation_id="simulation_1",
        character_id="character_1",
        turn_id="turn_1",
        memory_ids=["memory_1"],
    )

    assert result.applied is False
    updater._prepare_llm_service.assert_not_awaited()
    database.character.get_character.assert_not_awaited()


async def test_existing_state_decays_before_event_delta_and_versions_once():
    existing = EmotionState(
        id="emotion_1",
        simulation_id="simulation_1",
        character_id="character_1",
        immediate=EmotionVector(arousal=0.4),
        immediate_half_life_seconds=3600,
        last_updated_at=NOW.replace(hour=11),
    )
    database = make_database(existing=existing)
    updater = EmotionUpdater(database=database)
    updater._prepare_prompt = AsyncMock(return_value=[])
    updater._prepare_llm_service = AsyncMock(return_value=SimpleNamespace(
        invoke_structured_with_repair=AsyncMock(return_value=EmotionUpdateProposal(
            change=ProposedEmotionChange(
                immediate_delta=EmotionVector(arousal=0.1),
                evidence_memory_ids=["memory_1"],
                reason="Renewed concern.",
            ),
        )),
    ))

    await updater.update_from_memories(
        simulation_id="simulation_1",
        character_id="character_1",
        turn_id="turn_1",
        memory_ids=["memory_1"],
    )

    stored = database.emotion.update_state.await_args.args[0]
    assert stored.immediate.arousal == pytest.approx(0.3)
    assert stored.version == 2
