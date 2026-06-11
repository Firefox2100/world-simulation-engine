from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model.connection_profile import LlmConnectionProfile, LlmConnectionCreate
from .tables import LlmConnectionProfileOrm


class LlmConnectionRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: LlmConnectionProfileOrm) -> LlmConnectionProfile:
        payload = {column.name: getattr(record, column.name) for column in LlmConnectionProfileOrm.__table__.columns}
        return LlmConnectionProfile.model_validate(payload)

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

            return self._to_model(connection)

    async def list(self) -> list[LlmConnectionProfile]:
        """
        List all LLM connection profiles.
        :return: A list of all LLM connection profiles.
        """
        async with self._session_factory() as session:
            result = await session.execute(select(LlmConnectionProfileOrm))
            connections = result.scalars().all()

            return [self._to_model(connection) for connection in connections]

    async def create(self, connection: LlmConnectionCreate) -> LlmConnectionProfile:
        payload = connection.model_dump(mode="json")

        async with self._session_factory() as session:
            connection_orm = LlmConnectionProfileOrm(**payload)
            session.add(connection_orm)

            await session.commit()

        return self._to_model(connection_orm)


class ConnectionRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @property
    def llm(self) -> LlmConnectionRepository:
        return LlmConnectionRepository(self._session_factory)
