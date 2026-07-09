import os
from datetime import UTC, datetime
from uuid import uuid4

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.character_simulator import CharacterSimulator
from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, TurnType
from world_simulation_engine.model import Event, MemoryAtom, Simulation, Turn
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


class FakeEmbedService:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


async def create_simulation(clean_neo4j, world_id: str, current_time: datetime) -> Simulation:
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=current_time,
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world_id)
    return simulation


async def create_turn(clean_neo4j,
                      source_id: str,
                      sequence: int,
                      start_time: datetime,
                      ) -> Turn:
    turn = Turn(
        id=str(uuid4()),
        sequence=sequence,
        type=TurnType.USER_INPUT,
        content=f"Turn {sequence}",
        start_time=start_time,
    )
    await TurnStore(clean_neo4j).create_turn(turn, source_id=source_id)
    return turn


async def create_memory(clean_neo4j,
                        character_id: str,
                        turn: Turn,
                        summary: str,
                        embedding: list[float],
                        confidence: float,
                        ) -> MemoryAtom:
    event = Event(
        id=str(uuid4()),
        name=f"Event for {summary}",
        summary=summary,
    )
    memory = MemoryAtom(
        id=str(uuid4()),
        summary=summary,
        keywords=summary.lower().split(),
        embedding=embedding,
    )

    await EventStore(clean_neo4j).create_event(event, turn_ids=[turn.id])
    await MemoryStore(clean_neo4j).create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.DIRECT,
        character_links=[
            CharacterMemoryLink(
                character_id=character_id,
                confidence=confidence,
                salience=Salience.MEDIUM,
                behavioural_relevance=f"Remember {summary}",
                stance=MemoryStance.REMEMBER,
            )
        ],
    )

    return memory


async def test_recall_memory_includes_recent_turn_event_memories(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await create_simulation(
        clean_neo4j,
        world.id,
        current_time=datetime(2026, 1, 10, 12, 0, tzinfo=UTC),
    )
    character = await create_character(clean_neo4j, world.id, name="Alex")
    turn = await create_turn(
        clean_neo4j,
        simulation.id,
        sequence=1,
        start_time=datetime(2026, 1, 10, 11, 0, tzinfo=UTC),
    )
    memory = await create_memory(
        clean_neo4j,
        character.id,
        turn,
        summary="Alex saw a lantern",
        embedding=[0.0, 1.0],
        confidence=0.8,
    )
    simulator = CharacterSimulator(DatabaseService(clean_neo4j), langfuse_handler=None)

    recalled = await simulator._recall_memory(
        simulation=simulation,
        character=character,
        user_input="",
    )

    assert [entry.memory.id for entry in recalled] == [memory.id]
    assert recalled[0].recall_sources == ["recent_event"]
    assert recalled[0].decayed_confidence > 0.79


async def test_recall_memory_embedding_match_deduplicates_recent_memory(clean_neo4j, monkeypatch):
    world = await create_world(clean_neo4j)
    simulation = await create_simulation(
        clean_neo4j,
        world.id,
        current_time=datetime(2026, 1, 10, 12, 0, tzinfo=UTC),
    )
    character = await create_character(clean_neo4j, world.id, name="Alex")
    old_turn = await create_turn(
        clean_neo4j,
        simulation.id,
        sequence=1,
        start_time=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
    )
    for sequence in range(2, 7):
        await create_turn(
            clean_neo4j,
            simulation.id,
            sequence=sequence,
            start_time=datetime(2026, 1, sequence, 11, 0, tzinfo=UTC),
        )
    recent_turn = await create_turn(
        clean_neo4j,
        simulation.id,
        sequence=7,
        start_time=datetime(2026, 1, 10, 11, 0, tzinfo=UTC),
    )
    recent_memory = await create_memory(
        clean_neo4j,
        character.id,
        recent_turn,
        summary="Alex saw a lantern",
        embedding=[1.0, 0.0],
        confidence=0.8,
    )
    old_memory = await create_memory(
        clean_neo4j,
        character.id,
        old_turn,
        summary="Alex heard bells",
        embedding=[0.9, 0.1],
        confidence=0.9,
    )
    simulator = CharacterSimulator(DatabaseService(clean_neo4j), langfuse_handler=None)

    async def fake_prepare_embed_service(simulation_id: str):
        return FakeEmbedService()

    monkeypatch.setattr(simulator, "_prepare_embed_service", fake_prepare_embed_service)

    recalled = await simulator._recall_memory(
        simulation=simulation,
        character=character,
        user_input="lantern",
    )

    by_id = {
        entry.memory.id: entry
        for entry in recalled
    }
    assert set(by_id) == {recent_memory.id, old_memory.id}
    assert by_id[recent_memory.id].recall_sources == ["recent_event", "embedding_match"]
    assert by_id[recent_memory.id].similarity == 1.0
    assert by_id[old_memory.id].recall_sources == ["embedding_match"]


async def test_recall_memory_filters_old_embedding_matches_below_decay_threshold(clean_neo4j, monkeypatch):
    world = await create_world(clean_neo4j)
    simulation = await create_simulation(
        clean_neo4j,
        world.id,
        current_time=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
    )
    character = await create_character(clean_neo4j, world.id, name="Alex")
    old_turn = await create_turn(
        clean_neo4j,
        simulation.id,
        sequence=1,
        start_time=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
    )
    for sequence in range(2, 7):
        await create_turn(
            clean_neo4j,
            simulation.id,
            sequence=sequence,
            start_time=datetime(2026, 1, sequence, 11, 0, tzinfo=UTC),
        )
    await create_memory(
        clean_neo4j,
        character.id,
        old_turn,
        summary="Alex saw a lantern long ago",
        embedding=[1.0, 0.0],
        confidence=0.3,
    )
    simulator = CharacterSimulator(DatabaseService(clean_neo4j), langfuse_handler=None)

    async def fake_prepare_embed_service(simulation_id: str):
        return FakeEmbedService()

    monkeypatch.setattr(simulator, "_prepare_embed_service", fake_prepare_embed_service)

    recalled = await simulator._recall_memory(
        simulation=simulation,
        character=character,
        user_input="lantern",
    )

    assert recalled == []
