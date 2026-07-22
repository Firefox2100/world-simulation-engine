import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, TurnType
from world_simulation_engine.model import (
    EmotionChangeAudit,
    EmotionState,
    EmotionVector,
    Event,
    MemoryAtom,
    Simulation,
    Turn,
)
from world_simulation_engine.service.database.emotion_store import EmotionStore
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_emotion_state_crud_decay_audit_and_concurrent_version_guard(clean_neo4j):
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    simulation = Simulation(id=str(uuid4()), name="Emotion simulation", current_time=now)
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    character = await create_character(clean_neo4j, simulation.id, name="Alex")
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="A threat is made.",
        start_time=now,
    )
    event = Event(id=str(uuid4()), name="Threat", summary="Alex was threatened.")
    memory = MemoryAtom(
        id=str(uuid4()),
        summary="Alex was threatened.",
        keywords=["threat"],
        embedding=None,
    )
    await TurnStore(clean_neo4j).create_turn(turn, source_id=simulation.id)
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
    store = EmotionStore(clean_neo4j)
    state = EmotionState(
        simulation_id=simulation.id,
        character_id=character.id,
        immediate=EmotionVector(valence=-0.3, arousal=0.4),
        last_updated_at=now,
    )

    assert await store.validate_memory_evidence(
        simulation_id=simulation.id,
        character_id=character.id,
        memory_ids=[memory.id],
    ) is True
    assert await store.validate_memory_evidence(
        simulation_id=simulation.id,
        character_id=character.id,
        memory_ids=["missing_memory"],
    ) is False
    assert await store.create_state(state) == state
    assert await store.get_state(
        simulation_id=simulation.id,
        character_id=character.id,
    ) == state
    audit = EmotionChangeAudit(
        emotion_state_id=state.id,
        simulation_id=simulation.id,
        character_id=character.id,
        turn_id=turn.id,
        evidence_memory_ids=[memory.id],
        changed_at=now,
        change_type="create",
        new_version=1,
        new_state=state.model_dump(mode="json"),
    )
    assert await store.create_change_audit(audit) == audit
    assert await store.list_change_audits(state.id) == [audit]
    provenance = await clean_neo4j.execute_query(
        """
        MATCH (:Event {id: $event_id})-[:CAUSED_EMOTION_CHANGE]->
            (:EmotionChangeAudit {id: $audit_id})
        RETURN count(*) AS count
        """,
        parameters_={"event_id": event.id, "audit_id": audit.id},
    )
    assert provenance.records[0]["count"] == 1

    positive = state.model_copy(update={
        "immediate": EmotionVector(arousal=0.6),
        "last_updated_at": now + timedelta(seconds=1),
        "version": 2,
    })
    negative = state.model_copy(update={
        "immediate": EmotionVector(arousal=-0.2),
        "last_updated_at": now + timedelta(seconds=1),
        "version": 2,
    })
    results = await asyncio.gather(
        store.update_state(positive),
        store.update_state(negative),
    )

    assert sum(result is not None for result in results) == 1
    persisted = await store.get_state(
        simulation_id=simulation.id,
        character_id=character.id,
    )
    assert persisted is not None
    assert persisted.version == 2
    assert persisted.immediate.arousal in {0.6, -0.2}
