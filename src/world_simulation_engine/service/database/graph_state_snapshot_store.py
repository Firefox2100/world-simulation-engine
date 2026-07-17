import json

from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import GraphStateSnapshotType
from world_simulation_engine.model import GraphStateSnapshot


def _snapshot_from_node(snapshot_node) -> GraphStateSnapshot:
    created_at = snapshot_node["created_at"]
    if hasattr(created_at, "to_native"):
        created_at = created_at.to_native()

    return GraphStateSnapshot(
        id=snapshot_node["id"],
        simulation_id=snapshot_node["simulation_id"],
        type=snapshot_node["type"],
        turn_id=snapshot_node.get("turn_id"),
        turn_sequence=snapshot_node.get("turn_sequence"),
        state=json.loads(snapshot_node["state_json"]),
        created_at=created_at,
    )


class GraphStateSnapshotStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def save_snapshot(self,
                            snapshot: GraphStateSnapshot,
                            ) -> GraphStateSnapshot:
        snapshot_key = self._snapshot_key(snapshot)
        if snapshot.type == GraphStateSnapshotType.BEFORE_USER_INPUT:
            await self._delete_existing_snapshots(snapshot.simulation_id)

        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})
            MERGE (simulation)-[:HAS_GRAPH_STATE_SNAPSHOT]->(
                snapshot:GraphStateSnapshot {
                    simulation_id: $simulation_id,
                    snapshot_key: $snapshot_key
                }
            )
            SET snapshot.id = $id,
                snapshot.type = $type,
                snapshot.turn_id = $turn_id,
                snapshot.turn_sequence = $turn_sequence,
                snapshot.state_json = $state_json,
                snapshot.created_at = $created_at
            RETURN snapshot
            """,
            parameters_={
                "id": snapshot.id,
                "simulation_id": snapshot.simulation_id,
                "snapshot_key": snapshot_key,
                "type": snapshot.type,
                "turn_id": snapshot.turn_id,
                "turn_sequence": snapshot.turn_sequence,
                "state_json": json.dumps(snapshot.state),
                "created_at": snapshot.created_at,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            raise ValueError(f"Simulation {snapshot.simulation_id} not found")

        return _snapshot_from_node(record["snapshot"])

    @staticmethod
    def _snapshot_key(snapshot: GraphStateSnapshot) -> str:
        if snapshot.type == GraphStateSnapshotType.BEFORE_USER_INPUT:
            return snapshot.type

        if snapshot.turn_sequence is None:
            raise ValueError(f"Snapshot {snapshot.type} requires a turn_sequence")

        return f"{snapshot.type}:{snapshot.turn_sequence}"

    async def _delete_existing_snapshots(self, simulation_id: str):
        await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GRAPH_STATE_SNAPSHOT]->(
                snapshot:GraphStateSnapshot
            )
            DETACH DELETE snapshot
            """,
            parameters_={
                "simulation_id": simulation_id,
            },
        )

    async def get_snapshot(self,
                           simulation_id: str,
                           type: GraphStateSnapshotType,
                           ) -> GraphStateSnapshot | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GRAPH_STATE_SNAPSHOT]->(
                snapshot:GraphStateSnapshot {type: $type}
            )
            RETURN snapshot
            ORDER BY snapshot.turn_sequence DESC, snapshot.created_at DESC
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

        return _snapshot_from_node(record["snapshot"])

    async def get_generation_base_snapshot_by_turn_sequence(
            self,
            simulation_id: str,
            turn_sequence: int,
    ) -> GraphStateSnapshot | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GRAPH_STATE_SNAPSHOT]->(
                snapshot:GraphStateSnapshot
            )
            WHERE snapshot.type IN $types AND snapshot.turn_sequence = $turn_sequence
            RETURN snapshot
            ORDER BY snapshot.created_at DESC
            LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "turn_sequence": turn_sequence,
                "types": [
                    GraphStateSnapshotType.AFTER_USER_INPUT,
                    GraphStateSnapshotType.AFTER_CHARACTER_ROUND,
                ],
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _snapshot_from_node(record["snapshot"])

    async def get_latest_generation_base_snapshot(
            self,
            simulation_id: str,
    ) -> GraphStateSnapshot | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GRAPH_STATE_SNAPSHOT]->(
                snapshot:GraphStateSnapshot
            )
            WHERE snapshot.type IN $types
            RETURN snapshot
            ORDER BY snapshot.turn_sequence DESC, snapshot.created_at DESC
            LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "types": [
                    GraphStateSnapshotType.AFTER_USER_INPUT,
                    GraphStateSnapshotType.AFTER_CHARACTER_ROUND,
                ],
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _snapshot_from_node(record["snapshot"])

    async def list_snapshots(self,
                             simulation_id: str,
                             ) -> list[GraphStateSnapshot]:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_GRAPH_STATE_SNAPSHOT]->(
                snapshot:GraphStateSnapshot
            )
            RETURN snapshot
            ORDER BY snapshot.created_at DESC
            """,
            parameters_={
                "simulation_id": simulation_id,
            },
        )

        return [
            _snapshot_from_node(record["snapshot"])
            for record in result.records
        ]
