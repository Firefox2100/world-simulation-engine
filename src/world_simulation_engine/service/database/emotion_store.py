"""Neo4j persistence and simulation-time decay for private emotion state."""

import json
from datetime import datetime
from math import exp, log

from neo4j import AsyncDriver

from world_simulation_engine.model import EmotionChangeAudit, EmotionState, EmotionVector


class EmotionStore:
    """Persist emotion state and immutable event-change provenance."""

    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @staticmethod
    def _state_from_node(node) -> EmotionState:
        updated_at = node["last_updated_at"]
        if hasattr(updated_at, "to_native"):
            updated_at = updated_at.to_native()
        return EmotionState(
            id=node["id"],
            simulation_id=node["simulation_id"],
            character_id=node["character_id"],
            baseline=json.loads(node["baseline_json"]),
            immediate=json.loads(node["immediate_json"]),
            baseline_half_life_seconds=node["baseline_half_life_seconds"],
            immediate_half_life_seconds=node["immediate_half_life_seconds"],
            last_updated_at=updated_at,
            version=node["version"],
        )

    async def get_state(
            self,
            *,
            simulation_id: str,
            character_id: str,
    ) -> EmotionState | None:
        """Return the stored, non-decayed state for one simulation character."""
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->
                (state:EmotionState {character_id: $character_id})
            RETURN state LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "character_id": character_id,
            },
        )
        return self._state_from_node(result.records[0]["state"]) if result.records else None

    async def character_belongs_to_simulation(
            self,
            *,
            simulation_id: str,
            character_id: str,
    ) -> bool:
        """Check ownership before exposing or author-editing private state."""
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->
                (:Character {id: $character_id})
            RETURN 1 AS found LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "character_id": character_id,
            },
        )
        return bool(result.records)

    async def validate_memory_evidence(
            self,
            *,
            simulation_id: str,
            character_id: str,
            memory_ids: list[str],
    ) -> bool:
        """Require every memory to belong to this character and simulation event history."""
        if not memory_ids:
            return False
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})-[:CONTAINS]->
                (character:Character {id: $character_id})-[:REMEMBERS]->(memory:MemoryAtom)
            MATCH (simulation)-[:CONTAINS]->(:Turn)-[:PART_OF]->(:Event)-[:SUPPORTS]->(memory)
            WHERE memory.id IN $memory_ids
            RETURN count(DISTINCT memory.id) AS found
            """,
            parameters_={
                "simulation_id": simulation_id,
                "character_id": character_id,
                "memory_ids": list(dict.fromkeys(memory_ids)),
            },
        )
        return bool(
            result.records
            and result.records[0]["found"] == len(set(memory_ids))
        )

    async def create_state(self, state: EmotionState) -> EmotionState | None:
        """Create the sole emotion state for a simulation character."""
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})-[:CONTAINS]->
                (character:Character {id: $character_id})
            WHERE NOT EXISTS {
                MATCH (simulation)-[:CONTAINS]->(:EmotionState {character_id: $character_id})
            }
            CREATE (state:EmotionState {
                id: $id,
                simulation_id: $simulation_id,
                character_id: $character_id,
                baseline_json: $baseline_json,
                immediate_json: $immediate_json,
                baseline_half_life_seconds: $baseline_half_life_seconds,
                immediate_half_life_seconds: $immediate_half_life_seconds,
                last_updated_at: $last_updated_at,
                version: $version
            })
            MERGE (simulation)-[:CONTAINS]->(state)
            MERGE (character)-[:HAS_EMOTION_STATE]->(state)
            RETURN state
            """,
            parameters_=self._state_parameters(state),
        )
        return self._state_from_node(result.records[0]["state"]) if result.records else None

    async def update_state(self, state: EmotionState) -> EmotionState | None:
        """Update one version with a write lock guarding overlapping simulation work."""
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->
                (stored:EmotionState {id: $id, character_id: $character_id})
            SET stored._update_lock = coalesce(stored._update_lock, 0) + 1
            WITH stored
            WHERE stored.version = $expected_version
                AND stored.last_updated_at <= $last_updated_at
            SET stored.baseline_json = $baseline_json,
                stored.immediate_json = $immediate_json,
                stored.baseline_half_life_seconds = $baseline_half_life_seconds,
                stored.immediate_half_life_seconds = $immediate_half_life_seconds,
                stored.last_updated_at = $last_updated_at,
                stored.version = $version
            RETURN stored AS state
            """,
            parameters_={
                **self._state_parameters(state),
                "expected_version": state.version - 1,
            },
        )
        return self._state_from_node(result.records[0]["state"]) if result.records else None

    async def create_change_audit(
            self,
            audit: EmotionChangeAudit,
    ) -> EmotionChangeAudit | None:
        """Link an immutable change record to its turn, memories, and events."""
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})-[:CONTAINS]->
                (state:EmotionState {id: $emotion_state_id})
            MATCH (simulation)-[:CONTAINS]->(turn:Turn {id: $turn_id})
            MATCH (simulation)-[:CONTAINS]->(character:Character {id: $character_id})
            MATCH (event:Event)-[:SUPPORTS]->(memory:MemoryAtom)
            WHERE memory.id IN $evidence_memory_ids
                AND EXISTS { MATCH (character)-[:REMEMBERS]->(memory) }
                AND EXISTS {
                    MATCH (simulation)-[:CONTAINS]->(:Turn)-[:PART_OF]->(event)
                }
            WITH simulation, state, turn, collect(DISTINCT memory) AS memories,
                collect(DISTINCT event) AS events
            WHERE size(memories) = size($evidence_memory_ids)
                AND NOT EXISTS { MATCH (:EmotionChangeAudit {id: $id}) }
            CREATE (audit:EmotionChangeAudit {
                id: $id,
                emotion_state_id: $emotion_state_id,
                simulation_id: $simulation_id,
                character_id: $character_id,
                turn_id: $turn_id,
                evidence_memory_ids: $evidence_memory_ids,
                changed_at: $changed_at,
                change_type: $change_type,
                previous_version: $previous_version,
                new_version: $new_version,
                previous_state_json: $previous_state_json,
                new_state_json: $new_state_json
            })
            MERGE (simulation)-[:CONTAINS]->(audit)
            MERGE (turn)-[:TRIGGERED]->(audit)
            MERGE (audit)-[:CHANGED]->(state)
            FOREACH (memory IN memories | MERGE (memory)-[:EVIDENCE_FOR]->(audit))
            FOREACH (event IN events | MERGE (event)-[:CAUSED_EMOTION_CHANGE]->(audit))
            RETURN audit
            """,
            parameters_={
                **audit.model_dump(exclude={"previous_state", "new_state"}),
                "previous_state_json": (
                    json.dumps(audit.previous_state, sort_keys=True)
                    if audit.previous_state is not None else None
                ),
                "new_state_json": json.dumps(audit.new_state, sort_keys=True),
            },
        )
        return audit if result.records else None

    async def list_change_audits(self, emotion_state_id: str) -> list[EmotionChangeAudit]:
        """Return provenance ordered by resulting state version."""
        result = await self._driver.execute_query(
            """
            MATCH (audit:EmotionChangeAudit {emotion_state_id: $emotion_state_id})
            RETURN audit ORDER BY audit.new_version, audit.id
            """,
            parameters_={"emotion_state_id": emotion_state_id},
        )
        audits = []
        for record in result.records:
            node = record["audit"]
            changed_at = node["changed_at"]
            if hasattr(changed_at, "to_native"):
                changed_at = changed_at.to_native()
            audits.append(EmotionChangeAudit(
                id=node["id"],
                emotion_state_id=node["emotion_state_id"],
                simulation_id=node["simulation_id"],
                character_id=node["character_id"],
                turn_id=node["turn_id"],
                evidence_memory_ids=list(node["evidence_memory_ids"]),
                changed_at=changed_at,
                change_type=node["change_type"],
                previous_version=node.get("previous_version"),
                new_version=node["new_version"],
                previous_state=(
                    json.loads(node["previous_state_json"])
                    if node.get("previous_state_json") else None
                ),
                new_state=json.loads(node["new_state_json"]),
            ))
        return audits

    @classmethod
    def decay_state(cls, state: EmotionState, at_time: datetime) -> EmotionState:
        """Return deterministic decay toward neutral using elapsed simulation time."""
        elapsed_seconds = max((at_time - state.last_updated_at).total_seconds(), 0)
        return state.model_copy(update={
            "baseline": cls._decay_vector(
                state.baseline,
                elapsed_seconds,
                state.baseline_half_life_seconds,
            ),
            "immediate": cls._decay_vector(
                state.immediate,
                elapsed_seconds,
                state.immediate_half_life_seconds,
            ),
            "last_updated_at": max(at_time, state.last_updated_at),
        })

    @staticmethod
    def combined_vector(state: EmotionState) -> EmotionVector:
        """Combine baseline and immediate response for compact prompt context."""
        dimensions = set(state.baseline.dimensions) | set(state.immediate.dimensions)
        return EmotionVector(
            valence=max(min(state.baseline.valence + state.immediate.valence, 1), -1),
            arousal=max(min(state.baseline.arousal + state.immediate.arousal, 1), -1),
            dominance=max(min(state.baseline.dominance + state.immediate.dominance, 1), -1),
            dimensions={
                key: max(min(
                    state.baseline.dimensions.get(key, 0)
                    + state.immediate.dimensions.get(key, 0),
                    1,
                ), -1)
                for key in sorted(dimensions)
            },
        )

    @staticmethod
    def _decay_vector(vector: EmotionVector, elapsed: float, half_life: int) -> EmotionVector:
        multiplier = exp(-log(2) * elapsed / half_life)
        return EmotionVector(
            valence=vector.valence * multiplier,
            arousal=vector.arousal * multiplier,
            dominance=vector.dominance * multiplier,
            dimensions={key: value * multiplier for key, value in vector.dimensions.items()},
        )

    @staticmethod
    def _state_parameters(state: EmotionState) -> dict:
        return {
            "id": state.id,
            "simulation_id": state.simulation_id,
            "character_id": state.character_id,
            "baseline_json": state.baseline.model_dump_json(),
            "immediate_json": state.immediate.model_dump_json(),
            "baseline_half_life_seconds": state.baseline_half_life_seconds,
            "immediate_half_life_seconds": state.immediate_half_life_seconds,
            "last_updated_at": state.last_updated_at,
            "version": state.version,
        }
