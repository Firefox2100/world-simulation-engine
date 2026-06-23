import pytest

from world_simulation_engine.component import WorldEntryRecaller
from world_simulation_engine.misc.enums import (
    NarrationPermission,
    WorldEntryRecallType,
    WorldEntryVisibility,
)
from world_simulation_engine.model import WorldEntry, WorldEntryRecallKeyword


class FakeEmbeddingService:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(index), float(len(text))]
            for index, text in enumerate(texts, start=1)
        ]


def make_world_entry(**overrides) -> WorldEntry:
    data = {
        "id": 1,
        "scope": [0],
        "content": "The old mine is dangerous.",
        "visibility": WorldEntryVisibility.KNOWN,
        "confidence": 1.0,
        "created_at": None,
        "narration_permission": NarrationPermission.VISIBLE,
        "recall_type": WorldEntryRecallType.ALWAYS,
        "keywords": None,
        "chained_ids": None,
        "semantic_instruction": None,
        "embedding": [99.0],
    }
    data.update(overrides)
    return WorldEntry.model_validate(data)


@pytest.mark.asyncio
async def test_generate_entry_embeddings_for_semantic_entry():
    recaller = WorldEntryRecaller(FakeEmbeddingService())
    entry = make_world_entry(
        recall_type=WorldEntryRecallType.SEMANTIC,
        content="Remember the vanished director.",
        embedding=None,
    )

    result = await recaller.generate_entry_embeddings(entry)

    assert result.embedding == [1.0, 31.0]
    assert result.keywords is None


@pytest.mark.asyncio
async def test_generate_entry_embeddings_for_keyword_entry():
    recaller = WorldEntryRecaller(FakeEmbeddingService())
    entry = make_world_entry(
        recall_type=WorldEntryRecallType.KEYWORD,
        keywords=[
            WorldEntryRecallKeyword(keyword="old mine", similarity=0.72),
            WorldEntryRecallKeyword(keyword="mine collapse", similarity=0.75),
        ],
    )

    result = await recaller.generate_entry_embeddings(entry)

    assert result.embedding is None
    assert result.keywords is not None
    assert result.keywords[0].embedding == [1.0, 8.0]
    assert result.keywords[1].embedding == [2.0, 13.0]


@pytest.mark.asyncio
async def test_generate_entry_embeddings_clears_unused_embeddings():
    recaller = WorldEntryRecaller(FakeEmbeddingService())
    entry = make_world_entry(
        keywords=[
            WorldEntryRecallKeyword(
                keyword="old mine",
                similarity=0.72,
                embedding=[1.0],
            ),
        ],
    )

    result = await recaller.generate_entry_embeddings(entry)

    assert result.embedding is None
    assert result.keywords is not None
    assert result.keywords[0].embedding is None
