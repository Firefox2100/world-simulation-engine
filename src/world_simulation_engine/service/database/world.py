from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model.world import World, WorldCreate
from .tables import WorldOrm


class WorldRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: WorldOrm) -> World:
        payload = {column.name: getattr(record, column.name) for column in WorldOrm.__table__.columns}
        return World.model_validate(payload)

    async def get(self, world_id: int) -> World | None:
        async with self._session_factory() as session:
            world = await session.get(WorldOrm, world_id)

            if not world:
                return None

            return self._to_model(world)

    async def list(self) -> list[World]:
        async with self._session_factory() as session:
            stmt = select(WorldOrm)
            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self, world: WorldCreate) -> World:
        new_world = WorldOrm(**world.model_dump(mode="json"))

        async with self._session_factory() as session:
            session.add(new_world)
            await session.commit()

            result_dict = world.model_dump(mode="json")
            result_dict["id"] = new_world.id
            return World.model_validate(result_dict)
