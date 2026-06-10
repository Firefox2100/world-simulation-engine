from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model.connection_profile import LlmConnectionProfile, LlmConnectionCreate
from .tables import LlmConnectionProfileOrm


class LlmConnectionRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    async def get(self, connection_id: int) -> LlmConnectionProfile | None:
        """
        Retrieve an LLM connection profile by its ID.
        :param connection_id: The ID of the LLM connection profile to retrieve.
        :return: The LLM connection profile with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            connection = await session.get(LlmConnectionProfileOrm, connection_id)

            if not connection:
                return None

            return LlmConnectionProfile(
                id=connection.id,
                name=connection.name,
                provider=LlmProvider(connection.provider),
                base_url=connection.base_url,
                api_key=connection.api_key,
            )

    async def list(self) -> list[LlmConnectionProfile]:
        """
        List all LLM connection profiles.
        :return: A list of all LLM connection profiles.
        """
        async with self._session_factory() as session:
            result = await session.execute(select(LlmConnectionProfileOrm))
            connections = result.scalars().all()

            return [
                LlmConnectionProfile(
                    id=connection.id,
                    name=connection.name,
                    provider=LlmProvider(connection.provider),
                    base_url=connection.base_url,
                    api_key=connection.api_key,
                )
                for connection in connections
            ]

    async def create(self, connection: LlmConnectionCreate) -> LlmConnectionProfile:
        async with self._session_factory() as session:
            connection_orm = LlmConnectionProfileOrm(
                name=connection.name,
                provider=connection.provider.value,
                base_url=connection.base_url,
                api_key=connection.api_key,
            )
            session.add(connection_orm)

            await session.flush()
            result = LlmConnectionProfile(
                id=connection_orm.id,
                name=connection.name,
                provider=connection.provider,
                base_url=connection.base_url,
                api_key=connection.api_key,
            )
            await session.commit()

        return result


class ConnectionRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @property
    def llm(self) -> LlmConnectionRepository:
        return LlmConnectionRepository(self._session_factory)
