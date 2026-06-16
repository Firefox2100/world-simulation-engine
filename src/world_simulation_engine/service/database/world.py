from sqlalchemy import select, update, delete
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

    async def list(self,
                   limit: int | None = None,
                   offset: int = 0,
                   ) -> list[World]:
        async with self._session_factory() as session:
            stmt = select(WorldOrm).order_by(WorldOrm.id)
            if offset:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)

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

    async def update(self, world_id: int, patched_data: dict):
        async with self._session_factory() as session:
            await session.execute(
                update(WorldOrm).where(WorldOrm.id == world_id).values(patched_data)
            )
            await session.commit()

    async def delete(self, world_id: int):
        async with self._session_factory() as session:
            await session.execute(delete(WorldOrm).where(WorldOrm.id == world_id))
            await session.commit()
