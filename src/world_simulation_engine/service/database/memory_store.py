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
            embedding=list(memory_node["embedding"]),
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
                                 ):
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

    async def add_character_memory(self,
                                   memory_id: str,
                                   character_link: CharacterMemoryLink,
                                   ):
        await self._driver.execute_query(
            """
            MATCH (memory:MemoryAtom {id: $memory_id})
            MATCH (character:Character {id: $character_id})
            MERGE (character)-[remembers:REMEMBERS]->(memory)
            SET remembers.confidence = $confidence,
                remembers.salience = $salience,
                remembers.behavioural_relevance = $behavioural_relevance,
                remembers.stance = $stance
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
