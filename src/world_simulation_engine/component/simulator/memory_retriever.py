"""Deterministic multi-channel memory retrieval and prompt-budget fusion."""

from datetime import datetime
import inspect
from math import ceil, exp, log, sqrt

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience
from world_simulation_engine.model import Event, MemoryAtom
from world_simulation_engine.service.database.memory_store import MemoryRecallRecord


class RecalledMemory(BaseModel):
    memory: MemoryAtom
    event: Event
    event_id: str
    event_name: str
    event_summary: str
    event_ending_time: datetime
    support_type: MemorySupportType
    confidence: float = Field(ge=0, le=1)
    decayed_confidence: float = Field(ge=0, le=1)
    salience: Salience
    behavioural_relevance: str | None = None
    stance: MemoryStance
    recall_sources: list[str] = Field(default_factory=list)
    channel_scores: dict[str, float] = Field(default_factory=dict)
    similarity: float | None = None
    fusion_score: float = Field(default=0, ge=0, le=1)
    selection_rank: int | None = Field(default=None, ge=1)
    estimated_tokens: int = Field(default=0, ge=0)


class MemoryRetrievalDiagnostics(BaseModel):
    considered_count: int = 0
    selected_count: int = 0
    token_budget: int
    estimated_tokens_used: int = 0
    dropped_memory_ids: list[str] = Field(default_factory=list)


class MemoryRetrievalResult(BaseModel):
    memories: list[RecalledMemory] = Field(default_factory=list)
    diagnostics: MemoryRetrievalDiagnostics


