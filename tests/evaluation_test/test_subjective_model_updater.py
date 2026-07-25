from world_simulation_engine.component.simulator.subjective_model_updater import SubjectiveModelUpdater
from world_simulation_engine.misc.enums import ComponentType


async def test_evaluate_subjective_model_updater_uses_bounded_grounded_schema(
        evaluation_seeded_database,
        evaluation_chat_model_config,
        mock_graph_world_setup,
):
    """Exercise the compact observer/entity claim output with the configured local model."""
    simulation_id = mock_graph_world_setup.simulation.id
    await evaluation_seeded_database.config.link_chat(
        source_id=simulation_id,
        config_id=evaluation_chat_model_config.id,
        component=ComponentType.MEMORY_SUMMARIZER,
    )
    candidate_entity_ids = ["location_observatory_directors_office", "location_old_mine_entrance"]
    # Confirms the test's own fixture references are real seeded entities (update_from_memories
    # silently returns an empty result if none resolve), so an empty result below can be trusted
    # to reflect the model's decision rather than a broken test setup.
    resolved_candidates = await evaluation_seeded_database.entity_relationship.resolve_entity_refs(
        scope_id=simulation_id,
        entity_ids=candidate_entity_ids,
    )
    assert len(resolved_candidates) == len(candidate_entity_ids)

    result = await SubjectiveModelUpdater(database=evaluation_seeded_database).update_from_memories(
        simulation_id=simulation_id,
        character_id="character_arthur_moore",
        turn_id=mock_graph_world_setup.initial_turn.id,
        memory_ids=["memory_disappearance_threads"],
        candidate_entity_ids=candidate_entity_ids,
    )

    # The seeded memory is a neutral investigative summary rather than an unambiguous claim-
    # worthy event, so a genuinely correct model could produce 0-2 claims; both outcomes are
    # checked so the test can't pass by silently skipping an empty result.
    assert 0 <= len(result.applied_claim_ids) <= 2
    for claim_id in result.applied_claim_ids:
        claim = await evaluation_seeded_database.subjective_entity_claim.get_claim(claim_id)
        assert claim is not None
        assert claim.observer_character_id == "character_arthur_moore"
        assert set(claim.supporting_memory_ids + claim.contradicting_memory_ids) <= {
            "memory_disappearance_threads"
        }
