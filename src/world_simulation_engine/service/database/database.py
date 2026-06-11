from pathlib import Path
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .tables import Base
from .simulation import SimulationRepository, SimulationStateRepository
from .character import CharacterRepository
from .connection import ConnectionRepository
from .location import LocationRepository
from .turn_record import TurnRecordRepository
from .inventory import ItemRepository, EquipmentRepository
from .world_entry import WorldEntryRepository
from .task import TaskRepository


class DatabaseService:
    def __init__(self,
                 database_path: str | Path = "data/database.db",
                 is_static: bool = False,
                 ):
        self._database_path = Path(database_path)
        self._is_static = is_static

        if not is_static:
            self._engine = create_async_engine(f"sqlite+aiosqlite:///{self._database_path}")
        else:
            self._engine = create_async_engine(
                f"sqlite+aiosqlite:///{self._database_path}",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async def init(self):
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self):
        await self._engine.dispose()

    @property
    def character(self) -> CharacterRepository:
        return CharacterRepository(self._session_factory)

    @property
    def connection(self) -> ConnectionRepository:
        return ConnectionRepository(self._session_factory)

    @property
    def entry(self) -> WorldEntryRepository:
        return WorldEntryRepository(self._session_factory)

    @property
    def equipment(self) -> EquipmentRepository:
        return EquipmentRepository(self._session_factory)

    @property
    def item(self) -> ItemRepository:
        return ItemRepository(self._session_factory)

    @property
    def location(self) -> LocationRepository:
        return LocationRepository(self._session_factory)

    @property
    def record(self) -> TurnRecordRepository:
        return TurnRecordRepository(self._session_factory)

    @property
    def simulation(self) -> SimulationRepository:
        return SimulationRepository(self._session_factory)

    @property
    def state(self) -> SimulationStateRepository:
        return SimulationStateRepository(self._session_factory)

    @property
    def task(self) -> TaskRepository:
        return TaskRepository(self._session_factory)
