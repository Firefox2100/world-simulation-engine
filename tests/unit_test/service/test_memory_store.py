from datetime import datetime

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience
from world_simulation_engine.service.database.memory_store import MemoryStore


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
