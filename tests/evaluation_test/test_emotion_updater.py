from world_simulation_engine.component.simulator.emotion_updater import EmotionUpdater
from world_simulation_engine.misc.enums import ComponentType


async def test_evaluate_emotion_updater_returns_bounded_audited_response(
        evaluation_seeded_database,
        evaluation_chat_model_config,
        mock_graph_world_setup,
):
    """Exercise the compact single-character emotion schema with the configured model."""
    simulation_id = mock_graph_world_setup.simulation.id
    await evaluation_seeded_database.config.link_chat(
        source_id=simulation_id,
        config_id=evaluation_chat_model_config.id,
        component=ComponentType.MEMORY_SUMMARIZER,
    )

    result = await EmotionUpdater(database=evaluation_seeded_database).update_from_memories(
        simulation_id=simulation_id,
        character_id="character_arthur_moore",
        turn_id=mock_graph_world_setup.initial_turn.id,
        memory_ids=["memory_disappearance_threads"],
    )

    if result.applied:
        assert result.emotion_state_id is not None
        assert result.audit_id is not None
        state = await evaluation_seeded_database.emotion.get_state(
            simulation_id=simulation_id,
            character_id="character_arthur_moore",
        )
        assert state is not None
        assert all(
            -1 <= value <= 1
            for value in (
                state.baseline.valence,
                state.baseline.arousal,
                state.baseline.dominance,
                state.immediate.valence,
                state.immediate.arousal,
                state.immediate.dominance,
            )
        )
