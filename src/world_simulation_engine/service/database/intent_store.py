from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import IntentStatus
from world_simulation_engine.model import Intent

if TYPE_CHECKING:
    from world_simulation_engine.service.embed_service import EmbedService


class IntentStore:
    def __init__(self,
                 driver: AsyncDriver,
                 embed_service: "EmbedService | None" = None,
                 ):
        self._driver = driver
        self._embed_service = embed_service

    async def _with_keyword_embedding(self, intent: Intent) -> Intent:
        if intent.embedding is not None or not intent.keywords or self._embed_service is None:
            return intent

        embedding = await self._embed_service.embed_keywords(intent.keywords)
        return intent.model_copy(update={"embedding": embedding})

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
                            ) -> Intent | None:
        intent = await self._with_keyword_embedding(intent)

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
            return None

        return intent

    async def list_intents(self,
                           character_id: str | None = None,
                           event_id: str | None = None,
                           ) -> list[Intent]:
        if character_id is not None and event_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Character {id: $character_id})-[:HOLDS]->(intent:Intent)
                MATCH (:Event {id: $event_id})-[:CREATES|CONTRIBUTES_TO]->(intent)
                RETURN DISTINCT intent
                ORDER BY intent.name
                """,
                parameters_={
                    "character_id": character_id,
                    "event_id": event_id,
                },
            )
        elif character_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Character {id: $character_id})-[:HOLDS]->(intent:Intent)
                RETURN intent
                ORDER BY intent.name
                """,
                parameters_={"character_id": character_id},
            )
        elif event_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Event {id: $event_id})-[:CREATES|CONTRIBUTES_TO]->(intent:Intent)
                RETURN DISTINCT intent
                ORDER BY intent.name
                """,
                parameters_={"event_id": event_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (intent:Intent)
                RETURN intent
                ORDER BY intent.name
                """
            )

        return [
            self.intent_from_node(record["intent"])
            for record in result.records
        ]

    async def get_intent(self, intent_id: str) -> Intent | None:
        result = await self._driver.execute_query(
            """
            MATCH (intent:Intent {id: $intent_id})
            RETURN intent LIMIT 1
            """,
            parameters_={"intent_id": intent_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.intent_from_node(record["intent"])

    async def add_event_contribution(self,
                                     event_id: str,
                                     intent_id: str,
                                     ) -> Intent | None:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (intent:Intent {id: $intent_id})
            MERGE (event)-[:CONTRIBUTES_TO]->(intent)
            RETURN intent
            """,
            parameters_={
                "event_id": event_id,
                "intent_id": intent_id,
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.intent_from_node(record["intent"])

    async def add_event_creation(self,
                                 event_id: str,
                                 intent_id: str,
                                 ) -> Intent | None:
        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (intent:Intent {id: $intent_id})
            MERGE (event)-[:CREATES]->(intent)
            RETURN intent
            """,
            parameters_={
                "event_id": event_id,
                "intent_id": intent_id,
            },
        )
        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.intent_from_node(record["intent"])

    async def update_intent(self,
                            *,
                            intent_id: str,
                            properties: dict,
                            ) -> Intent | None:
        if (
            properties.get("embedding") is None
            and properties.get("keywords")
            and self._embed_service is not None
        ):
            properties = {
                **properties,
                "embedding": await self._embed_service.embed_keywords(properties["keywords"]),
            }

        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }
        if not properties:
            return None

        result = await self._driver.execute_query(
            """
            MATCH (intent:Intent {id: $intent_id})
            SET intent += $properties
            RETURN intent LIMIT 1
            """,
            parameters_={
                "intent_id": intent_id,
                "properties": properties,
            },
        )
        records = getattr(result, "records", None)
        if not isinstance(records, list):
            return None
        record = records[0] if records else None
        if not record:
            return None

        return self.intent_from_node(record["intent"])

    async def delete_intent(self, intent_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (intent:Intent {id: $intent_id})
            WITH collect(intent) AS intents
            FOREACH (intent IN intents | DETACH DELETE intent)
            RETURN size(intents) AS deleted
            """,
            parameters_={"intent_id": intent_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def copy_intents(self,
                           character_pairs: list[dict],
                           event_pairs: list[dict] | None = None,
                           ) -> tuple[list[Intent], list[dict]]:
        event_pairs = event_pairs or []
        if not character_pairs:
            return [], []

        result = await self._driver.execute_query(
            """
            UNWIND $character_pairs AS character_pair
            MATCH (:Character {id: character_pair.source_id})-[:HOLDS]->(source_intent:Intent)
            MATCH (copy_character:Character {id: character_pair.copy_id})
            CREATE (intent:Intent {
                id: randomUUID(),
                type: source_intent.type,
                name: source_intent.name,
                description: source_intent.description,
                keywords: source_intent.keywords,
                embedding: source_intent.embedding,
                priority: source_intent.priority,
                urgency: source_intent.urgency,
                status: source_intent.status,
                desired_state: source_intent.desired_state,
                success_conditions: source_intent.success_conditions,
                failure_conditions: source_intent.failure_conditions,
                maintenance_conditions: source_intent.maintenance_conditions,
                deadline: source_intent.deadline,
                horizon: source_intent.horizon,
                constraints: source_intent.constraints,
                current_plan: source_intent.current_plan,
                next_action_biases: source_intent.next_action_biases,
                blockers: source_intent.blockers,
                open_threads: source_intent.open_threads
            })
            MERGE (copy_character)-[:HOLDS]->(intent)
            RETURN source_intent.id AS source_id, intent.id AS copy_id, intent
            ORDER BY intent.name
            """,
            parameters_={"character_pairs": character_pairs},
        )
        intent_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if intent_pairs and event_pairs:
            await self._driver.execute_query(
                """
                UNWIND $intent_pairs AS intent_pair
                MATCH (source_event:Event)-[:CREATES]->(:Intent {id: intent_pair.source_id})
                WITH intent_pair, [
                    event_pair IN $event_pairs
                    WHERE event_pair.source_id = source_event.id
                ][0] AS event_pair
                WHERE event_pair IS NOT NULL
                MATCH (copy_event:Event {id: event_pair.copy_id})
                MATCH (copy_intent:Intent {id: intent_pair.copy_id})
                MERGE (copy_event)-[:CREATES]->(copy_intent)
                """,
                parameters_={
                    "intent_pairs": intent_pairs,
                    "event_pairs": event_pairs,
                },
            )
            await self._driver.execute_query(
                """
                UNWIND $intent_pairs AS intent_pair
                MATCH (source_event:Event)-[:CONTRIBUTES_TO]->(:Intent {id: intent_pair.source_id})
                WITH intent_pair, [
                    event_pair IN $event_pairs
                    WHERE event_pair.source_id = source_event.id
                ][0] AS event_pair
                WHERE event_pair IS NOT NULL
                MATCH (copy_event:Event {id: event_pair.copy_id})
                MATCH (copy_intent:Intent {id: intent_pair.copy_id})
                MERGE (copy_event)-[:CONTRIBUTES_TO]->(copy_intent)
                """,
                parameters_={
                    "intent_pairs": intent_pairs,
                    "event_pairs": event_pairs,
                },
            )

        return (
            [
                self.intent_from_node(record["intent"])
                for record in result.records
            ],
            intent_pairs,
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
