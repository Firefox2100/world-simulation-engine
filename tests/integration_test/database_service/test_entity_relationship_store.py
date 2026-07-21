import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, TurnType
from world_simulation_engine.model import (
    EntityRelationship,
    Event,
    InterpersonalRelationshipDetails,
    MemoryAtom,
    RelationshipChangeAudit,
    RelationshipEntityRef,
    RelationshipScope,
    RelationshipVisibility,
    Simulation,
    Turn,
)
from world_simulation_engine.service.database.entity_relationship_store import EntityRelationshipStore
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_relationship_crud_scoped_recall_and_memory_evidence(clean_neo4j):
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    simulation = Simulation(
        id=str(uuid4()),
        name="Relationship Simulation",
        description="Relationship persistence test",
        current_time=now,
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    alex = await create_character(clean_neo4j, simulation.id, name="Alex")
    blair = await create_character(clean_neo4j, simulation.id, name="Blair")
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Blair keeps a promise.",
        start_time=now,
    )
    event = Event(id=str(uuid4()), name="Promise kept", summary="Blair kept a promise to Alex.")
    memory = MemoryAtom(
        id=str(uuid4()),
        summary="Blair kept a promise.",
        keywords=["Blair", "promise", "trust"],
        embedding=None,
    )
    await TurnStore(clean_neo4j).create_turn(turn, source_id=simulation.id)
    await EventStore(clean_neo4j).create_event(event, turn_ids=[turn.id])
    await MemoryStore(clean_neo4j).create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.DIRECT,
        character_links=[CharacterMemoryLink(
            character_id=alex.id,
            confidence=0.9,
            salience=Salience.HIGH,
            behavioural_relevance="Alex may trust Blair more.",
            stance=MemoryStance.REMEMBER,
        )],
    )
    relationship = EntityRelationship(
        scope_type=RelationshipScope.SIMULATION,
        scope_id=simulation.id,
        source=RelationshipEntityRef(type="character", id=alex.id, name=alex.name),
        target=RelationshipEntityRef(type="character", id=blair.id, name=blair.name),
        label="trusts",
        private_description="Alex now considers Blair dependable.",
        visibility=RelationshipVisibility.PRIVATE,
        perspective_character_id=alex.id,
        confidence=0.9,
        details=InterpersonalRelationshipDetails(
            category="friend",
            familiarity=0.7,
            trust=0.5,
            affinity=0.3,
        ),
        evidence_memory_ids=[memory.id],
        created_at=now,
        last_changed_at=now,
    )
    store = EntityRelationshipStore(clean_neo4j)

    assert await store.create_relationship(relationship) == relationship
    assert await store.get_relationship(relationship.id) == relationship
    assert await store.list_relationships(
        scope_id=simulation.id,
        perspective_character_id=alex.id,
        entity_ids=[blair.id],
    ) == [relationship]
    assert await store.list_relationships(
        scope_id=simulation.id,
        perspective_character_id=blair.id,
        entity_ids=[alex.id],
    ) == []

    updated = relationship.model_copy(update={
        "details": relationship.details.model_copy(update={"trust": 0.7}),
        "last_changed_at": now + timedelta(minutes=1),
        "version": 2,
    })
    assert await store.update_relationship(updated) == updated

    stale_update = relationship.model_copy(update={
        "details": relationship.details.model_copy(update={"trust": -0.2}),
        "last_changed_at": now + timedelta(minutes=2),
        "version": 2,
    })
    assert await store.update_relationship(stale_update) is None
    assert await store.get_relationship(relationship.id) == updated

    audit = RelationshipChangeAudit(
        relationship_id=relationship.id,
        scope_id=simulation.id,
        perspective_character_id=alex.id,
        turn_id=turn.id,
        evidence_memory_ids=[memory.id],
        changed_at=updated.last_changed_at,
        change_type="update",
        previous_version=relationship.version,
        new_version=updated.version,
        previous_state=relationship.model_dump(mode="json"),
        new_state=updated.model_dump(mode="json"),
    )
    assert await store.create_change_audit(audit) == audit
    assert await store.list_change_audits(relationship.id) == [audit]

    resolved = await store.resolve_entity_refs(
        scope_id=simulation.id,
        entity_ids=[alex.id, blair.id, "missing"],
    )
    assert {entity.id for entity in resolved} == {alex.id, blair.id}

    evidence_result = await clean_neo4j.execute_query(
        """
        MATCH (:MemoryAtom {id: $memory_id})-[:EVIDENCE_FOR]->
            (:EntityRelationship {id: $relationship_id})
        RETURN count(*) AS evidence_count
        """,
        parameters_={
            "memory_id": memory.id,
            "relationship_id": relationship.id,
        },
    )
    assert evidence_result.records[0]["evidence_count"] == 1
    assert await store.delete_relationship(relationship.id) is True
    assert await store.get_relationship(relationship.id) is None


