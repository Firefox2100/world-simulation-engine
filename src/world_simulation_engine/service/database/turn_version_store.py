import json

from neo4j import AsyncDriver

from world_simulation_engine.model import TurnVersion


def _version_from_node(node) -> TurnVersion:
    created_at = node["created_at"]
    if hasattr(created_at, "to_native"):
        created_at = created_at.to_native()

    return TurnVersion(
        id=node["id"],
        simulation_id=node["simulation_id"],
        turn_sequence=node["turn_sequence"],
        turn=json.loads(node["turn_json"]),
        presentation_blocks=json.loads(node["presentation_blocks_json"]),
        user_input=node.get("user_input"),
        checkpoint_id=node.get("checkpoint_id"),
        created_at=created_at,
    )


class TurnVersionStore:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    async def archive_version(self, version: TurnVersion) -> TurnVersion:
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})
            CREATE (version:TurnVersion {
                id: $id,
                simulation_id: $simulation_id,
                turn_sequence: $turn_sequence,
                turn_json: $turn_json,
                presentation_blocks_json: $presentation_blocks_json,
                user_input: $user_input,
                checkpoint_id: $checkpoint_id,
                created_at: $created_at
            })
            MERGE (simulation)-[:HAS_TURN_VERSION]->(version)
            RETURN version
            """,
            parameters_={
                "id": version.id,
                "simulation_id": version.simulation_id,
                "turn_sequence": version.turn_sequence,
                "turn_json": json.dumps(version.turn),
                "presentation_blocks_json": json.dumps(version.presentation_blocks),
                "user_input": version.user_input,
                "checkpoint_id": version.checkpoint_id,
                "created_at": version.created_at,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            raise ValueError(f"Simulation {version.simulation_id} not found")

        return _version_from_node(record["version"])

    async def list_versions(self, *, simulation_id: str, turn_sequence: int) -> list[TurnVersion]:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_TURN_VERSION]->(
                version:TurnVersion {turn_sequence: $turn_sequence}
            )
            RETURN version
            ORDER BY version.created_at DESC
            """,
            parameters_={
                "simulation_id": simulation_id,
                "turn_sequence": turn_sequence,
            },
        )

        return [_version_from_node(record["version"]) for record in result.records]

    async def get_version(self, version_id: str) -> TurnVersion | None:
        result = await self._driver.execute_query(
            "MATCH (version:TurnVersion {id: $id}) RETURN version LIMIT 1",
            parameters_={"id": version_id},
        )

        record = result.records[0] if result.records else None
        return _version_from_node(record["version"]) if record else None

    async def delete_all_for_simulation(self, simulation_id: str) -> None:
        """Prune every archived swipe alternate for a simulation - called when a genuinely new
        user turn starts (mirrors WorldStateCheckpointStore's retention wipe on BEFORE_USER_INPUT):
        once the conversation moves forward, only whichever version the frontend left selected
        survives as the live Turn; every other swipe for that slot is no longer reachable and
        would otherwise accumulate forever."""
        await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_TURN_VERSION]->(version:TurnVersion)
            DETACH DELETE version
            """,
            parameters_={"simulation_id": simulation_id},
        )
