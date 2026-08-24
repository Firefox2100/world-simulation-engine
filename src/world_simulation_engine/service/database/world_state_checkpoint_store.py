import json

from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import WorldStateCheckpointType
from world_simulation_engine.model import WorldStateCheckpoint

# Every WorldStateCheckpoint list field, stored as its own "<field>_json" string property on one
# WorldStateCheckpoint node - mirrors GraphStateSnapshot's single state_json, just wider since a
# checkpoint captures many entity types instead of one opaque LangGraph state blob.
_ENTITY_FIELDS = (
    "characters",
    "background_characters",
    "items",
    "item_stacks",
    "equipment",
    "containers",
    "variable_sets",
    "entity_relationships",
    "emotion_states",
    "subjective_entity_claims",
    "memories",
    "events",
)


def _checkpoint_from_node(node) -> WorldStateCheckpoint:
    created_at = node["created_at"]
    if hasattr(created_at, "to_native"):
        created_at = created_at.to_native()

    return WorldStateCheckpoint(
        id=node["id"],
        simulation_id=node["simulation_id"],
        type=node["type"],
        turn_id=node.get("turn_id"),
        turn_sequence=node.get("turn_sequence"),
        created_at=created_at,
        **{field: json.loads(node[f"{field}_json"]) for field in _ENTITY_FIELDS},
    )


class WorldStateCheckpointStore:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    async def save_checkpoint(self, checkpoint: WorldStateCheckpoint) -> WorldStateCheckpoint:
        checkpoint_key = self._checkpoint_key(checkpoint)
        if checkpoint.type == WorldStateCheckpointType.BEFORE_USER_INPUT:
            await self._delete_existing_checkpoints(checkpoint.simulation_id)

        entity_parameters = {
            f"{field}_json": json.dumps(getattr(checkpoint, field))
            for field in _ENTITY_FIELDS
        }
        set_clause = ",\n                ".join(
            f"checkpoint.{field}_json = ${field}_json" for field in _ENTITY_FIELDS
        )
        result = await self._driver.execute_query(
            f"""
            MATCH (simulation:Simulation {{id: $simulation_id}})
            MERGE (simulation)-[:HAS_STATE_CHECKPOINT]->(
                checkpoint:WorldStateCheckpoint {{
                    simulation_id: $simulation_id,
                    checkpoint_key: $checkpoint_key
                }}
            )
            SET checkpoint.id = $id,
                checkpoint.type = $type,
                checkpoint.turn_id = $turn_id,
                checkpoint.turn_sequence = $turn_sequence,
                checkpoint.created_at = $created_at,
                {set_clause}
            RETURN checkpoint
            """,
            parameters_={
                "id": checkpoint.id,
                "simulation_id": checkpoint.simulation_id,
                "checkpoint_key": checkpoint_key,
                "type": checkpoint.type,
                "turn_id": checkpoint.turn_id,
                "turn_sequence": checkpoint.turn_sequence,
                "created_at": checkpoint.created_at,
                **entity_parameters,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            raise ValueError(f"Simulation {checkpoint.simulation_id} not found")

        return _checkpoint_from_node(record["checkpoint"])

    @staticmethod
    def _checkpoint_key(checkpoint: WorldStateCheckpoint) -> str:
        if checkpoint.type == WorldStateCheckpointType.BEFORE_USER_INPUT:
            return checkpoint.type

        if checkpoint.turn_sequence is None:
            raise ValueError(f"Checkpoint {checkpoint.type} requires a turn_sequence")

        return f"{checkpoint.type}:{checkpoint.turn_sequence}"

    async def _delete_existing_checkpoints(self, simulation_id: str):
        await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_STATE_CHECKPOINT]->(
                checkpoint:WorldStateCheckpoint
            )
            DETACH DELETE checkpoint
            """,
            parameters_={
                "simulation_id": simulation_id,
            },
        )

    async def get_checkpoint(
            self,
            simulation_id: str,
            type: WorldStateCheckpointType,
    ) -> WorldStateCheckpoint | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_STATE_CHECKPOINT]->(
                checkpoint:WorldStateCheckpoint {type: $type}
            )
            RETURN checkpoint
            ORDER BY checkpoint.turn_sequence DESC, checkpoint.created_at DESC
            LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "type": type,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _checkpoint_from_node(record["checkpoint"])

    async def get_checkpoint_by_id(self, checkpoint_id: str) -> WorldStateCheckpoint | None:
        """Fetch a specific historical checkpoint by its own id, not "the latest of its type" -
        needed when reverting to an archived TurnVersion, whose referenced checkpoint may no
        longer be the most recent one of that type."""
        result = await self._driver.execute_query(
            "MATCH (checkpoint:WorldStateCheckpoint {id: $id}) RETURN checkpoint LIMIT 1",
            parameters_={"id": checkpoint_id},
        )

        record = result.records[0] if result.records else None
        return _checkpoint_from_node(record["checkpoint"]) if record else None

    async def get_checkpoint_by_turn_sequence(
            self,
            simulation_id: str,
            turn_sequence: int,
    ) -> WorldStateCheckpoint | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_STATE_CHECKPOINT]->(
                checkpoint:WorldStateCheckpoint
            )
            WHERE checkpoint.type IN $types AND checkpoint.turn_sequence = $turn_sequence
            RETURN checkpoint
            ORDER BY checkpoint.created_at DESC
            LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "turn_sequence": turn_sequence,
                "types": [
                    WorldStateCheckpointType.AFTER_USER_INPUT,
                    WorldStateCheckpointType.AFTER_CHARACTER_ROUND,
                ],
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _checkpoint_from_node(record["checkpoint"])

    async def list_checkpoints(self, simulation_id: str) -> list[WorldStateCheckpoint]:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_STATE_CHECKPOINT]->(
                checkpoint:WorldStateCheckpoint
            )
            RETURN checkpoint
            ORDER BY checkpoint.created_at DESC
            """,
            parameters_={
                "simulation_id": simulation_id,
            },
        )

        return [
            _checkpoint_from_node(record["checkpoint"])
            for record in result.records
        ]
