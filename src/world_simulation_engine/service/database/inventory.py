from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Item, Equipment
from .tables import ItemOrm, EquipmentOrm


class ItemRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: ItemOrm) -> Item:
        payload = {
            column.name: getattr(record, column.name)
            for column in ItemOrm.__table__.columns
            if column.name not in {"simulation_id", "character_id"}
        }
        return Item.model_validate(payload)

    async def get(self, item_id: int) -> Item | None:
        async with self._session_factory() as session:
            item = await session.get(ItemOrm, item_id)

            if not item:
                return None

            return self._to_model(item)

    async def list(self,
                   simulation_id: int | None = None,
                   character_id: int | None = None,
                   include_character_items: bool = False,
                   ) -> list[Item]:
        stmt = select(ItemOrm)

        if simulation_id:
            stmt = stmt.where(ItemOrm.simulation_id == simulation_id)

        if character_id is not None:
            stmt = stmt.where(ItemOrm.character_id == character_id)
        elif not include_character_items:
            stmt = stmt.where(ItemOrm.character_id == character_id)

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self,
                     item: Item,
                     simulation_id: int,
                     character_id: int | None = None,
                     ) -> Item:
        payload = item.model_dump(mode="json", exclude={"id"})
        new_item = ItemOrm(simulation_id=simulation_id, character_id=character_id, **payload)

        async with self._session_factory() as session:
            session.add(new_item)
            await session.commit()

            return self._to_model(new_item)

    async def update(self, item_id: int, patched_data: dict):
        async with self._session_factory() as session:
            await session.execute(
                update(ItemOrm).where(ItemOrm.id == item_id).values(patched_data)
            )
            await session.commit()

    async def delete(self, item_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(ItemOrm).where(ItemOrm.id == item_id)
            )
            await session.commit()


class EquipmentRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: EquipmentOrm) -> Equipment:
        payload = {
            column.name: getattr(record, column.name)
            for column in EquipmentOrm.__table__.columns
            if column.name not in {"simulation_id", "character_id"}
        }
        return Equipment.model_validate(payload)

    async def get(self, equipment_id: int) -> Equipment | None:
        async with self._session_factory() as session:
            equipment = await session.get(EquipmentOrm, equipment_id)

            if not equipment:
                return None

            return self._to_model(equipment)

    async def list(self,
                   simulation_id: int | None = None,
                   character_id: int | None = None,
                   include_character_equipment: bool = False,
                   ) -> list[Equipment]:
        stmt = select(EquipmentOrm)

        if simulation_id:
            stmt = stmt.where(EquipmentOrm.simulation_id == simulation_id)

        if character_id is not None:
            stmt = stmt.where(EquipmentOrm.character_id == character_id)
        elif not include_character_equipment:
            stmt = stmt.where(EquipmentOrm.character_id == character_id)

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self,
                     equipment: Equipment,
                     simulation_id: int,
                     character_id: int | None = None,
                     ) -> Equipment:
        payload = equipment.model_dump(mode="json", exclude={"id"})
        new_equipment = EquipmentOrm(simulation_id=simulation_id, character_id=character_id, **payload)

        async with self._session_factory() as session:
            session.add(new_equipment)
            await session.commit()

            return self._to_model(new_equipment)

    async def update(self, equipment_id: int, patched_data: dict):
        async with self._session_factory() as session:
            await session.execute(
                update(EquipmentOrm).where(EquipmentOrm.id == equipment_id).values(patched_data)
            )
            await session.commit()

    async def delete(self, equipment_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(EquipmentOrm).where(EquipmentOrm.id == equipment_id)
            )
            await session.commit()
