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

    async def get_turn(self, turn_id: str) -> Turn | None:
        result = await self._driver.execute_query(
            """
            MATCH (turn:Turn {id: $turn_id})
            RETURN turn LIMIT 1
            """,
            parameters_={"turn_id": turn_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.turn_from_node(record["turn"])

    async def list_turns(self,
                         source_id: str | None = None,
                         limit: int = 10,
                         skip: int = 0,
                         ) -> list[Turn]:
        if source_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(turn:Turn)
                RETURN turn
                ORDER BY turn.sequence DESC
                SKIP $skip
                LIMIT $limit
                """,
                parameters_={
                    "source_id": source_id,
                    "limit": limit,
                    "skip": skip,
                },
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (turn:Turn)
                RETURN turn
                ORDER BY turn.sequence DESC
                SKIP $skip
                LIMIT $limit
                """,
                parameters_={
                    "limit": limit,
                    "skip": skip,
                },
            )

        return [
            self.turn_from_node(record["turn"])
            for record in result.records
        ]

    async def get_turn_by_sequence(self,
                                   source_id: str,
                                   sequence: int,
                                   ) -> Turn | None:
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(turn:Turn {sequence: $sequence})
            RETURN turn LIMIT 1
            """,
            parameters_={
                "source_id": source_id,
                "sequence": sequence,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.turn_from_node(record["turn"])

    async def copy_turns(self,
                         source_id: str,
                         target_id: str,
                         ) -> tuple[list[Turn], list[dict]]:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            MATCH (target:World|Simulation {id: $target_id})
            MATCH (source)-[:CONTAINS]->(source_turn:Turn)
            WITH target, source_turn
            ORDER BY source_turn.sequence
            CREATE (turn:Turn {
                id: randomUUID(),
                sequence: source_turn.sequence,
                type: source_turn.type,
                content: source_turn.content,
                start_time: source_turn.start_time
            })
            MERGE (target)-[:CONTAINS]->(turn)
            WITH collect({
                source_id: source_turn.id,
                copy_id: turn.id,
                copy: turn
            }) AS turn_pairs
            CALL {
                WITH turn_pairs
                UNWIND turn_pairs AS previous_pair
                UNWIND turn_pairs AS next_pair
                MATCH (:Turn {id: previous_pair.source_id})-[:NEXT]->(:Turn {id: next_pair.source_id})
                MATCH (previous_copy:Turn {id: previous_pair.copy_id})
                MATCH (next_copy:Turn {id: next_pair.copy_id})
                MERGE (previous_copy)-[:NEXT]->(next_copy)
                RETURN count(*) AS link_count
            }
            WITH turn_pairs
            UNWIND turn_pairs AS pair
            RETURN pair.source_id AS source_id, pair.copy_id AS copy_id, pair.copy AS turn
            ORDER BY turn.sequence
            """,
            parameters_={
                "source_id": source_id,
                "target_id": target_id,
            },
        )

        turns = [
            self.turn_from_node(record["turn"])
            for record in result.records
        ]
        turn_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]

        return turns, turn_pairs
