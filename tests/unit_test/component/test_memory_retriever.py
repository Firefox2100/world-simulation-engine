from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.simulator.memory_retriever import MemoryRetriever
from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience
from world_simulation_engine.model import Event, MemoryAtom
from world_simulation_engine.service.database.memory_store import MemoryRecallRecord


NOW = datetime(2026, 1, 10, tzinfo=UTC)


def record(memory_id: str, *, days_old=0, embedding=None, channels=None, summary=None):
    return MemoryRecallRecord(
        memory=MemoryAtom(
            id=memory_id,
            summary=summary or memory_id,
            keywords=[memory_id],
            embedding=embedding,
        ),
        event=Event(id=f"event_{memory_id}", name=memory_id, summary=summary or memory_id),
        event_ending_time=NOW - timedelta(days=days_old),
        support_type=MemorySupportType.DIRECT,
        confidence=.8,
        salience=Salience.MEDIUM,
        stance=MemoryStance.REMEMBER,
        recall_channels=channels or [],
    )


def database(*, recent=None, graph=None, semantic=None):
    db = Mock()
    db.memory.get_recent_turn_memory_candidates = AsyncMock(return_value=recent or [])
    db.memory.get_graph_memory_candidates = AsyncMock(return_value=graph or [])
    db.memory.get_scoped_character_memory_candidates = AsyncMock(return_value=semantic or [])
    db.memory.update_embeddings = AsyncMock(return_value=len(semantic or []))
    return db


class FakeEmbedService:
    async def embed_texts(self, texts):
        return [[1, 0] for _ in texts]


async def test_direct_recent_evidence_ranks_above_perfect_semantic_coincidence():
    recent = record("recent", embedding=[0, 1])
    semantic = record("semantic", embedding=[1, 0])
    retriever = MemoryRetriever(database(recent=[recent], semantic=[semantic]))

    result = await retriever.retrieve(
        simulation_id="simulation_1",
        character_id="character_1",
        current_time=NOW,
        entity_ids=[],
        query_embedding=[1, 0],
    )

    assert [entry.memory.id for entry in result.memories] == ["recent", "semantic"]
    assert result.memories[0].recall_sources == ["recent_event"]
    assert result.memories[1].recall_sources == ["embedding_match"]
    assert result.memories[0].selection_rank == 1


async def test_channels_are_deduplicated_and_scores_explain_fusion():
    shared = record(
        "shared",
        embedding=[1, 0],
        channels=["relationship_evidence", "portrait_evidence"],
    )
    retriever = MemoryRetriever(database(recent=[shared], graph=[shared], semantic=[shared]))

    result = await retriever.retrieve(
        simulation_id="simulation_1",
        character_id="character_1",
        current_time=NOW,
        entity_ids=["character_2"],
        query_embedding=[1, 0],
    )

    recalled = result.memories[0]
    assert recalled.recall_sources == [
        "recent_event",
        "portrait_evidence",
        "relationship_evidence",
        "embedding_match",
    ]
    assert recalled.channel_scores["relationship_evidence"] == .44
    assert recalled.channel_scores["embedding_match"] == .28
    assert recalled.fusion_score == 1


async def test_prompt_budget_truncation_is_stable_and_reported():
    memories = [
        record(f"memory_{index}", summary="x" * 120)
        for index in range(4)
    ]
    retriever = MemoryRetriever(database(recent=memories))

    first = await retriever.retrieve(
        simulation_id="simulation_1",
        character_id="character_1",
        current_time=NOW,
        entity_ids=[],
        query_embedding=None,
        token_budget=120,
    )
    second = await retriever.retrieve(
        simulation_id="simulation_1",
        character_id="character_1",
        current_time=NOW,
        entity_ids=[],
        query_embedding=None,
        token_budget=120,
    )

    assert [entry.memory.id for entry in first.memories] == [
        entry.memory.id for entry in second.memories
    ]
    assert first.diagnostics == second.diagnostics
    assert first.diagnostics.selected_count < first.diagnostics.considered_count
    assert first.diagnostics.dropped_memory_ids


async def test_missing_memory_embeddings_are_batched_and_cached():
    missing = record("missing", embedding=None)
    db = database(semantic=[missing])
    retriever = MemoryRetriever(db)

    result = await retriever.retrieve(
        simulation_id="simulation_1",
        character_id="character_1",
        current_time=NOW,
        entity_ids=[],
        query_embedding=[1, 0],
        embed_service=FakeEmbedService(),
    )

    assert [entry.memory.id for entry in result.memories] == ["missing"]
    assert result.memories[0].similarity == 1
    db.memory.update_embeddings.assert_awaited_once_with([
        {"memory_id": "missing", "embedding": [1, 0]},
    ])
