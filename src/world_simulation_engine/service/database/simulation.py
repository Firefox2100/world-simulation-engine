from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Simulation, SimulationState, AgentPreset, DataPreset, EmbeddingProfile
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
                embedding_profile=EmbeddingProfile.model_validate(simulation.embedding_profile),
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
                    embedding_profile=EmbeddingProfile.model_validate(simulation.embedding_profile),
                    language=simulation.language,
                )
                for simulation in simulations
            ]

    async def create(self,
                     simulation: Simulation,
                     world_id: int | None = None,
                     ) -> Simulation:
        """
        Create a simulation in the database.
        :param simulation: The simulation to create.
        :param world_id: The ID of the world configuration that this simulation is generated from. Can be None
        """
        async with self._session_factory() as session:
            new_simulation = SimulationOrm(
                name=simulation.name,
                description=simulation.description,
                world_id=world_id,
                agent_preset=simulation.agent_preset.model_dump(),
                data_preset=simulation.data_preset.model_dump(),
                embedding_profile=simulation.embedding_profile.model_dump(),
                language=simulation.language,
            )
            session.add(new_simulation)

            await session.flush()
            simulation = simulation.model_copy(update={'id': new_simulation.id})

            await session.commit()
            return simulation

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
                    agent_preset=simulation.agent_preset.model_dump(),
                    data_preset=simulation.data_preset.model_dump(),
                    embedding_profile=simulation.embedding_profile.model_dump(),
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

    async def create(self, state: SimulationState) -> SimulationState:
        new_state = SimulationStateOrm(
            id=state.id,
            location_id=state.scene,
            turn_number=state.turn_number,
            state=state.state,
            time_label=state.time_label,
            recent_history_summary=state.recent_history_summary,
            long_term_history_summary=state.long_term_history_summary,
        )

        async with self._session_factory() as session:
            session.add(new_state)

            await session.commit()

            return state.model_copy()
