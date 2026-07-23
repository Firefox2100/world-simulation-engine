from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.simulator.relationship_updater import (
    RelationshipUpdateContext,
    RelationshipUpdater,
)
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import (
    Character,
    CurrentActivity,
    EntityRelationship,
    InterpersonalRelationshipDetails,
    MemoryAtom,
    ProposedEntityRelationshipChange,
    RelationshipEntityRef,
    RelationshipScope,
    RelationshipUpdateProposal,
    RelationshipVisibility,
    Simulation,
    World,
)


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_context(existing_relationships=None):
    return RelationshipUpdateContext(
        simulation_id="simulation_1",
        actor_id="character_1",
        actor_name="Alex",
        simulation_time=NOW,
        turn_id="turn_1",
        new_memories=[MemoryAtom(
            id="memory_1",
            summary="Blair kept a promise to Alex.",
            keywords=["promise"],
            embedding=None,
        )],
        candidate_entities=[
            RelationshipEntityRef(type="character", id="character_1", name="Alex"),
            RelationshipEntityRef(type="character", id="character_2", name="Blair"),
        ],
        existing_relationships=existing_relationships or [],
    )


async def test_apply_proposal_creates_bounded_private_relationship_with_audit():
    database = Mock()
    database.entity_relationship.create_relationship = AsyncMock(side_effect=lambda value: value)
    database.entity_relationship.create_change_audit = AsyncMock(side_effect=lambda value: value)
    updater = RelationshipUpdater(database=database)
    proposal = RelationshipUpdateProposal(changes=[ProposedEntityRelationshipChange(
        kind="interpersonal",
        source_id="character_1",
        target_id="character_2",
        label="trusts",
        private_description="Alex considers Blair more dependable.",
        confidence=0.8,
        evidence_memory_ids=["memory_1"],
        trust_delta=0.25,
    )])

    result = await updater._apply_proposal(proposal=proposal, context=make_context())

    created = database.entity_relationship.create_relationship.await_args.args[0]
    assert result.applied_relationship_ids == [created.id]
    assert created.scope_id == "simulation_1"
    assert created.visibility == RelationshipVisibility.PRIVATE
    assert created.perspective_character_id == "character_1"
    assert created.details.trust == 0.15
    audit = database.entity_relationship.create_change_audit.await_args.args[0]
    assert audit.relationship_id == created.id
    assert audit.turn_id == "turn_1"
    assert audit.evidence_memory_ids == ["memory_1"]
    assert audit.change_type == "create"


async def test_apply_proposal_updates_existing_version_and_clamps_change():
    existing = EntityRelationship(
        id="relationship_1",
        scope_type=RelationshipScope.SIMULATION,
        scope_id="simulation_1",
        source=RelationshipEntityRef(type="character", id="character_1"),
        target=RelationshipEntityRef(type="character", id="character_2"),
        label="trusts",
        private_description="Alex is cautiously optimistic.",
        visibility=RelationshipVisibility.PRIVATE,
        perspective_character_id="character_1",
        confidence=0.5,
        details=InterpersonalRelationshipDetails(trust=0.2),
        evidence_memory_ids=["memory_old"],
        created_at=NOW,
        last_changed_at=NOW,
    )
    database = Mock()
    database.entity_relationship.update_relationship = AsyncMock(side_effect=lambda value: value)
    database.entity_relationship.create_change_audit = AsyncMock(side_effect=lambda value: value)
    updater = RelationshipUpdater(database=database)
    proposal = RelationshipUpdateProposal(changes=[ProposedEntityRelationshipChange(
        relationship_id=existing.id,
        kind="interpersonal",
        source_id="character_1",
        target_id="character_2",
        label="trusts",
        private_description="Alex now has stronger evidence of Blair's reliability.",
        confidence=1,
        evidence_memory_ids=["memory_1"],
        trust_delta=0.25,
    )])

    result = await updater._apply_proposal(
        proposal=proposal,
        context=make_context([existing]),
    )

    updated = database.entity_relationship.update_relationship.await_args.args[0]
    assert result.applied_relationship_ids == [existing.id]
    assert updated.version == 2
    assert updated.confidence == 0.7
    assert updated.details.trust == 0.35
    assert updated.evidence_memory_ids == ["memory_old", "memory_1"]
    audit = database.entity_relationship.create_change_audit.await_args.args[0]
    assert audit.previous_version == 1
    assert audit.new_version == 2
    assert audit.change_type == "update"