class MemoryRetriever:
    """Fuse graph evidence before bounded semantic similarity."""

    RECENT = "recent_event"
    ENTITY = "entity_neighborhood"
    INTENT = "active_intent"
    RELATIONSHIP = "relationship_evidence"
    PORTRAIT = "portrait_evidence"
    SEMANTIC = "embedding_match"

    _CHANNEL_WEIGHT = {
        RECENT: .55,
        INTENT: .48,
        RELATIONSHIP: .44,
        PORTRAIT: .42,
        ENTITY: .38,
    }
    _CHANNEL_PRIORITY = {
        RECENT: 5,
        INTENT: 4,
        RELATIONSHIP: 4,
        PORTRAIT: 4,
        ENTITY: 3,
        SEMANTIC: 1,
    }
    _SALIENCE = {
        Salience.LOW: .02,
        Salience.MEDIUM: .05,
        Salience.HIGH: .08,
        Salience.CRITICAL: .1,
    }

    def __init__(self, database):
        self._db = database

    async def _records(self, method_name: str, **kwargs) -> list[MemoryRecallRecord]:
        method = getattr(self._db.memory, method_name, None)
        if not inspect.iscoroutinefunction(method):
            return []
        return await method(**kwargs)

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0

    @staticmethod
    def decayed_confidence(
            record: MemoryRecallRecord,
            current_time: datetime,
            half_life_days: float = 30,
    ) -> float:
        elapsed_days = max((current_time - record.event_ending_time).total_seconds() / 86400, 0)
        return max(min(record.confidence * exp(-log(2) * elapsed_days / half_life_days), 1), 0)

    @staticmethod
    def _temporal_score(record: MemoryRecallRecord, current_time: datetime) -> float:
        elapsed_days = max((current_time - record.event_ending_time).total_seconds() / 86400, 0)
        return .12 * exp(-log(2) * elapsed_days / 7)

    @staticmethod
    def estimate_tokens(record: MemoryRecallRecord) -> int:
        text = " ".join(filter(None, [
            record.memory.summary,
            record.event.name,
            record.event.summary,
            record.behavioural_relevance,
        ]))
        return 24 + ceil(len(text) / 4)

    async def retrieve(
            self,
            *,
            simulation_id: str,
            character_id: str,
            current_time: datetime,
            entity_ids: list[str],
            query_embedding: list[float] | None,
            embed_service=None,
            max_memories: int = 12,
            token_budget: int = 1200,
    ) -> MemoryRetrievalResult:
        recent = await self._records(
            "get_recent_turn_memory_candidates",
            character_id=character_id,
            source_id=simulation_id,
            turn_limit=5,
        )
        graph = await self._records(
            "get_graph_memory_candidates",
            character_id=character_id,
            source_id=simulation_id,
            entity_ids=entity_ids,
            limit=50,
        )
        semantic_records = (
            await self._records(
                "get_scoped_character_memory_candidates",
                character_id=character_id,
                source_id=simulation_id,
                limit=200,
            )
            if query_embedding else []
        )
        missing_embeddings = [
            record
            for record in semantic_records
            if record.memory.embedding is None
        ]
        if missing_embeddings and embed_service is not None:
            embedded = await embed_service.embed_texts([
                " ".join([record.memory.summary, *record.memory.keywords])
                for record in missing_embeddings
            ])
            embedding_rows = []
            replacements = {}
            for record, vector in zip(missing_embeddings, embedded):
                replacements[record.memory.id] = record.model_copy(update={
                    "memory": record.memory.model_copy(update={"embedding": vector}),
                })
                embedding_rows.append({"memory_id": record.memory.id, "embedding": vector})
            semantic_records = [
                replacements.get(record.memory.id, record)
                for record in semantic_records
            ]
            update_embeddings = getattr(self._db.memory, "update_embeddings", None)
            if inspect.iscoroutinefunction(update_embeddings):
                await update_embeddings(embedding_rows)

        records: dict[str, MemoryRecallRecord] = {}
        sources: dict[str, set[str]] = {}
        similarity: dict[str, float] = {}
        for record in recent:
            records[record.memory.id] = record
            sources.setdefault(record.memory.id, set()).add(self.RECENT)
        for record in graph:
            records[record.memory.id] = record
            sources.setdefault(record.memory.id, set()).update(record.recall_channels)
        for record in semantic_records:
            score = self.cosine_similarity(query_embedding or [], record.memory.embedding or [])
            if score < .15:
                continue
            records.setdefault(record.memory.id, record)
            sources.setdefault(record.memory.id, set()).add(self.SEMANTIC)
            similarity[record.memory.id] = score

        candidates = []
        for memory_id, record in records.items():
            memory_sources = sources[memory_id]
            decayed = self.decayed_confidence(record, current_time)
            if memory_sources == {self.SEMANTIC} and decayed < .2:
                continue
            channel_scores = {
                source: (
                    min(max(similarity.get(memory_id, 0), 0), 1) * .28
                    if source == self.SEMANTIC
                    else self._CHANNEL_WEIGHT[source]
                )
                for source in sorted(memory_sources)
            }
            confidence_score = decayed * .2
            temporal_score = self._temporal_score(record, current_time)
            channel_scores["confidence"] = confidence_score
            channel_scores["temporal_proximity"] = temporal_score
            channel_scores["salience"] = self._SALIENCE[record.salience]
            fusion_score = min(sum(channel_scores.values()), 1)
            priority = max(self._CHANNEL_PRIORITY[source] for source in memory_sources)
            candidates.append((
                priority,
                fusion_score,
                record.event_ending_time,
                memory_id,
                record,
                memory_sources,
                channel_scores,
                decayed,
            ))
        candidates.sort(key=lambda item: (-item[0], -item[1], -item[2].timestamp(), item[3]))

        selected = []
        dropped = []
        used = 0
        for _, fusion_score, _, memory_id, record, memory_sources, channel_scores, decayed in candidates:
            estimated = self.estimate_tokens(record)
            if len(selected) >= max_memories or used + estimated > token_budget:
                dropped.append(memory_id)
                continue
            used += estimated
            selected.append(RecalledMemory(
                memory=record.memory,
                event=record.event,
                event_id=record.event.id,
                event_name=record.event.name,
                event_summary=record.event.summary,
                event_ending_time=record.event_ending_time,
                support_type=record.support_type,
                confidence=record.confidence,
                decayed_confidence=decayed,
                salience=record.salience,
                behavioural_relevance=record.behavioural_relevance,
                stance=record.stance,
                recall_sources=sorted(
                    memory_sources,
                    key=lambda source: (-self._CHANNEL_PRIORITY[source], source),
                ),
                channel_scores=channel_scores,
                similarity=similarity.get(memory_id),
                fusion_score=fusion_score,
                selection_rank=len(selected) + 1,
                estimated_tokens=estimated,
            ))
        return MemoryRetrievalResult(
            memories=selected,
            diagnostics=MemoryRetrievalDiagnostics(
                considered_count=len(candidates),
                selected_count=len(selected),
                token_budget=token_budget,
                estimated_tokens_used=used,
                dropped_memory_ids=dropped,
            ),
        )
