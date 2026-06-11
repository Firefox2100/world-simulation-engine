from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Simulation, SimulationState
from .tables import SimulationOrm, SimulationStateOrm


class SimulationRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: SimulationOrm) -> Simulation:
        payload = {
            column.name: getattr(record, column.name)
            for column in SimulationOrm.__table__.columns
            if column.name != "world_id"
        }
        return Simulation.model_validate(payload)

    async def get(self, simulation_id: int) -> Simulation | None:
        """
        Retrieve a simulation by its ID.
        :param simulation_id: The ID of the simulation to retrieve.
        :return: The simulation with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            simulation = await session.get(SimulationOrm, simulation_id)

            if not simulation:
                return None

            return self._to_model(simulation)

    async def list(self) -> list[Simulation]:
        """
        List all simulations.
        :return: A list of simulations
        """
        async with self._session_factory() as session:
            simulations = await session.scalars(select(SimulationOrm))

            return [self._to_model(simulation) for simulation in simulations]

    async def create(self,
                     simulation: Simulation,
                     world_id: int | None = None,
                     ) -> Simulation:
        """
        Create a simulation in the database.
        :param simulation: The simulation to create.
        :param world_id: The ID of the world configuration that this simulation is generated from. Can be None
        """
        payload = simulation.model_dump(mode="json", exclude={"id"})

        async with self._session_factory() as session:
            new_simulation = SimulationOrm(world_id=world_id, **payload)
            session.add(new_simulation)

            await session.commit()
            return self._to_model(new_simulation)

    async def update(self, simulation: Simulation) -> None:
        """
        Update an existing simulation.
        :param simulation: The new simulation data.
        """
        payload = simulation.model_dump(mode="json")

        async with self._session_factory() as session:
            await session.merge(SimulationOrm(**payload))

            await session.commit()

    async def delete(self, simulation_id: int) -> None:
        """
        Delete an existing simulation
        :param simulation_id: The simulation ID to delete
        """
        async with self._session_factory() as session:
            simulation = await session.get(SimulationOrm, simulation_id)

            if simulation:
                await session.delete(simulation)
                await session.commit()


class SimulationStateRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: SimulationStateOrm) -> SimulationState:
        payload = {column.name: getattr(record, column.name) for column in SimulationStateOrm.__table__.columns}
        payload["scene"] = payload.pop("location_id")
        return SimulationState.model_validate(payload)

    async def get(self, simulation_id: int) -> SimulationState | None:
        """
        Retrieve the state of a simulation by its ID.
        :param simulation_id: The ID of the simulation whose state to retrieve.
        :return: The state of the simulation with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            state = await session.get(SimulationStateOrm, simulation_id)

            if not state:
                return None

            return self._to_model(state)

    async def create(self, state: SimulationState) -> SimulationState:
        payload = state.model_dump(mode="json")
        payload["location_id"] = payload.pop("scene")
        new_state = SimulationStateOrm(**payload)

        async with self._session_factory() as session:
            session.add(new_state)

            await session.commit()

            return self._to_model(new_state)
