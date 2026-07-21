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
            MATCH (character:Character)
            WHERE character.id IN $character_ids
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
                    MATCH (:Character {id: $character_id})-[:REMEMBERS]->(memory)
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

    async def get_recent_turn_memory_candidates(self,
                                                character_id: str,
                                                source_id: str,
                                                turn_limit: int = 5,
                                                ) -> list[MemoryRecallRecord]:
        result = await self._driver.execute_query(
            """
            MATCH (:World|Simulation {id: $source_id})-[:CONTAINS]->(recent_turn:Turn)
            WITH recent_turn
            ORDER BY recent_turn.sequence DESC
            LIMIT $turn_limit
            MATCH (recent_turn)-[:PART_OF]->(event:Event)-[support:SUPPORTS]->(memory:MemoryAtom)
            MATCH (:Character {id: $character_id})-[remembers:REMEMBERS]->(memory)
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
