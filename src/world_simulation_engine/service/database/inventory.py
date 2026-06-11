from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Item, Equipment
from .tables import ItemOrm


class ItemRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    async def get(self, item_id: int) -> Item | None:
        async with self._session_factory() as session:
            item = await session.get(ItemOrm, item_id)

            if not item:
                return None

            return Item(
                id=item.id,
                name=item.name,
                description=item.description,
                quality=item.quality,
                quantity=item.quantity,
                unique=item.unique,
            )

    async def list(self,
                   simulation_id: int | None = None,
                   character_id: int | None = None,
                   ) -> list[Item]:
        stmt = select(ItemOrm)

        if simulation_id:
            stmt = stmt.where(ItemOrm.simulation_id == simulation_id)

        stmt = stmt.where(ItemOrm.character_id == character_id)

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [
                Item(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    quality=r.quality,
                    quantity=r.quantity,
                    unique=r.unique,
                ) for r in records
            ]

    async def create(self,
                     item: Item,
                     simulation_id: int,
                     character_id: int | None = None,
                     ) -> Item:
        new_item = ItemOrm(
            simulation_id=simulation_id,
            character_id=character_id,
            name=item.name,
            description=item.description,
            quality=item.quality,
            quantity=item.quantity,
            unique=item.unique,
        )

        async with self._session_factory() as session:
            session.add(new_item)
            await session.commit()

            return item.model_copy(update={"id": new_item.id})


class EquipmentRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory
