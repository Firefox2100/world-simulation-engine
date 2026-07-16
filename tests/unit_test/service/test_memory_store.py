from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience
from world_simulation_engine.model import MemoryAtom
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore


class FakeNeo4jDateTime:
    def __init__(self, value: datetime):
        self.value = value

    def to_native(self):
        return self.value


class FakeRecord(dict):
    pass


def test_memory_from_node_converts_neo4j_sequences_to_plain_lists():
    memory = MemoryStore.memory_from_node(
        {
            "id": "memory_1",
            "summary": "Alex found a sealed door.",
            "keywords": ("door", "sealed"),
            "embedding": (0.1, 0.2),
        }
    )

    assert memory.keywords == ["door", "sealed"]
    assert memory.embedding == [0.1, 0.2]


def test_recall_record_from_record_converts_nodes_and_native_datetime():
    ended_at = datetime(2026, 1, 1, 12, 0, 0)
    record = FakeRecord(
        memory={
            "id": "memory_1",
            "summary": "Alex found a sealed door.",
            "keywords": ["door", "sealed"],
            "embedding": [0.1, 0.2],
        },
        event={
            "id": "event_1",
            "name": "Door discovery",
            "summary": "Alex discovered a sealed door.",
        },
        event_ending_time=FakeNeo4jDateTime(ended_at),
        support_type=MemorySupportType.DIRECT,
        confidence=0.9,
        salience=Salience.CRITICAL,
        behavioural_relevance="Remember the door is sealed.",
        stance=MemoryStance.REMEMBER,
    )

    recall_record = MemoryStore.recall_record_from_record(record)

    assert recall_record.memory.id == "memory_1"
    assert recall_record.event.id == "event_1"
    assert recall_record.event_ending_time == ended_at
    assert recall_record.support_type == MemorySupportType.DIRECT
    assert recall_record.confidence == 0.9
    assert recall_record.salience == Salience.CRITICAL
    assert recall_record.behavioural_relevance == "Remember the door is sealed."


async def test_create_memory_atom_embeds_keywords_when_embedding_missing():
    driver = SimpleNamespace(
        execute_query=AsyncMock(return_value=SimpleNamespace(records=[{"memory": {}}]))
    )
    embed_service = SimpleNamespace(embed_keywords=AsyncMock(return_value=[0.3, 0.4]))
    store = MemoryStore(driver, embed_service=embed_service)

    await store.create_memory_atom(
        memory=MemoryAtom(
            id="memory_1",
            summary="Alex found a sealed door.",
            keywords=["door", "sealed"],
            embedding=None,
        ),
        event_id="event_1",
        support_type=MemorySupportType.DIRECT,
        character_links=[
            CharacterMemoryLink(
                character_id="character_1",
                confidence=0.9,
                salience=Salience.CRITICAL,
                stance=MemoryStance.REMEMBER,
            )
        ],
    )

    embed_service.embed_keywords.assert_awaited_once_with(["door", "sealed"])
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["embedding"] == [0.3, 0.4]


async def test_create_memory_atom_preserves_existing_embedding():
    driver = SimpleNamespace(
        execute_query=AsyncMock(return_value=SimpleNamespace(records=[{"memory": {}}]))
    )
    embed_service = SimpleNamespace(embed_keywords=AsyncMock())
    store = MemoryStore(driver, embed_service=embed_service)

    await store.create_memory_atom(
        memory=MemoryAtom(
            id="memory_1",
            summary="Alex found a sealed door.",
            keywords=["door", "sealed"],
            embedding=[0.1, 0.2],
        ),
        event_id="event_1",
        support_type=MemorySupportType.DIRECT,
        character_links=[
            CharacterMemoryLink(
                character_id="character_1",
                confidence=0.9,
                salience=Salience.CRITICAL,
                stance=MemoryStance.REMEMBER,
            )
        ],
    )

    embed_service.embed_keywords.assert_not_awaited()
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["embedding"] == [0.1, 0.2]
