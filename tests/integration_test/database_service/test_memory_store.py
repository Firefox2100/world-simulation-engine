from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, TurnType
from world_simulation_engine.model import Event, MemoryAtom, Simulation, Turn
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_create_memory_atom_attaches_to_event_and_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
    memory_store = MemoryStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )
    memory = MemoryAtom(
        id=str(uuid4()),
        summary="Alex greeted someone.",
        keywords=["Alex", "greeting"],
        embedding=[0.1, 0.2, 0.3],
    )

    await turn_store.create_turn(turn, source_id=world.id)
    await event_store.create_event(event, turn_ids=[turn.id])
    assert await memory_store.create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.DIRECT,
        character_links=[
            CharacterMemoryLink(
                character_id=character.id,
                confidence=0.9,
                salience=Salience.MEDIUM,
                behavioural_relevance="May greet this person again.",
                stance=MemoryStance.REMEMBER,
            )
        ],
    ) == memory
    assert await memory_store.get_memory(memory.id) == memory
    assert await memory_store.list_memories() == [memory]
    assert await memory_store.list_memories(character_id=character.id) == [memory]
    assert await memory_store.list_memories(event_id=event.id) == [memory]
    assert await memory_store.update_memory(memory.id, {"summary": "Updated memory"}) == memory.model_copy(
        update={"summary": "Updated memory"}
    )

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Event {id: $event_id})-[support:SUPPORTS]->(memory:MemoryAtom {id: $memory_id})
        MATCH (:Character {id: $character_id})-[remembers:REMEMBERS]->(memory)
        RETURN support.type AS support_type,
               memory.summary AS summary,
               memory.keywords AS keywords,
               memory.embedding AS embedding,
               remembers.confidence AS confidence,
               remembers.salience AS salience,
               remembers.behavioural_relevance AS behavioural_relevance,
               remembers.stance AS stance
        """,
        parameters_={
            "event_id": event.id,
            "memory_id": memory.id,
            "character_id": character.id,
        },
    )

    record = result.records[0]
    assert record["support_type"] == MemorySupportType.DIRECT
    assert record["summary"] == "Updated memory"
    assert record["keywords"] == memory.keywords
    assert record["embedding"] == memory.embedding
    assert record["confidence"] == 0.9
    assert record["salience"] == Salience.MEDIUM
    assert record["behavioural_relevance"] == "May greet this person again."
    assert record["stance"] == MemoryStance.REMEMBER
    assert await memory_store.delete_memory(memory.id) is True


async def test_list_memories_can_filter_by_simulation(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Memory Simulation",
        description="A simulation used to list memories",
        current_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    character = await create_character(clean_neo4j, simulation.id, name="Alex")
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
    memory_store = MemoryStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )
    memory = MemoryAtom(
        id=str(uuid4()),
        summary="Alex greeted someone.",
        keywords=["Alex", "greeting"],
        embedding=[0.1, 0.2, 0.3],
    )

    await turn_store.create_turn(turn, source_id=simulation.id)
    await event_store.create_event(event, turn_ids=[turn.id])
    await memory_store.create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.DIRECT,
        character_links=[
            CharacterMemoryLink(
                character_id=character.id,
                confidence=0.9,
                salience=Salience.MEDIUM,
                stance=MemoryStance.REMEMBER,
            )
        ],
    )

    assert await memory_store.list_memories(simulation_id=simulation.id) == [memory]
    assert await memory_store.get_memory(memory.id) == memory
    assert await memory_store.delete_memory(memory.id) is True


async def test_add_character_memory(clean_neo4j):
    world = await create_world(clean_neo4j)
    first_character = await create_character(clean_neo4j, world.id, name="Alex")
    second_character = await create_character(clean_neo4j, world.id, name="Blair")
    turn_store = TurnStore(clean_neo4j)
    event_store = EventStore(clean_neo4j)
    memory_store = MemoryStore(clean_neo4j)
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.USER_INPUT,
        content="Hello",
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="A greeting exchange",
    )
    memory = MemoryAtom(
        id=str(uuid4()),
        summary="Alex greeted someone.",
        keywords=["Alex", "greeting"],
        embedding=[0.1, 0.2, 0.3],
    )

    await turn_store.create_turn(turn, source_id=world.id)
    await event_store.create_event(event, turn_ids=[turn.id])
    await memory_store.create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.REPORTED,
        character_links=[
            CharacterMemoryLink(
                character_id=first_character.id,
                confidence=0.9,
                salience=Salience.MEDIUM,
                behavioural_relevance=None,
                stance=MemoryStance.REMEMBER,
            )
        ],
    )
    await memory_store.add_character_memory(
        memory.id,
        CharacterMemoryLink(
            character_id=second_character.id,
            confidence=0.4,
            salience=Salience.LOW,
            behavioural_relevance="May be uncertain about the greeting.",
            stance=MemoryStance.DOUBT,
        ),
    )

    result = await clean_neo4j.execute_query(
        """
        MATCH (character:Character)-[remembers:REMEMBERS]->(:MemoryAtom {id: $memory_id})
        RETURN character.id AS character_id,
               remembers.confidence AS confidence,
               remembers.salience AS salience,
               remembers.behavioural_relevance AS behavioural_relevance,
               remembers.stance AS stance
        ORDER BY character.name
        """,
        parameters_={"memory_id": memory.id},
    )

    assert [
        (
            record["character_id"],
            record["confidence"],
            record["salience"],
            record["behavioural_relevance"],
            record["stance"],
        )
        for record in result.records
    ] == [
        (first_character.id, 0.9, Salience.MEDIUM, None, MemoryStance.REMEMBER),
        (
            second_character.id,
            0.4,
            Salience.LOW,
            "May be uncertain about the greeting.",
            MemoryStance.DOUBT,
        ),
    ]
    assert await memory_store.replace_character_memories(
        memory.id,
        [
            CharacterMemoryLink(
                character_id=second_character.id,
                confidence=0.5,
                salience=Salience.HIGH,
                behavioural_relevance=None,
                stance=MemoryStance.BELIEVE,
            )
        ],
    ) == memory
    assert await memory_store.list_memories(character_id=first_character.id) == []
    assert await memory_store.list_memories(character_id=second_character.id) == [memory]
    assert await memory_store.remove_character_memories(memory.id, [second_character.id]) is False
    assert await memory_store.link_memory_event(memory.id, event.id, MemorySupportType.DIRECT) == memory
