from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience
from world_simulation_engine.model import Event, MemoryAtom

if TYPE_CHECKING:
    from world_simulation_engine.service.embed_service import EmbedService


class CharacterMemoryLink(BaseModel):
    character_id: str
    confidence: float = Field(ge=0, le=1)
    salience: Salience
    behavioural_relevance: str | None = None
    stance: MemoryStance


class MemoryRecallRecord(BaseModel):
    memory: MemoryAtom
    event: Event
    event_ending_time: datetime
    support_type: MemorySupportType
    confidence: float
    salience: Salience
    behavioural_relevance: str | None = None
    stance: MemoryStance
    recall_channels: list[str] = Field(default_factory=list)


class MemoryStore:
    def __init__(self,
                 driver: AsyncDriver,
                 embed_service: "EmbedService | None" = None,
                 ):
        self._driver = driver
        self._embed_service = embed_service

    async def _with_keyword_embedding(self, memory: MemoryAtom) -> MemoryAtom:
        if memory.embedding is not None or not memory.keywords or self._embed_service is None:
            return memory

        embedding = await self._embed_service.embed_keywords(memory.keywords)
        return memory.model_copy(update={"embedding": embedding})

    @staticmethod
    def memory_from_node(memory_node) -> MemoryAtom:
        return MemoryAtom(
            id=memory_node["id"],
            summary=memory_node["summary"],
            keywords=list(memory_node["keywords"]),
            embedding=list(memory_node["embedding"]) if memory_node.get("embedding") is not None else None,
        )

    @staticmethod
    def event_from_node(event_node) -> Event:
        return Event(
            id=event_node["id"],
            name=event_node["name"],
            summary=event_node["summary"],
            outcome=event_node.get("outcome"),
        )

    @staticmethod
    def recall_record_from_record(record) -> MemoryRecallRecord:
        event_ending_time = record["event_ending_time"]
        if hasattr(event_ending_time, "to_native"):
            event_ending_time = event_ending_time.to_native()

        return MemoryRecallRecord(
            memory=MemoryStore.memory_from_node(record["memory"]),
            event=MemoryStore.event_from_node(record["event"]),
            event_ending_time=event_ending_time,
            support_type=record["support_type"],
            confidence=record["confidence"],
            salience=record["salience"],
            behavioural_relevance=record.get("behavioural_relevance"),
            stance=record["stance"],
            recall_channels=list(record.get("recall_channels") or []),
        )

    async def create_memory_atom(self,
                                 memory: MemoryAtom,
                                 event_id: str,
                                 support_type: MemorySupportType,
                                 character_links: list[CharacterMemoryLink],
                                 ) -> MemoryAtom:
        if not character_links:
            raise ValueError("A memory atom must be attached to at least one character")

        memory = await self._with_keyword_embedding(memory)

        character_ids = [
            link.character_id
            for link in character_links
        ]

        result = await self._driver.execute_query(
            """
            MATCH (event:Event {id: $event_id})
            MATCH (character)
            WHERE character.id IN $character_ids AND (character:Character OR character:BackgroundCharacter)
            WITH event, collect(character) AS characters
            WHERE size(characters) = size($character_ids)
            CREATE (memory:MemoryAtom {
                id: $id,
                summary: $summary,
                keywords: $keywords,
                embedding: $embedding
            })
            MERGE (event)-[support:SUPPORTS]->(memory)
            SET support.type = $support_type
            WITH memory, characters
            UNWIND $character_links AS character_link
            UNWIND characters AS character
            WITH memory, character_link, character
            WHERE character.id = character_link.character_id
            MERGE (character)-[remembers:REMEMBERS]->(memory)
            SET remembers.confidence = character_link.confidence,
                remembers.salience = character_link.salience,
                remembers.behavioural_relevance = character_link.behavioural_relevance,
                remembers.stance = character_link.stance
            RETURN memory
            """,
            parameters_={
                "event_id": event_id,
                "support_type": support_type,
                "id": memory.id,
                "summary": memory.summary,
                "keywords": memory.keywords,
                "embedding": memory.embedding,
                "character_ids": character_ids,
                "character_links": [
                    link.model_dump(mode="json")
                    for link in character_links
                ],
            },
        )
        if not result.records:
            raise ValueError("Could not create memory atom because the event or one or more characters were not found")

        created_memory = result.records[0]["memory"]
        if not created_memory:
            return memory

        return self.memory_from_node(created_memory)

    async def list_memories(self,
                            character_id: str | None = None,
                            event_id: str | None = None,
                            simulation_id: str | None = None,
                            ) -> list[MemoryAtom]:
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom)
            WHERE ($character_id IS NULL OR EXISTS {
                    MATCH (holder {id: $character_id})-[:REMEMBERS]->(memory)
                    WHERE holder:Character OR holder:BackgroundCharacter
                })
                AND ($event_id IS NULL OR EXISTS {
                    MATCH (:Event {id: $event_id})-[:SUPPORTS]->(memory)
                })
                AND ($simulation_id IS NULL OR EXISTS {
                    MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(:Turn)-[:PART_OF]->(:Event)-[:SUPPORTS]->(memory)
                })
            RETURN DISTINCT memory
            ORDER BY memory.summary
            """,
            parameters_={
                "character_id": character_id,
                "event_id": event_id,
                "simulation_id": simulation_id,
            },
        )

        return [
            self.memory_from_node(record["memory"])
            for record in result.records
        ]

    async def get_memory(self, memory_id: str) -> MemoryAtom | None:
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            RETURN memory LIMIT 1
            """,
            parameters_={"memory_id": memory_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.memory_from_node(record["memory"])

    async def get_event_links(self, memory_ids: list[str]) -> dict[str, dict]:
        """MemoryAtom doesn't carry its supporting event as a field - it's the SUPPORTS
        relationship - so exporting it needs this dedicated batched lookup."""
        if not memory_ids:
            return {}

        result = await self._driver.execute_query(
            """
            UNWIND $memory_ids AS memory_id
            MATCH (event:Event)-[support:SUPPORTS]->(:MemoryAtom {id: memory_id})
            RETURN memory_id, event.id AS event_id, support.type AS support_type
            """,
            parameters_={"memory_ids": memory_ids},
        )

        return {
            record["memory_id"]: {
                "event_id": record["event_id"],
                "support_type": record["support_type"],
            }
            for record in result.records
        }

    async def get_character_links(self, memory_ids: list[str]) -> dict[str, list[dict]]:
        """Same rationale as get_event_links, for the REMEMBERS relationship."""
        if not memory_ids:
            return {}

        result = await self._driver.execute_query(
            """
            UNWIND $memory_ids AS memory_id
            MATCH (character:Character)-[remembers:REMEMBERS]->(:MemoryAtom {id: memory_id})
            RETURN memory_id, collect({
                character_id: character.id,
                confidence: remembers.confidence,
                salience: remembers.salience,
                behavioural_relevance: remembers.behavioural_relevance,
                stance: remembers.stance
            }) AS character_links
            """,
            parameters_={"memory_ids": memory_ids},
        )

        return {
            record["memory_id"]: record["character_links"]
            for record in result.records
        }

    async def update_memory(self,
                            memory_id: str,
                            properties: dict,
                            ) -> MemoryAtom | None:
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
            return await self.get_memory(memory_id)

        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            SET memory += $properties
            RETURN memory LIMIT 1
            """,
            parameters_={
                "memory_id": memory_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.memory_from_node(record["memory"])

    async def update_embeddings(self, rows: list[dict]) -> int:
        """Cache lazily generated semantic vectors without changing memory meaning."""
        if not rows:
            return 0
        result = await self._driver.execute_query(
            """
            UNWIND $rows AS row
            MATCH (memory:MemoryAtom {id: row.memory_id})
            WHERE memory.embedding IS NULL
            SET memory.embedding = row.embedding
            RETURN count(memory) AS updated
            """,
            parameters_={"rows": rows},
        )
        return result.records[0]["updated"] if result.records else 0

    async def delete_memory(self, memory_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            WITH collect(memory) AS memories
            FOREACH (memory IN memories | DETACH DELETE memory)
            RETURN size(memories) AS deleted
            """,
            parameters_={"memory_id": memory_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def link_memory_event(self,
                                memory_id: str,
                                event_id: str,
                                support_type: MemorySupportType,
                                ) -> MemoryAtom | None:
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            MATCH (event:Event {id: $event_id})
            OPTIONAL MATCH (:Event)-[existing:SUPPORTS]->(memory)
            DELETE existing
            MERGE (event)-[support:SUPPORTS]->(memory)
            SET support.type = $support_type
            RETURN memory LIMIT 1
            """,
            parameters_={
                "memory_id": memory_id,
                "event_id": event_id,
                "support_type": support_type,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.memory_from_node(record["memory"])

    async def replace_character_memories(self,
                                         memory_id: str,
                                         character_links: list[CharacterMemoryLink],
                                         ) -> MemoryAtom | None:
        if not character_links:
            raise ValueError("A memory atom must be attached to at least one character")
        character_ids = [
            link.character_id
            for link in character_links
        ]
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            MATCH (character:Character)
            WHERE character.id IN $character_ids
            WITH memory, collect(character) AS characters
            WHERE size(characters) = size($character_ids)
            OPTIONAL MATCH (:Character)-[existing:REMEMBERS]->(memory)
            DELETE existing
            WITH memory, characters
            UNWIND $character_links AS character_link
            UNWIND characters AS character
            WITH memory, character_link, character
            WHERE character.id = character_link.character_id
            MERGE (character)-[remembers:REMEMBERS]->(memory)
            SET remembers.confidence = character_link.confidence,
                remembers.salience = character_link.salience,
                remembers.behavioural_relevance = character_link.behavioural_relevance,
                remembers.stance = character_link.stance
            RETURN DISTINCT memory
            """,
            parameters_={
                "memory_id": memory_id,
                "character_ids": character_ids,
                "character_links": [
                    link.model_dump(mode="json")
                    for link in character_links
                ],
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return self.memory_from_node(record["memory"])

    async def remove_character_memories(self,
                                        memory_id: str,
                                        character_ids: list[str],
                                        ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            OPTIONAL MATCH (existing_character:Character)-[:REMEMBERS]->(memory)
            WITH memory, count(existing_character) AS existing_count
            OPTIONAL MATCH (removed_character:Character)-[remembers:REMEMBERS]->(memory)
            WHERE removed_character.id IN $character_ids
            WITH memory, existing_count, collect(remembers) AS remembered_links
            WHERE existing_count > size(remembered_links)
            FOREACH (remembered_link IN remembered_links | DELETE remembered_link)
            RETURN count(memory) AS memory_count
            """,
            parameters_={
                "memory_id": memory_id,
                "character_ids": character_ids,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["memory_count"])

    async def add_character_memory(self,
                                   memory_id: str,
                                   character_link: CharacterMemoryLink,
                                   ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            MATCH (character:Character {id: $character_id})
            MERGE (character)-[remembers:REMEMBERS]->(memory)
            SET remembers.confidence = $confidence,
                remembers.salience = $salience,
                remembers.behavioural_relevance = $behavioural_relevance,
                remembers.stance = $stance
            RETURN memory
            """,
            parameters_={
                "memory_id": memory_id,
                "character_id": character_link.character_id,
                "confidence": character_link.confidence,
                "salience": character_link.salience,
                "behavioural_relevance": character_link.behavioural_relevance,
                "stance": character_link.stance,
            },
        )
        return bool(result.records)

    async def copy_memories(self,
                            event_pairs: list[dict],
                            character_pairs: list[dict] | None = None,
                            ) -> tuple[list[MemoryAtom], list[dict]]:
        character_pairs = character_pairs or []
        if not event_pairs:
            return [], []

        result = await self._driver.execute_query(
            """
            UNWIND $event_pairs AS event_pair
            MATCH (:Event {id: event_pair.source_id})-[source_support:SUPPORTS]->(source_memory:MemoryAtom)
            WITH DISTINCT source_memory, source_support, event_pair
            CREATE (memory:MemoryAtom {
                id: randomUUID(),
                summary: source_memory.summary,
                keywords: source_memory.keywords,
                embedding: source_memory.embedding
            })
            WITH source_memory, memory, source_support, event_pair
            MATCH (copy_event:Event {id: event_pair.copy_id})
            MERGE (copy_event)-[support:SUPPORTS]->(memory)
            SET support.type = source_support.type
            RETURN source_memory.id AS source_id, memory.id AS copy_id, memory
            """,
            parameters_={"event_pairs": event_pairs},
        )
        memory_pairs = [
            {
                "source_id": record["source_id"],
                "copy_id": record["copy_id"],
            }
            for record in result.records
        ]
        if memory_pairs and character_pairs:
            await self._driver.execute_query(
                """
                UNWIND $memory_pairs AS memory_pair
                MATCH (source_character:Character)-[source_remembers:REMEMBERS]->(:MemoryAtom {id: memory_pair.source_id})
                WITH memory_pair, source_remembers, [
                    character_pair IN $character_pairs
                    WHERE character_pair.source_id = source_character.id
                ][0] AS character_pair
                WHERE character_pair IS NOT NULL
                MATCH (copy_memory:MemoryAtom {id: memory_pair.copy_id})
                MATCH (copy_character:Character {id: character_pair.copy_id})
                MERGE (copy_character)-[remembers:REMEMBERS]->(copy_memory)
                SET remembers.confidence = source_remembers.confidence,
                    remembers.salience = source_remembers.salience,
                    remembers.behavioural_relevance = source_remembers.behavioural_relevance,
                    remembers.stance = source_remembers.stance
                """,
                parameters_={
                    "memory_pairs": memory_pairs,
                    "character_pairs": character_pairs,
                },
            )

        return (
            [
                self.memory_from_node(record["memory"])
                for record in result.records
            ],
            memory_pairs,
        )

    async def get_recent_turn_memory_candidates(self,
                                                character_id: str,
                                                source_id: str,
                                                turn_limit: int = 5,
                                                ) -> list[MemoryRecallRecord]:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})-[:CONTAINS]->(recent_turn:Turn)
            WITH source, recent_turn
            ORDER BY recent_turn.sequence DESC
            LIMIT $turn_limit
            MATCH (recent_turn)-[:PART_OF]->(event:Event)-[support:SUPPORTS]->(memory:MemoryAtom)
            MATCH (observer:Character {id: $character_id})-[remembers:REMEMBERS]->(memory)
            WHERE EXISTS { MATCH (source)-[:CONTAINS*0..]->(observer) }
            MATCH (event)<-[:PART_OF]-(event_turn:Turn)
            RETURN memory,
                   event,
                   max(event_turn.start_time) AS event_ending_time,
                   support.type AS support_type,
                   remembers.confidence AS confidence,
                   remembers.salience AS salience,
                   remembers.behavioural_relevance AS behavioural_relevance,
                   remembers.stance AS stance
            """,
            parameters_={
                "character_id": character_id,
                "source_id": source_id,
                "turn_limit": turn_limit,
            },
        )

        return [
            self.recall_record_from_record(record)
            for record in result.records
        ]

    async def get_character_memory_candidates(self,
                                              character_id: str,
                                              ) -> list[MemoryRecallRecord]:
        result = await self._driver.execute_query(
            """
            MATCH (:Character {id: $character_id})-[remembers:REMEMBERS]->(memory:MemoryAtom)
            MATCH (event:Event)-[support:SUPPORTS]->(memory)
            MATCH (event)<-[:PART_OF]-(event_turn:Turn)
            RETURN memory,
                   event,
                   max(event_turn.start_time) AS event_ending_time,
                   support.type AS support_type,
                   remembers.confidence AS confidence,
                   remembers.salience AS salience,
                   remembers.behavioural_relevance AS behavioural_relevance,
                   remembers.stance AS stance
            """,
            parameters_={
                "character_id": character_id,
            },
        )

        return [
            self.recall_record_from_record(record)
            for record in result.records
        ]

    async def get_scoped_character_memory_candidates(
            self,
            *,
            character_id: str,
            source_id: str,
            limit: int = 200,
    ) -> list[MemoryRecallRecord]:
        """Return semantic candidates only from the observer's requested world/simulation."""
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})-[:CONTAINS]->(event_turn:Turn)
                -[:PART_OF]->(event:Event)-[support:SUPPORTS]->(memory:MemoryAtom)
            MATCH (observer:Character {id: $character_id})-[remembers:REMEMBERS]->(memory)
            WHERE EXISTS { MATCH (source)-[:CONTAINS*0..]->(observer) }
            WITH memory, event, support, remembers, max(event_turn.start_time) AS event_ending_time
            RETURN memory, event, event_ending_time,
                   support.type AS support_type,
                   remembers.confidence AS confidence,
                   remembers.salience AS salience,
                   remembers.behavioural_relevance AS behavioural_relevance,
                   remembers.stance AS stance,
                   [] AS recall_channels
            ORDER BY event_ending_time DESC, memory.id
            LIMIT $limit
            """,
            parameters_={
                "character_id": character_id,
                "source_id": source_id,
                "limit": limit,
            },
        )
        return [self.recall_record_from_record(record) for record in result.records]

    async def get_graph_memory_candidates(
            self,
            *,
            character_id: str,
            source_id: str,
            entity_ids: list[str],
            limit: int = 50,
    ) -> list[MemoryRecallRecord]:
        """Expand observer-owned memories through scoped graph evidence channels."""
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})-[:CONTAINS]->(event_turn:Turn)
                -[:PART_OF]->(event:Event)-[support:SUPPORTS]->(memory:MemoryAtom)
            MATCH (observer:Character {id: $character_id})-[remembers:REMEMBERS]->(memory)
            WHERE EXISTS { MATCH (source)-[:CONTAINS*0..]->(observer) }
            WITH source, event_turn, event, support, memory, observer, remembers,
                CASE WHEN EXISTS {
                    MATCH (event)-[:INVOLVES]->(involved:Character)
                    WHERE involved.id IN $entity_ids
                } THEN ['entity_neighborhood'] ELSE [] END
                + CASE WHEN EXISTS {
                    MATCH (event)-[:CREATES|CONTRIBUTES_TO]->(intent:Intent)
                    WHERE EXISTS { MATCH (observer)-[:HOLDS]->(intent) }
                      AND intent.status IN ['active', 'paused']
                } THEN ['active_intent'] ELSE [] END
                + CASE WHEN EXISTS {
                    MATCH (memory)-[:EVIDENCE_FOR]->(relationship:EntityRelationship)
                    WHERE relationship.scope_id = $source_id
                      AND (relationship.perspective_character_id IS NULL
                           OR relationship.perspective_character_id = $character_id)
                      AND (
                          EXISTS {
                              MATCH (endpoint)-[:RELATIONSHIP_SOURCE]->(relationship)
                              WHERE endpoint.id IN $entity_ids
                          }
                          OR EXISTS {
                              MATCH (relationship)-[:RELATIONSHIP_TARGET]->(endpoint)
                              WHERE endpoint.id IN $entity_ids
                          }
                      )
                } THEN ['relationship_evidence'] ELSE [] END
                + CASE WHEN EXISTS {
                    MATCH (memory)-[:CLAIM_EVIDENCE]->(claim:SubjectiveEntityClaim)-[:ABOUT]->(subject)
                    WHERE claim.simulation_id = $source_id
                      AND claim.observer_character_id = $character_id
                      AND subject.id IN $entity_ids
                } THEN ['portrait_evidence'] ELSE [] END AS recall_channels
            WHERE size(recall_channels) > 0
            WITH memory, event, support, remembers, recall_channels,
                 max(event_turn.start_time) AS event_ending_time
            RETURN memory, event, event_ending_time,
                   support.type AS support_type,
                   remembers.confidence AS confidence,
                   remembers.salience AS salience,
                   remembers.behavioural_relevance AS behavioural_relevance,
                   remembers.stance AS stance,
                   recall_channels
            ORDER BY event_ending_time DESC, memory.id
            LIMIT $limit
            """,
            parameters_={
                "character_id": character_id,
                "source_id": source_id,
                "entity_ids": list(dict.fromkeys(entity_ids)),
                "limit": limit,
            },
        )
        return [self.recall_record_from_record(record) for record in result.records]
