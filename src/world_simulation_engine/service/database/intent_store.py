from datetime import datetime, timedelta

from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import IntentStatus
from world_simulation_engine.model import Intent


class IntentStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    @staticmethod
    def intent_from_node(intent_node) -> Intent:
        deadline = intent_node.get("deadline")
        if hasattr(deadline, "to_native"):
            deadline = deadline.to_native()

        return Intent(
            id=intent_node["id"],
            type=intent_node["type"],
            name=intent_node["name"],
            description=intent_node["description"],
            keywords=list(intent_node.get("keywords") or []),
            embedding=list(intent_node["embedding"]) if intent_node.get("embedding") is not None else None,
            priority=intent_node["priority"],
            urgency=intent_node["urgency"],
            status=intent_node["status"],
            desired_state=intent_node.get("desired_state"),
            success_conditions=list(intent_node.get("success_conditions") or []),
            failure_conditions=list(intent_node.get("failure_conditions") or []),
            maintenance_conditions=list(intent_node.get("maintenance_conditions") or []),
            deadline=deadline,
            horizon=intent_node["horizon"],
            constraints=list(intent_node.get("constraints") or []),
            current_plan=list(intent_node.get("current_plan") or []),
            next_action_biases=list(intent_node.get("next_action_biases") or []),
            blockers=list(intent_node.get("blockers") or []),
            open_threads=list(intent_node.get("open_threads") or []),
        )

    async def create_intent(self,
                            intent: Intent,
                            character_id: str,
                            ):
        result = await self._driver.execute_query(
            """
            MATCH (character:Character {id: $character_id})
            CREATE (intent:Intent {
                id: $id,
                type: $type,
                name: $name,
                description: $description,
                keywords: $keywords,
                embedding: $embedding,
                priority: $priority,
                urgency: $urgency,
                status: $status,
                desired_state: $desired_state,
                success_conditions: $success_conditions,
                failure_conditions: $failure_conditions,
                maintenance_conditions: $maintenance_conditions,
                deadline: $deadline,
                horizon: $horizon,
                constraints: $constraints,
                current_plan: $current_plan,
                next_action_biases: $next_action_biases,
                blockers: $blockers,
                open_threads: $open_threads
            })
            MERGE (character)-[:HOLDS]->(intent)
            RETURN intent
            """,
            parameters_={
                "character_id": character_id,
                "id": intent.id,
                "type": intent.type,
                "name": intent.name,
                "description": intent.description,
                "keywords": intent.keywords,
                "embedding": intent.embedding,
                "priority": intent.priority,
                "urgency": intent.urgency,
                "status": intent.status,
                "desired_state": intent.desired_state,
                "success_conditions": intent.success_conditions,
                "failure_conditions": intent.failure_conditions,
                "maintenance_conditions": intent.maintenance_conditions,
                "deadline": intent.deadline,
                "horizon": intent.horizon,
                "constraints": intent.constraints,
                "current_plan": intent.current_plan,
                "next_action_biases": intent.next_action_biases,
                "blockers": intent.blockers,
                "open_threads": intent.open_threads,
            },
        )
        if not result.records:
            raise ValueError(f"Could not create intent because character {character_id} was not found")

    async def add_event_contribution(self,
                                     event_id: str,
                                     intent_id: str,
                                     ):
        await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (intent:Intent {id: $intent_id})
            MERGE (event)-[:CONTRIBUTES_TO]->(intent)
            """,
            parameters_={
                "event_id": event_id,
                "intent_id": intent_id,
            },
        )

    async def add_event_creation(self,
                                 event_id: str,
                                 intent_id: str,
                                 ):
        await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (intent:Intent {id: $intent_id})
            MERGE (event)-[:CREATES]->(intent)
            """,
            parameters_={
                "event_id": event_id,
                "intent_id": intent_id,
            },
        )

    async def update_intent(self,
                            *,
                            intent_id: str,
                            properties: dict,
                            ):
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }
        if not properties:
            return

        await self._driver.execute_query(
            """
            MATCH (intent:Intent {id: $intent_id})
            SET intent += $properties
            """,
            parameters_={
                "intent_id": intent_id,
                "properties": properties,
            },
        )

    async def get_active_intent_candidates(self,
                                           character_id: str,
                                           current_time: datetime,
                                           deadline_delta: timedelta,
                                           priority_threshold: float,
                                           urgency_threshold: float,
                                           ) -> list[Intent]:
        result = await self._driver.execute_query(
            """
            MATCH (:Character {id: $character_id})-[:HOLDS]->(intent:Intent)
            WHERE intent.status IN $statuses
              AND (
                (
                    intent.deadline IS NOT NULL
                    AND intent.deadline >= $current_time
                    AND intent.deadline <= $deadline_cutoff
                )
                OR intent.priority >= $priority_threshold
                OR intent.urgency >= $urgency_threshold
              )
            RETURN intent
            ORDER BY intent.urgency DESC, intent.priority DESC, intent.deadline ASC
            """,
            parameters_={
                "character_id": character_id,
                "statuses": [IntentStatus.ACTIVE, IntentStatus.PAUSED],
                "current_time": current_time,
                "deadline_cutoff": current_time + deadline_delta,
                "priority_threshold": priority_threshold,
                "urgency_threshold": urgency_threshold,
            },
        )

        return [
            self.intent_from_node(record["intent"])
            for record in result.records
        ]

    async def get_character_intents(self,
                                    character_id: str,
                                    ) -> list[Intent]:
        result = await self._driver.execute_query(
            """
            MATCH (:Character {id: $character_id})-[:HOLDS]->(intent:Intent)
            RETURN intent
            """,
            parameters_={
                "character_id": character_id,
            },
        )

        return [
            self.intent_from_node(record["intent"])
            for record in result.records
        ]
