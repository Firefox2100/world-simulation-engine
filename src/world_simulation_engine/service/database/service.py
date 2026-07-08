from neo4j import AsyncDriver

from .character_store import CharacterStore
from .config_store import ConfigStore
from .equipment_store import EquipmentStore
from .item_store import ItemStore
from .location_store import LocationStore
from .simulation_store import SimulationStore
from .world_store import WorldStore


class DatabaseService:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

        self._character = CharacterStore(self._driver)
        self._config = ConfigStore(self._driver)
        self._equipment = EquipmentStore(self._driver)
        self._item = ItemStore(self._driver)
        self._location = LocationStore(self._driver)
        self._simulation = SimulationStore(self._driver)
        self._world = WorldStore(self._driver)

    @property
    def character(self) -> CharacterStore:
        return self._character

    @property
    def config(self) -> ConfigStore:
        return self._config

    @property
    def equipment(self) -> EquipmentStore:
        return self._equipment

    @property
    def item(self) -> ItemStore:
        return self._item

    @property
    def location(self) -> LocationStore:
        return self._location

    @property
    def simulation(self) -> SimulationStore:
        return self._simulation

    @property
    def world(self) -> WorldStore:
        return self._world
