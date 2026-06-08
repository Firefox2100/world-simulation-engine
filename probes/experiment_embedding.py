import os
import asyncio
import numpy as np

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model import EmbeddingProfile, LlmConnectionProfile
from world_simulation_engine.service.embedding import EmbeddingService


OLLAMA_URL = os.getenv("EXP_OLLAMA_URL")
OLLAMA_MODEL_EMBED = os.getenv("EXP_OLLAMA_MODEL_EMBED")


async def experiment_embedding(service: EmbeddingService):
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

    target_embedding = (await service.embed_texts(target_text))[0]
    sample_embeddings = await service.embed_texts(sample_text)

    for i in range(0, len(sample_text)):
        a = np.asarray(sample_embeddings[i], dtype=np.float32)
        b = np.asarray(target_embedding, dtype=np.float32)

        denom = np.linalg.norm(a) * np.linalg.norm(b)

        if denom == 0:
            score = 0
        else:
            c = float(np.dot(a, b) / denom)
            score = max(0, min(1, c))

        print(f"Text '{sample_text[i]}' has a {score} similarity with '{target_text[0]}'")


def main():
    service = EmbeddingService(
        profile=EmbeddingProfile(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL_EMBED,
            dimensions=1024,
        ),
    )

    asyncio.run(experiment_embedding(service))


if __name__ == "__main__":
    main()
