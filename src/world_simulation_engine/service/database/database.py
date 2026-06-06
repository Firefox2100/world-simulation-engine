from pathlib import Path
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .tables import Base
from .data_preset import DataPresetRepository


class DatabaseService:
    def __init__(self,
                 database_path: str | Path = "data/database.db",
                 ):
        self._database_path = Path(database_path)
        self._engine = create_async_engine(f"sqlite+aiosqlite:///{self._database_path}")
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init(self):
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self):
        await self._engine.dispose()

    @property
    def data_preset(self) -> DataPresetRepository:
        return DataPresetRepository(self._session_factory)