async def test_apply_proposal_rejects_unknown_evidence_and_endpoint():
    database = Mock()
    database.entity_relationship.create_relationship = AsyncMock()
    database.entity_relationship.create_change_audit = AsyncMock()
    updater = RelationshipUpdater(database=database)
    proposal = RelationshipUpdateProposal(changes=[
        ProposedEntityRelationshipChange(
            kind="generic",
            source_id="character_1",
            target_id="missing_entity",
            label="knows about",
            private_description="Unknown endpoint.",
            confidence=0.5,
            evidence_memory_ids=["memory_1"],
        ),
        ProposedEntityRelationshipChange(
            kind="generic",
            source_id="character_1",
            target_id="character_2",
            label="knows about",
            private_description="Unsupported evidence.",
            confidence=0.5,
            evidence_memory_ids=["memory_not_new"],
        ),
    ])

    result = await updater._apply_proposal(proposal=proposal, context=make_context())

    assert result.applied_relationship_ids == []
    assert result.skipped_changes == 2
    database.entity_relationship.create_relationship.assert_not_awaited()
    database.entity_relationship.create_change_audit.assert_not_awaited()


async def test_apply_proposal_skips_incomplete_specialized_shapes_after_parsing():
    database = Mock()
    database.entity_relationship.create_relationship = AsyncMock()
    updater = RelationshipUpdater(database=database)
    proposal = RelationshipUpdateProposal.model_validate({"changes": [
        {
            "kind": "spatial", "source_id": "character_1", "target_id": "character_2",
            "label": "near", "private_description": "No distance supplied.", "confidence": .5,
            "evidence_memory_ids": ["memory_1"],
        },
        {
            "kind": "compatibility", "source_id": "character_1", "target_id": "character_2",
            "label": "compatible", "private_description": "No compatible value supplied.", "confidence": .5,
            "evidence_memory_ids": ["memory_1"],
        },
    ]})

    result = await updater._apply_proposal(proposal=proposal, context=make_context())

    assert result.skipped_changes == 2
    database.entity_relationship.create_relationship.assert_not_awaited()


async def test_update_from_memories_uses_one_scoped_small_proposal_call():
    simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        current_time=NOW,
    )
    actor = Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="The actor",
        public_state="Present",
        private_state="Thoughtful",
        current_activity=CurrentActivity(name="idle"),
    )
    memory = MemoryAtom(
        id="memory_1",
        summary="Blair kept a promise.",
        keywords=["promise"],
        embedding=None,
    )
    database = Mock()
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_character = AsyncMock(return_value=actor)
    database.memory.get_memory = AsyncMock(return_value=memory)
    database.entity_relationship.resolve_entity_refs = AsyncMock(return_value=[
        RelationshipEntityRef(type="character", id="character_1", name="Alex"),
        RelationshipEntityRef(type="character", id="character_2", name="Blair"),
    ])
    database.entity_relationship.list_relationships = AsyncMock(return_value=[])
    database.world.get_world_by_simulation = AsyncMock(return_value=World(
        id="world_1",
        name="World",
        description="World",
        starting_time=NOW,
        version=1,
        language=SupportedLanguage.ENGLISH,
    ))
    updater = RelationshipUpdater(database=database)
    updater._prepare_prompt = AsyncMock(return_value=[])
    llm = SimpleNamespace(invoke_structured_with_repair=AsyncMock(
        return_value=RelationshipUpdateProposal(changes=[]),
    ))
    updater._prepare_llm_service = AsyncMock(return_value=llm)

    result = await updater.update_from_memories(
        simulation_id="simulation_1",
        character_id="character_1",
        turn_id="turn_1",
        memory_ids=["memory_1"],
        candidate_entity_ids=["character_2"],
    )

    assert result.applied_relationship_ids == []
    llm.invoke_structured_with_repair.assert_awaited_once()
    call = llm.invoke_structured_with_repair.await_args.kwargs
    assert call["output_model"] is RelationshipUpdateProposal
    assert len(call["data"]["new_memories"]) == 1
    assert len(call["data"]["candidate_entities"]) == 2
