from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Simulation, SimulationState, AgentPreset, DataPreset
from .tables import SimulationOrm, SimulationStateOrm


class SimulationRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

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

            return Simulation(
                id=simulation.id,
                name=simulation.name,
                description=simulation.description,
                agent_preset=AgentPreset.model_validate(simulation.agent_preset),
                data_preset=DataPreset.model_validate(simulation.data_preset),
                language=simulation.language,
            )

    async def list(self) -> list[Simulation]:
        """
        List all simulations.
        :return: A list of simulations
        """
        async with self._session_factory() as session:
            simulations = await session.scalars(select(SimulationOrm))

            return [
                Simulation(
                    id=simulation.id,
                    name=simulation.name,
                    description=simulation.description,
                    agent_preset=AgentPreset.model_validate(simulation.agent_preset),
                    data_preset=DataPreset.model_validate(simulation.data_preset),
                    language=simulation.language,
                )
                for simulation in simulations
            ]

    async def create(self, simulation: Simulation) -> None:
        """
        Create a simulation in the database.
        :param simulation: The simulation to create.
        """
        async with self._session_factory() as session:
            session.add(
                SimulationOrm(
                    id=simulation.id,
                    name=simulation.name,
                    description=simulation.description,
                    data_preset=simulation.data_preset.model_dump(),
                    language=simulation.language
                )
            )

            await session.commit()

    async def update(self, simulation: Simulation) -> None:
        """
        Update an existing simulation.
        :param simulation: The new simulation data.
        """
        async with self._session_factory() as session:
            await session.merge(
                SimulationOrm(
                    id=simulation.id,
                    name=simulation.name,
                    description=simulation.description,
                    data_preset=simulation.data_preset.model_dump(),
                    language=simulation.language
                )
            )

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

            return SimulationState(
                id=state.id,
                scene=state.location_id,
                turn_number=state.turn_number,
                state=state.state,
                time_label=state.time_label,
                recent_history_summary=state.recent_history_summary,
                long_term_history_summary=state.long_term_history_summary,
            )
