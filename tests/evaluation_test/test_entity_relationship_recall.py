from datetime import UTC, datetime

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.component.simulator.relationship_updater import RelationshipUpdater
from world_simulation_engine.misc.enums import ActionType, ComponentType
from world_simulation_engine.model import (
    CompatibilityRelationshipDetails,
    EntityRelationship,
    ProposedAction,
    RelationshipEntityRef,
    RelationshipScope,
    RelationshipVisibility,
)


async def test_evaluate_action_validator_uses_objective_compatibility_relationship(
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
    relationship = EntityRelationship(
        scope_type=RelationshipScope.SIMULATION,
        scope_id=mock_graph_world_setup.simulation.id,
        source=RelationshipEntityRef(
            type="equipment",
            id="equipment_pocket_revolver",
            name="Pocket Revolver",
        ),
        target=RelationshipEntityRef(
            type="item",
            id="item_anonymous_letter",
            name="Anonymous Letter",
        ),
        label="not compatible with",
        public_description="The revolver cannot safely be used as a letter opener.",
        visibility=RelationshipVisibility.OBJECTIVE,
        details=CompatibilityRelationshipDetails(
            compatible=False,
            conditions=["Using the revolver this way risks discharge and cannot open the letter safely."],
        ),
        created_at=now,
        last_changed_at=now,
    )
    assert await evaluation_seeded_database.entity_relationship.create_relationship(relationship)
    action = ProposedAction(
        type=ActionType.USE,
        label="use_revolver_to_open_letter",
        target_ids=["equipment_pocket_revolver", "item_anonymous_letter"],
        intended_duration_seconds=5,
        interruptible=True,
        required_preconditions=["The revolver is compatible with safely opening the letter."],
    )

    result = await ActionValidator(database=evaluation_seeded_database).validate_actions(
        world_id=mock_graph_world_setup.world.id,
        simulation_id=mock_graph_world_setup.simulation.id,
        character_id="character_arthur_moore",
        actions=[action],
    )

    assert len(result.validations) == 1
    assert result.validations[0].allowed is False


async def test_evaluate_relationship_updater_returns_audited_memory_grounded_changes(
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

    result = await RelationshipUpdater(database=evaluation_seeded_database).update_from_memories(
        simulation_id=simulation_id,
        character_id="character_arthur_moore",
        turn_id=mock_graph_world_setup.initial_turn.id,
        memory_ids=["memory_disappearance_threads"],
        candidate_entity_ids=[
            "character_clara_whitlock",
            "location_old_mine_entrance",
        ],
    )

    assert len(result.applied_relationship_ids) <= 2
    assert len(result.audit_ids) == len(result.applied_relationship_ids)
    for relationship_id in result.applied_relationship_ids:
        relationship = await evaluation_seeded_database.entity_relationship.get_relationship(
            relationship_id,
        )
        assert relationship is not None
        assert relationship.perspective_character_id == "character_arthur_moore"
        assert "memory_disappearance_threads" in relationship.evidence_memory_ids
