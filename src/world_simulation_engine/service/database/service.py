from neo4j import AsyncDriver

from world_simulation_engine.model import Character, Location, Landmark
from .character_store import CharacterStore
from .config_store import ConfigStore
from .container_store import ContainerStore
from .equipment_store import EquipmentStore
from .event_store import EventStore
from .intent_store import IntentStore
from .item_store import ItemStore
from .location_store import LocationStore
from .memory_store import MemoryStore
from .simulation_store import SimulationStore
from .turn_store import TurnStore
from .world_store import WorldStore


class DatabaseService:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

        self._character = CharacterStore(self._driver)
        self._config = ConfigStore(self._driver)
        self._container = ContainerStore(self._driver)
        self._equipment = EquipmentStore(self._driver)
        self._event = EventStore(self._driver)
        self._intent = IntentStore(self._driver)
        self._item = ItemStore(self._driver)
        self._location = LocationStore(self._driver)
        self._memory = MemoryStore(self._driver)
        self._simulation = SimulationStore(self._driver)
        self._turn = TurnStore(self._driver)
        self._world = WorldStore(self._driver)

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
    def event(self) -> EventStore:
        return self._event

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
    def simulation(self) -> SimulationStore:
        return self._simulation

    @property
    def turn(self) -> TurnStore:
        return self._turn

    @property
    def world(self) -> WorldStore:
        return self._world

    async def get_characters_in_location(self,
                                         root_location_id: str,
                                         ) -> list[tuple[Character, Location, str | None, Landmark | None]]:
        result = await self._driver.execute_query(
            """
            MATCH (root:Location {id: $root_id})
            MATCH path = (root) -[:CONTAINS*0..]-> (loc:Location)
            MATCH (c:Character) -[r:PRESENT_IN]-> (loc)
            OPTIONAL MATCH (c) -[:ANCHORED_TO]-> (lm:Landmark)
            WHERE (loc) -[:CONTAINS]-> (lm)
            
            RETURN c as character, loc as location, r.position as position, lm as landmark
            ORDER BY character.name
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
