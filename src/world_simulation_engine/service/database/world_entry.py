import numpy as np
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.misc.enums import NarrationPermission
from world_simulation_engine.model import WorldEntry
from .tables import WorldEntryOrm


class WorldEntryRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: WorldEntryOrm) -> WorldEntry:
        payload = {column.name: getattr(record, column.name) for column in WorldEntryOrm.__table__.columns}
        payload.pop("simulation_id", None)
        if isinstance(payload.get("embedding"), np.ndarray):
            payload["embedding"] = payload["embedding"].tolist()
        return WorldEntry.model_validate(payload)

    async def get(self, entry_id: int) -> WorldEntry | None:
        """
        Retrieve a world entry by its ID.
        :param entry_id: The ID of the world entry to retrieve.
        :return: The world entry with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            entry = await session.get(WorldEntryOrm, entry_id)

            if not entry:
                return None

            return self._to_model(entry)

    async def list(self,
                   simulation_id: int | None = None,
                   search_scope: list[int] | None = None,
                   entry_ids: list[int] | None = None,
                   narration_only: bool = False,
                   ) -> list[WorldEntry]:
        stmt = select(WorldEntryOrm)
        if simulation_id:
            stmt = stmt.where(WorldEntryOrm.simulation_id == simulation_id)
        if search_scope:
            # Match any that contains any scope ID in the list
            je = func.json_each(WorldEntryOrm.scope).table_valued("value").alias("je")
            stmt = stmt.where(
                exists(
                    select(1)
                    .select_from(je)
                    .where(je.c.value.in_(search_scope))
                )
            )
        if entry_ids:
            stmt = stmt.where(WorldEntryOrm.id.in_(entry_ids))
        if narration_only:
            stmt = stmt.where(WorldEntryOrm.narration_permission.in_(
                [NarrationPermission.VISIBLE, NarrationPermission.MAY_HINT]
            ))

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self,
                     world_entry: WorldEntry,
                     simulation_id: int,
                     ):
        payload = world_entry.model_dump(mode="json", exclude={"id"})
        new_entry = WorldEntryOrm(simulation_id=simulation_id, **payload)

        async with self._session_factory() as session:
            session.add(new_entry)
            await session.commit()

            return self._to_model(new_entry)
