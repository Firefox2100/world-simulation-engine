from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import EventInvolvement
from world_simulation_engine.model import Event


class EventStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_event(self,
                           event: Event,
                           turn_ids: list[str],
                           ):
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
            raise ValueError("Could not create event because one or more turns were not found")

    async def add_turn_to_event(self,
                                event_id: str,
                                turn_id: str,
                                ):
        await self._driver.execute_query(
            """
            MATCH (turn:Turn {id: $turn_id})
            MATCH (event:Event {id: $event_id})
            MERGE (turn)-[:PART_OF]->(event)
            """,
            parameters_={
                "event_id": event_id,
                "turn_id": turn_id,
            },
        )

    async def add_character_involvement(self,
                                        event_id: str,
                                        character_id: str,
                                        involvement: EventInvolvement,
                                        ):
        await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (character:Character {id: $character_id})
            MERGE (event)-[relationship:INVOLVES]->(character)
            SET relationship.involvement = $involvement
            """,
            parameters_={
                "event_id": event_id,
                "character_id": character_id,
                "involvement": involvement,
            },
        )
