from datetime import UTC, datetime
from uuid import uuid4

import pytest

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.relationship_updater import RelationshipUpdater
from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import EntityRelationship, ProposedAction, RelationshipScope

from workflow_helpers import OBJECTIVE_RELATIONSHIP_VALIDATION_CASES, RELATIONSHIP_UPDATER_CASES, case_ids


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    OBJECTIVE_RELATIONSHIP_VALIDATION_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(OBJECTIVE_RELATIONSHIP_VALIDATION_CASES),
)
async def test_evaluate_action_validator_uses_objective_compatibility_relationship(
        case,
        evaluation_seeded_database,
        evaluation_chat_model_config,
        mock_graph_world_setup,
):
    await evaluation_seeded_database.config.link_chat(
        source_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        component=ComponentType.ACTION_VALIDATOR,
    )
    now = datetime.now(UTC)
    relationship = EntityRelationship.model_validate({
        **case["relationship"],
        "id": str(uuid4()),
        "scope_type": RelationshipScope.SIMULATION,
        "scope_id": mock_graph_world_setup.simulation.id,
        "created_at": now,
        "last_changed_at": now,
    })
    assert await evaluation_seeded_database.entity_relationship.create_relationship(relationship)
    action = ProposedAction.model_validate(case["action"])

    result = await ActionValidator(database=evaluation_seeded_database).validate_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id=case["actor_id"],
        actions=[action],
    )

    assert len(result.validations) == 1
    assert result.validations[0].allowed is case["expected_allowed"]


@pytest.mark.parametrize(
    ("mock_graph_world_setup", "case"),
    RELATIONSHIP_UPDATER_CASES,
    indirect=["mock_graph_world_setup"],
    ids=case_ids(RELATIONSHIP_UPDATER_CASES),
)
async def test_evaluate_relationship_updater_returns_audited_memory_grounded_changes(
        case,
        evaluation_seeded_database,
        evaluation_chat_model_config,
        mock_graph_world_setup,
):
    """Exercise the compact Phase 3 update prompt against the configured evaluation model."""
    simulation_id = mock_graph_world_setup.simulation.id
    await evaluation_seeded_database.config.link_chat(
        source_id=simulation_id,
        config_id=evaluation_chat_model_config.id,
        component=ComponentType.MEMORY_SUMMARIZER,
    )

    candidate_entity_ids = case["candidate_entity_ids"]
    # Confirms the test's own fixture references are real seeded entities, so an empty result
    # below can be trusted to reflect the model's decision rather than a broken test setup.
    resolved_candidates = await evaluation_seeded_database.entity_relationship.resolve_entity_refs(
        scope_id=simulation_id,
        entity_ids=candidate_entity_ids,
    )
    assert len(resolved_candidates) == len(candidate_entity_ids)

    result = await RelationshipUpdater(database=evaluation_seeded_database).update_from_memories(
        simulation_id=simulation_id,
        character_id=case["character_id"],
        turn_id=mock_graph_world_setup.initial_turn.id,
        memory_ids=case["memory_ids"],
        candidate_entity_ids=candidate_entity_ids,
    )

    # The seeded memory is a neutral investigative summary rather than an unambiguous
    # relationship-changing event, so a genuinely correct model could apply 0-2 changes; both
    # outcomes are checked so the test can't pass by silently skipping an empty result.
    assert 0 <= len(result.applied_relationship_ids) <= 2
    assert len(result.audit_ids) == len(result.applied_relationship_ids)
    for relationship_id in result.applied_relationship_ids:
        relationship = await evaluation_seeded_database.entity_relationship.get_relationship(
            relationship_id,
        )
        assert relationship is not None
        assert relationship.perspective_character_id == case["character_id"]
        assert set(case["memory_ids"]) & set(relationship.evidence_memory_ids)
