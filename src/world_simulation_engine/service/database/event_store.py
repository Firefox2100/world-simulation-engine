from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import EventInvolvement
from world_simulation_engine.model import Event


class EventStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def event_from_node(event_node) -> Event:
        return Event(
            id=event_node["id"],
            name=event_node["name"],
            summary=event_node["summary"],
        )

    async def create_event(self,
                           event: Event,
                           turn_ids: list[str],
                           ) -> Event | None:
        turn_ids = list(dict.fromkeys(turn_ids))
        if not turn_ids:
            raise ValueError("An event must be attached to at least one turn")

        result = await self._driver.execute_query(
            """
            MATCH (turn:Turn)
            WHERE turn.id IN $turn_ids
            WITH collect(turn) AS turns
            WHERE size(turns) = size($turn_ids)
            CREATE (event:Event {
                id: $id,
                name: $name,
                summary: $summary
            })
            WITH event, turns
            UNWIND turns AS turn
            MERGE (turn)-[:PART_OF]->(event)
            RETURN event
            """,
            parameters_={
                "id": event.id,
                "name": event.name,
                "summary": event.summary,
                "turn_ids": turn_ids,
            },
        )
        if not result.records:
            return None

        return self.event_from_node(result.records[0]["event"])

    async def list_events(self,
                          character_id: str | None = None,
                          turn_id: str | None = None,
                          ) -> list[Event]:
        if character_id is not None and turn_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Turn {id: $turn_id})-[:PART_OF]->(event:Event)-[:INVOLVES]->(:Character {id: $character_id})
                RETURN event
                ORDER BY event.name
                """,
                parameters_={
                    "character_id": character_id,
                    "turn_id": turn_id,
                },
            )
        elif character_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (event:Event)-[:INVOLVES]->(:Character {id: $character_id})
                RETURN event
                ORDER BY event.name
                """,
                parameters_={"character_id": character_id},
            )
        elif turn_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Turn {id: $turn_id})-[:PART_OF]->(event:Event)
                RETURN event
                ORDER BY event.name
                """,
                parameters_={"turn_id": turn_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (event:Event)
                RETURN event
                ORDER BY event.name
                """
            )

        return [
            self.event_from_node(record["event"])
            for record in result.records
        ]

    async def get_event(self, event_id: str) -> Event | None:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            RETURN event LIMIT 1
            """,
            parameters_={"event_id": event_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.event_from_node(record["event"])

    async def add_turn_to_event(self,
                                event_id: str,
                                turn_id: str,
                                ) -> Event | None:
        result = await self._driver.execute_query(
            """
            MATCH (turn:Turn {id: $turn_id})
            MATCH (event:Event {id: $event_id})
            MERGE (turn)-[:PART_OF]->(event)
            RETURN event
            """,
            parameters_={
                "event_id": event_id,
                "turn_id": turn_id,
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.event_from_node(record["event"])

    async def replace_event_turns(self,
                                  event_id: str,
                                  turn_ids: list[str],
                                  ) -> Event | None:
        turn_ids = list(dict.fromkeys(turn_ids))
        if not turn_ids:
            raise ValueError("An event must be attached to at least one turn")

        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (turn:Turn)
            WHERE turn.id IN $turn_ids
            WITH event, collect(turn) AS turns
            WHERE size(turns) = size($turn_ids)
            OPTIONAL MATCH (:Turn)-[existing:PART_OF]->(event)
            DELETE existing
            WITH event, turns
            UNWIND turns AS turn
            MERGE (turn)-[:PART_OF]->(event)
            RETURN event
            """,
            parameters_={
                "event_id": event_id,
                "turn_ids": turn_ids,
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.event_from_node(record["event"])

    async def remove_event_turns(self,
                                 event_id: str,
                                 turn_ids: list[str],
                                 ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            OPTIONAL MATCH (remaining_turn:Turn)-[:PART_OF]->(event)
            WITH event, count(remaining_turn) AS existing_count
            OPTIONAL MATCH (removed_turn:Turn)-[part:PART_OF]->(event)
            WHERE removed_turn.id IN $turn_ids
            WITH event, existing_count, collect(part) AS parts
            WHERE existing_count > size(parts)
            FOREACH (part IN parts | DELETE part)
            RETURN count(event) AS event_count
            """,
            parameters_={
                "event_id": event_id,
                "turn_ids": list(dict.fromkeys(turn_ids)),
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["event_count"])

    async def update_event(self,
                           event_id: str,
                           name: str | None = None,
                           summary: str | None = None,
                           ) -> Event | None:
        properties = {}
        if name is not None:
            properties["name"] = name
        if summary is not None:
            properties["summary"] = summary
        if not properties:
            return await self.get_event(event_id)

        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            SET event += $properties
            RETURN event LIMIT 1
            """,
            parameters_={
                "event_id": event_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.event_from_node(record["event"])

    async def delete_event(self, event_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            WITH collect(event) AS events
            FOREACH (event IN events | DETACH DELETE event)
            RETURN size(events) AS deleted
            """,
            parameters_={"event_id": event_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def add_character_involvement(self,
                                        event_id: str,
                                        character_id: str,
                                        involvement: EventInvolvement,
                                        ) -> Event | None:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (character:Character {id: $character_id})
            MERGE (event)-[relationship:INVOLVES]->(character)
            SET relationship.involvement = $involvement
            RETURN event
            """,
            parameters_={
                "event_id": event_id,
                "character_id": character_id,
                "involvement": involvement,
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.event_from_node(record["event"])

    async def replace_character_involvements(self,
                                             event_id: str,
                                             involvements: list[dict],
                                             ) -> Event | None:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            OPTIONAL MATCH (event)-[existing:INVOLVES]->(:Character)
            DELETE existing
            WITH event
            CALL {
                WITH event
                UNWIND $involvements AS involvement
                MATCH (character:Character {id: involvement.character_id})
                MERGE (event)-[relationship:INVOLVES]->(character)
                SET relationship.involvement = involvement.involvement
                RETURN count(*) AS linked_count
            }
            RETURN event
            """,
            parameters_={
                "event_id": event_id,
                "involvements": involvements,
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.event_from_node(record["event"])

    async def remove_character_involvements(self,
                                            event_id: str,
                                            character_ids: list[str],
                                            ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            CALL {
                WITH event
                UNWIND $character_ids AS character_id
                OPTIONAL MATCH (event)-[involves:INVOLVES]->(:Character {id: character_id})
                DELETE involves
                RETURN count(*) AS removed_count
            }
            RETURN count(event) AS event_count
            """,
            parameters_={
                "event_id": event_id,
                "character_ids": character_ids,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["event_count"])

    async def copy_events(self,
                          turn_pairs: list[dict],
                          character_pairs: list[dict] | None = None,
                          ) -> tuple[list[Event], list[dict]]:
        character_pairs = character_pairs or []
        if not turn_pairs:
            return [], []

        result = await self._driver.execute_query(
            """
            UNWIND $turn_pairs AS turn_pair
            MATCH (:Turn {id: turn_pair.source_id})-[:PART_OF]->(source_event:Event)
            WITH DISTINCT source_event
            CREATE (event:Event {
                id: randomUUID(),
                name: source_event.name,
                summary: source_event.summary
            })
            RETURN source_event.id AS source_id, event.id AS copy_id, event
            ORDER BY event.name
            """,
            parameters_={"turn_pairs": turn_pairs},
        )
        event_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if event_pairs:
            await self._driver.execute_query(
                """
                UNWIND $event_pairs AS event_pair
                MATCH (source_turn:Turn)-[:PART_OF]->(:Event {id: event_pair.source_id})
                WITH event_pair, [
                    turn_pair IN $turn_pairs
                    WHERE turn_pair.source_id = source_turn.id
                ][0] AS turn_pair
                WHERE turn_pair IS NOT NULL
                MATCH (copy_turn:Turn {id: turn_pair.copy_id})
                MATCH (copy_event:Event {id: event_pair.copy_id})
                MERGE (copy_turn)-[:PART_OF]->(copy_event)
                """,
                parameters_={
                    "event_pairs": event_pairs,
                    "turn_pairs": turn_pairs,
                },
            )
        if event_pairs and character_pairs:
            await self._driver.execute_query(
                """
                UNWIND $event_pairs AS event_pair
                MATCH (:Event {id: event_pair.source_id})-[source_relationship:INVOLVES]->(source_character:Character)
                WITH event_pair, source_relationship, [
                    character_pair IN $character_pairs
                    WHERE character_pair.source_id = source_character.id
                ][0] AS character_pair
                WHERE character_pair IS NOT NULL
                MATCH (copy_event:Event {id: event_pair.copy_id})
                MATCH (copy_character:Character {id: character_pair.copy_id})
                MERGE (copy_event)-[relationship:INVOLVES]->(copy_character)
                SET relationship.involvement = source_relationship.involvement
                """,
                parameters_={
                    "event_pairs": event_pairs,
                    "character_pairs": character_pairs,
                },
            )

        return (
            [
                self.event_from_node(record["event"])
                for record in result.records
            ],
            event_pairs,
        )