async def test_relationship_creation_rejects_missing_evidence(clean_neo4j):
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    source = await create_character(clean_neo4j, world.id, name="Alex")
    target = await create_character(clean_neo4j, world.id, name="Blair")
    relationship = EntityRelationship(
        scope_type=RelationshipScope.WORLD,
        scope_id=world.id,
        source=RelationshipEntityRef(type="character", id=source.id),
        target=RelationshipEntityRef(type="character", id=target.id),
        label="knows",
        details=InterpersonalRelationshipDetails(),
        evidence_memory_ids=["missing_memory"],
        created_at=now,
        last_changed_at=now,
    )

    assert await EntityRelationshipStore(clean_neo4j).create_relationship(relationship) is None


async def test_relationship_update_uses_version_compare_and_set(clean_neo4j):
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    simulation = Simulation(
        id=str(uuid4()),
        name="Concurrent relationship simulation",
        current_time=now,
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    source = await create_character(clean_neo4j, simulation.id, name="Alex")
    target = await create_character(clean_neo4j, simulation.id, name="Blair")
    relationship = EntityRelationship(
        scope_type=RelationshipScope.SIMULATION,
        scope_id=simulation.id,
        source=RelationshipEntityRef(type="character", id=source.id),
        target=RelationshipEntityRef(type="character", id=target.id),
        label="trusts",
        details=InterpersonalRelationshipDetails(trust=0),
        created_at=now,
        last_changed_at=now,
    )
    store = EntityRelationshipStore(clean_neo4j)
    assert await store.create_relationship(relationship)
    positive = relationship.model_copy(update={
        "details": relationship.details.model_copy(update={"trust": 0.2}),
        "last_changed_at": now + timedelta(seconds=1),
        "version": 2,
    })
    negative = relationship.model_copy(update={
        "details": relationship.details.model_copy(update={"trust": -0.2}),
        "last_changed_at": now + timedelta(seconds=1),
        "version": 2,
    })

    results = await asyncio.gather(
        store.update_relationship(positive),
        store.update_relationship(negative),
    )

    assert sum(result is not None for result in results) == 1
    persisted = await store.get_relationship(relationship.id)
    assert persisted is not None
    assert persisted.version == 2
    assert persisted.details.trust in {0.2, -0.2}


async def test_world_relationships_copy_to_simulation_with_remapped_entities(clean_neo4j):
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    source = await create_character(clean_neo4j, world.id, name="Alex")
    target = await create_character(clean_neo4j, world.id, name="Blair")
    store = EntityRelationshipStore(clean_neo4j)
    template = EntityRelationship(
        scope_type=RelationshipScope.WORLD,
        scope_id=world.id,
        source=RelationshipEntityRef(type="character", id=source.id),
        target=RelationshipEntityRef(type="character", id=target.id),
        label="rivals",
        details=InterpersonalRelationshipDetails(category="rival", tension=0.6),
        created_at=now,
        last_changed_at=now,
    )
    await store.create_relationship(template)
    simulation = Simulation(
        id=str(uuid4()),
        name="Copied relationship simulation",
        description="Copy test",
        current_time=now,
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    _, character_pairs = await CharacterStore(clean_neo4j).copy_characters(
        world.id,
        simulation.id,
        return_pairs=True,
    )

    copied = await store.copy_relationships(
        source_id=world.id,
        target_simulation_id=simulation.id,
        entity_pairs=character_pairs,
        copied_at=now,
    )

    id_map = {pair["source_id"]: pair["copy_id"] for pair in character_pairs}
    assert len(copied) == 1
    assert copied[0].scope_type == RelationshipScope.SIMULATION
    assert copied[0].scope_id == simulation.id
    assert copied[0].source.id == id_map[source.id]
    assert copied[0].target.id == id_map[target.id]
    assert copied[0].id != template.id
