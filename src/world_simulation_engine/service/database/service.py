from neo4j import AsyncDriver
from typing import TYPE_CHECKING

from world_simulation_engine.model import Character, Location, Landmark
from .character_store import CharacterStore
from .config_store import ConfigStore
from .container_store import ContainerStore
from .equipment_store import EquipmentStore
from .emotion_store import EmotionStore
from .entity_relationship_store import EntityRelationshipStore
from .subjective_entity_claim_store import SubjectiveEntityClaimStore
from .event_store import EventStore
from .graph_state_snapshot_store import GraphStateSnapshotStore
from .generation_job_store import GenerationJobStore
from .intent_store import IntentStore
from .item_store import ItemStore
from .location_store import LocationStore
from .memory_store import MemoryStore
from .memory_summary_store import MemorySummaryStore
from .media_store import MediaStore
from .simulation_store import SimulationStore
from .state_commit_store import StateCommitStore
from .turn_store import TurnStore
from .turn_presentation_store import TurnPresentationStore
from .world_store import WorldStore

if TYPE_CHECKING:
    from world_simulation_engine.service.embed_service import EmbedService


class DatabaseService:
    def __init__(self,
                 driver: AsyncDriver,
                 embed_service: "EmbedService | None" = None,
                 ):
        self._driver = driver

        self._character = CharacterStore(self._driver)
        self._config = ConfigStore(self._driver)
        self._container = ContainerStore(self._driver)
        self._equipment = EquipmentStore(self._driver)
        self._emotion = EmotionStore(self._driver)
        self._entity_relationship = EntityRelationshipStore(self._driver)
        self._subjective_entity_claim = SubjectiveEntityClaimStore(self._driver)
        self._event = EventStore(self._driver)
        self._graph_state_snapshot = GraphStateSnapshotStore(self._driver)
        self._generation_job = GenerationJobStore(self._driver)
        self._intent = IntentStore(self._driver, embed_service=embed_service)
        self._item = ItemStore(self._driver)
        self._location = LocationStore(self._driver)
        self._memory = MemoryStore(self._driver, embed_service=embed_service)
        self._memory_summary = MemorySummaryStore(
            event_store=self._event,
            memory_store=self._memory,
            intent_store=self._intent,
        )
        self._media = MediaStore(self._driver)
        self._simulation = SimulationStore(self._driver)
        self._state_commit = StateCommitStore(self._driver)
        self._turn = TurnStore(self._driver)
        self._turn_presentation = TurnPresentationStore(self._driver)
        self._world = WorldStore(self._driver)

    async def close(self):
        await self._driver.close()

    @property
    def character(self) -> CharacterStore:
        return self._character

    @property
    def config(self) -> ConfigStore:
        return self._config

    @property
    def container(self) -> ContainerStore:
        return self._container

    @property
    def equipment(self) -> EquipmentStore:
        return self._equipment

    @property
    def emotion(self) -> EmotionStore:
        return self._emotion

    @property
    def entity_relationship(self) -> EntityRelationshipStore:
        return self._entity_relationship

    @property
    def subjective_entity_claim(self) -> SubjectiveEntityClaimStore:
        return self._subjective_entity_claim

    @property
    def event(self) -> EventStore:
        return self._event

    @property
    def graph_state_snapshot(self) -> GraphStateSnapshotStore:
        return self._graph_state_snapshot

    @property
    def generation_job(self) -> GenerationJobStore:
        return self._generation_job

    @property
    def intent(self) -> IntentStore:
        return self._intent

    @property
    def item(self) -> ItemStore:
        return self._item

    @property
    def location(self) -> LocationStore:
        return self._location

    @property
    def memory(self) -> MemoryStore:
        return self._memory

    @property
    def memory_summary(self) -> MemorySummaryStore:
        return self._memory_summary

    @property
    def media(self) -> MediaStore:
        return self._media

    @property
    def simulation(self) -> SimulationStore:
        return self._simulation

    @property
    def state_commit(self) -> StateCommitStore:
        return self._state_commit

    @property
    def turn(self) -> TurnStore:
        return self._turn

    @property
    def turn_presentation(self) -> TurnPresentationStore:
        return self._turn_presentation

    @property
    def world(self) -> WorldStore:
        return self._world

    async def get_characters_in_location(self,
                                         root_location_id: str,
                                         ) -> list[tuple[Character, Location, str | None, Landmark | None]]:
        result = await self._driver.execute_query(
            """
            MATCH (root:Location {id: $root_id})
            MATCH (root) -[:CONTAINS*0..]-> (loc:Location)
            MATCH (c:Character) -[r:PRESENT_IN]-> (loc)
            OPTIONAL MATCH (c) -[:ANCHORED_TO]-> (lm:Landmark)<-[:CONTAINS]-(loc)
            
            RETURN c as character, loc as location, r.position as position, lm as landmark
            ORDER BY character.name, character.id
            """,
            parameters_={"root_id": root_location_id},
        )

        entries = []
        for record in result.records:
            character = self.character.character_from_node(record["character"])
            location = self.location.location_from_node(record["location"])
            if record.get("landmark"):
                landmark = self.location.landmark_from_node(record["landmark"])
            else:
                landmark = None

            entries.append((character, location, record["position"], landmark))

        return entries

    async def get_characters_perceivable_by(
            self,
            observer_id: str,
    ) -> list[tuple[Character, Location, str | None, Landmark | None]]:
        """Return spatial perception candidates using the resolver's location rule."""
        result = await self._driver.execute_query(
            """
            MATCH (observer:Character {id: $observer_id})-[:PRESENT_IN]->(observer_location:Location)
            MATCH (observer_location)-[:CONTAINS*0..]->(location:Location)
            MATCH (character:Character)-[present:PRESENT_IN]->(location)
            WHERE character.id <> observer.id
            OPTIONAL MATCH (character)-[:ANCHORED_TO]->(landmark:Landmark)<-[:CONTAINS]-(location)
            RETURN DISTINCT character, location, present.position AS position, landmark
            ORDER BY character.name, character.id
            """,
            parameters_={"observer_id": observer_id},
        )
        return [
            (
                self.character.character_from_node(record["character"]),
                self.location.location_from_node(record["location"]),
                record["position"],
                self.location.landmark_from_node(record["landmark"])
                if record.get("landmark") else None,
            )
            for record in result.records
        ]

    async def get_characters_that_can_perceive_characters(
            self,
            *,
            simulation_id: str,
            character_ids: list[str],
    ) -> list[Character]:
        """Return simulation characters whose location scope contains any subject location."""
        if not character_ids:
            return []

        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})-[:CONTAINS]->(observer:Character)
            MATCH (observer)-[:PRESENT_IN]->(observer_location:Location)
            MATCH (simulation)-[:CONTAINS]->(subject:Character)-[:PRESENT_IN]->(subject_location:Location)
            WHERE subject.id IN $character_ids
                AND EXISTS {
                    MATCH (observer_location)-[:CONTAINS*0..]->(subject_location)
                }
            RETURN DISTINCT observer
            ORDER BY observer.name, observer.id
            """,
            parameters_={
                "simulation_id": simulation_id,
                "character_ids": list(dict.fromkeys(character_ids)),
            },
        )
        return [
            self.character.character_from_node(record["observer"])
            for record in result.records
        ]
