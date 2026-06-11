import numpy as np
from icu import BreakIterator, Locale
from langchain_ollama import embeddings

from world_simulation_engine.misc.enums import WorldEntryRecallType
from world_simulation_engine.model import WorldEntry
from world_simulation_engine.service.embedding import EmbeddingService


class WorldEntryRecaller:
    def __init__(self,
                 embedding_service: EmbeddingService,
                 ):
        self._embedding_service = embedding_service

    @staticmethod
    def _segment_text(text: str, language: str):
        locale = Locale(language)
        bi = BreakIterator.createWordInstance(locale)
        bi.setText(text)

        start = bi.first()
        end = bi.nextBoundary()
        while end != BreakIterator.DONE:
            yield text[start:end]
            start = end
            end = bi.nextBoundary()

    @staticmethod
    def _ngrams(tokens: list[str], min_n: int = 1, max_n: int = 4) -> list[str]:
        for n in range(min_n, max_n + 1):
            for i in range(len(tokens) - n + 1):
                yield " ".join(tokens[i:i + n])

    @staticmethod
    def _score(a: list[float], b: list[float]) -> float:
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)

        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0

        c = float(np.dot(a, b) / denom)

        # Recommended for semantic search
        return max(0.0, min(1.0, c))

    async def recall(self,
                     query: str | None,
                     entries: list[WorldEntry],
                     language: str,
                     ) -> list[WorldEntry]:
        """
        Performs a recall operation to find relevant world entries based on the query.
        :param query: The query to search for.
        :param entries: The world entries that are already filtered for the role/stage.
        :param language: The language to segment the query in.
        :return: A trimmed list of world entries that matches the recall rules.
        """
        query_tokens = list(self._segment_text(query, language)) if query else []
        ngrams = list(self._ngrams(query_tokens, min_n=1, max_n=4)) if query_tokens else []

        if query and ngrams:
            embeddings = await self._embedding_service.embed_texts([query] + ngrams)
        else:
            embeddings = []

        recalled_entries = []
        semantic_entries = []
        chained_entries = []

        for entry in entries:
            if entry.recall_type == WorldEntryRecallType.ALWAYS:
                recalled_entries.append(entry)
            elif entry.recall_type == WorldEntryRecallType.SEMANTIC:
                if not entry.embedding or not embeddings:
                    continue

                semantic_entries.append((entry, self._score(embeddings[0], entry.embedding)))
            elif entry.recall_type == WorldEntryRecallType.KEYWORD:
                if not entry.keywords or not embeddings:
                    continue

                for k in entry.keywords:
                    if not k.embedding:
                        continue

                    recall = False
                    for e in embeddings[1:]:
                        if self._score(e, k.embedding) > k.similarity:
                            recall = True
                            break

                    if recall:
                        recalled_entries.append(entry)
                        break
            elif entry.recall_type == WorldEntryRecallType.CHAINED:
                chained_entries.append(entry)

        # Sort the semantic entries by score in descending order and take the top 5
        semantic_entries.sort(key=lambda x: x[1], reverse=True)
        recalled_entries.extend([e[0] for e in semantic_entries[:5]])

        # Scan the chained entry again
        for entry in chained_entries:
            if entry.chained_ids is None:
                continue

            for recalled in recalled_entries:
                if recalled.id in entry.chained_ids:
                    recalled_entries.append(entry)
                    break

        return recalled_entries
