from datetime import UTC, datetime, timedelta

import pytest

from world_simulation_engine.model import EmotionState, EmotionVector
from world_simulation_engine.service.database.emotion_store import EmotionStore


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_emotion_decay_uses_elapsed_simulation_time_and_half_lives():
    state = EmotionState(
        simulation_id="simulation_1",
        character_id="character_1",
        baseline=EmotionVector(valence=0.8, arousal=0.4, dominance=-0.2),
        immediate=EmotionVector(valence=-0.6, arousal=1, dominance=0.5),
        baseline_half_life_seconds=7200,
        immediate_half_life_seconds=3600,
        last_updated_at=NOW,
    )

    first = EmotionStore.decay_state(state, NOW + timedelta(hours=1))
    repeated = EmotionStore.decay_state(state, NOW + timedelta(hours=1))

    assert first == repeated
    assert first.baseline.valence == pytest.approx(0.8 * 2 ** -0.5)
    assert first.immediate.valence == pytest.approx(-0.3)
    assert first.immediate.arousal == pytest.approx(0.5)
    assert state.last_updated_at == NOW


def test_combined_emotion_clamps_baseline_plus_immediate():
    state = EmotionState(
        simulation_id="simulation_1",
        character_id="character_1",
        baseline=EmotionVector(valence=0.8, dimensions={"fear": 0.7}),
        immediate=EmotionVector(valence=0.5, dimensions={"fear": 0.6}),
        last_updated_at=NOW,
    )

    combined = EmotionStore.combined_vector(state)

    assert combined.valence == 1
    assert combined.dimensions == {"fear": 1}
