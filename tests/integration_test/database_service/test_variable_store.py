import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, TurnType
from world_simulation_engine.model import (
    EntityVariableSet,
    Event,
    MemoryAtom,
    Simulation,
    Turn,
    VariableChangeAudit,
    VariableDefinition,
)
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from world_simulation_engine.service.database.variable_store import VariableStore
from integration_test.database_service.helpers import create_character, create_world


def make_health_variable(value: int = 100) -> VariableDefinition:
    return VariableDefinition(
        name="health",
        value_type="integer",
        value=value,
        default_value=100,
        description="Hit points; decreases when the character takes damage.",
        minimum=0,
        maximum=100,
    )


async def test_variable_set_create_get_update_and_audit(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    turn = Turn(id=str(uuid4()), sequence=1, type=TurnType.USER_INPUT, content="A fight breaks out.", start_time=now)
    event = Event(id=str(uuid4()), name="Fight", summary="Alex was struck.")
    memory = MemoryAtom(id=str(uuid4()), summary="Alex took a hit.", keywords=["fight"], embedding=None)

    await TurnStore(clean_neo4j).create_turn(turn, source_id=world.id)
    await EventStore(clean_neo4j).create_event(event, turn_ids=[turn.id])
    await MemoryStore(clean_neo4j).create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.DIRECT,
        character_links=[CharacterMemoryLink(
            character_id=character.id,
            confidence=1,
            salience=Salience.HIGH,
            stance=MemoryStance.REMEMBER,
        )],
    )

    store = VariableStore(clean_neo4j)
    variable_set = EntityVariableSet(
        source_id=world.id,
        owner_type="character",
        owner_id=character.id,
        variables=[make_health_variable()],
        last_updated_at=now,
    )

    assert await store.get_variable_set(character.id) is None
    assert await store.create_variable_set(variable_set) == variable_set
    assert await store.get_variable_set(character.id) == variable_set
    assert await store.list_variable_sets_by_source(world.id) == [variable_set]

    # A second variable set for the same owner must be rejected (one node per entity).
    duplicate = variable_set.model_copy(update={"id": str(uuid4())})
    assert await store.create_variable_set(duplicate) is None

    assert await store.owner_belongs_to_source(source_id=world.id, owner_id=character.id) is True
    assert await store.owner_belongs_to_source(source_id=world.id, owner_id="not_an_owner") is False

    updated = variable_set.model_copy(update={
        "variables": [make_health_variable(value=60)],
        "last_updated_at": now + timedelta(seconds=1),
        "version": 2,
    })
    assert await store.update_variable_set(updated) == updated
    persisted = await store.get_variable_set(character.id)
    assert persisted.variables[0].value == 60

    audit = VariableChangeAudit(
        variable_set_id=persisted.id,
        source_id=world.id,
        owner_id=character.id,
        turn_id=turn.id,
        evidence_memory_ids=[memory.id],
        changed_at=now + timedelta(seconds=1),
        change_type="update",
        previous_version=1,
        new_version=2,
        previous_state=variable_set.model_dump(mode="json"),
        new_state=persisted.model_dump(mode="json"),
    )
    assert await store.create_change_audit(audit) == audit
    assert await store.list_change_audits(persisted.id) == [audit]


async def test_variable_set_update_guards_against_concurrent_writes(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    store = VariableStore(clean_neo4j)
    variable_set = EntityVariableSet(
        source_id=world.id,
        owner_type="character",
        owner_id=character.id,
        variables=[make_health_variable()],
        last_updated_at=now,
    )
    await store.create_variable_set(variable_set)

    raised = variable_set.model_copy(update={
        "variables": [make_health_variable(value=90)],
        "version": 2,
    })
    lowered = variable_set.model_copy(update={
        "variables": [make_health_variable(value=70)],
        "version": 2,
    })
    results = await asyncio.gather(
        store.update_variable_set(raised),
        store.update_variable_set(lowered),
    )

    assert sum(result is not None for result in results) == 1
    persisted = await store.get_variable_set(character.id)
    assert persisted.version == 2
    assert persisted.variables[0].value in {90, 70}


async def test_variable_sets_are_sparse_by_default(clean_neo4j):
    """Most owners have no EntityVariableSet at all - this must not error, just return None/[]."""
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="No Variables")
    store = VariableStore(clean_neo4j)

    assert await store.get_variable_set(character.id) is None
    assert await store.list_variable_sets_by_source(world.id) == []
