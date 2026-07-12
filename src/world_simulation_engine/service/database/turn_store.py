from neo4j import AsyncDriver

from world_simulation_engine.model import Turn


class TurnStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_turn(self,
                          turn: Turn,
                          source_id: str,
                          previous_turn_id: str | None = None,
                          ):
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (previous:Turn {id: $previous_turn_id})
            WITH source, previous
            WHERE $previous_turn_id IS NULL OR previous IS NOT NULL
            CREATE (turn:Turn {
                id: $id,
                sequence: $sequence,
                type: $type,
                content: $content,
                start_time: $start_time
            })
            MERGE (source)-[:CONTAINS]->(turn)
            WITH turn, previous
            FOREACH (_ IN CASE
                WHEN $previous_turn_id IS NOT NULL AND previous IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (previous)-[:NEXT]->(turn)
            )
            RETURN turn
            """,
            parameters_={
                "id": turn.id,
                "sequence": turn.sequence,
                "type": turn.type,
                "content": turn.content,
                "start_time": turn.start_time,
                "source_id": source_id,
                "previous_turn_id": previous_turn_id,
            },
        )
        if not result.records:
            raise ValueError("Could not create turn because the source or previous turn was not found")

    @staticmethod
    def turn_from_node(turn_node) -> Turn:
        start_time = turn_node["start_time"]
        if hasattr(start_time, "to_native"):
            start_time = start_time.to_native()

        return Turn(
            id=turn_node["id"],
            sequence=turn_node["sequence"],
            type=turn_node["type"],
            content=turn_node["content"],
            start_time=start_time,
        )

    async def create_next_turn(self,
                               *,
                               turn: Turn,
                               source_id: str,
                               ) -> Turn:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (source)-[:CONTAINS]->(previous:Turn)
            WITH source, previous
            ORDER BY previous.sequence DESC
            WITH source, collect(previous)[0] AS previous
            CREATE (turn:Turn {
                id: $id,
                sequence: coalesce(previous.sequence + 1, 0),
                type: $type,
                content: $content,
                start_time: $start_time
            })
            MERGE (source)-[:CONTAINS]->(turn)
            WITH turn, previous
            FOREACH (_ IN CASE
                WHEN previous IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (previous)-[:NEXT]->(turn)
            )
            RETURN turn
            """,
            parameters_={
                "id": turn.id,
                "type": turn.type,
                "content": turn.content,
                "start_time": turn.start_time,
                "source_id": source_id,
            },
        )
        if not result.records:
            raise ValueError("Could not create turn because the source was not found")

        return self.turn_from_node(result.records[0]["turn"])
