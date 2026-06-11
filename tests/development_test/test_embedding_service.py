import numpy as np
import pytest

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.service import EmbeddingService


@pytest.fixture
def embedding_service(mock_embedding_profile,
                      mock_llm_connection,
                      ) -> EmbeddingService:
    return EmbeddingService(
        profile=mock_embedding_profile,
        connection=mock_llm_connection,
    )


async def test_embedding_comparison(embedding_service):
    sample_text = [
        "old mine",
        "coal mine",
        "mine",
        "collapsed mine",
        "gold mine",
    ]
    target_text = [
        "old mine",
    ]

    target_embedding = (await embedding_service.embed_texts(target_text))[0]
    sample_embeddings = await embedding_service.embed_texts(sample_text)

    for i in range(0, len(sample_text)):
        a = np.asarray(sample_embeddings[i], dtype=np.float32)
        b = np.asarray(target_embedding, dtype=np.float32)

        denom = np.linalg.norm(a) * np.linalg.norm(b)

        if denom == 0:
            score = 0
        else:
            c = float(np.dot(a, b) / denom)
            score = max(0, min(1, c))

        LOGGER.debug("Text '%s' has a %s similarity with '%s'", sample_text[i], score, target_text[0])
