from neo4j import AsyncDriver

from .simulation_store import SimulationStore
from .world_store import WorldStore


class DatabaseService:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

        self._simulation = SimulationStore(self._driver)
        self._world = WorldStore(self._driver)

    @property
    def simulation(self) -> SimulationStore:
        return self._simulation

    @property
    def world(self) -> WorldStore:
        return self._world
