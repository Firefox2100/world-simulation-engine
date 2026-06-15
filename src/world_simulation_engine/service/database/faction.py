from sqlalchemy import and_, or_, select, update, delete
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.misc.enums import FactionRelationshipEntity
from world_simulation_engine.model import Faction, FactionRelationship
from .tables import CharacterOrm, FactionOrm, FactionRelationshipOrm, ItemOrm


class FactionRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: FactionOrm) -> Faction:
        payload = {
            column.name: getattr(record, column.name)
            for column in FactionOrm.__table__.columns
            if column.name != "simulation_id"
        }
        return Faction.model_validate(payload)

    async def get(self, faction_id: int) -> Faction | None:
        async with self._session_factory() as session:
            faction = await session.get(FactionOrm, faction_id)

            if not faction:
                return None

            return self._to_model(faction)

    async def list(self,
                   simulation_id: int | None = None,
                   faction_ids: list[int] | None = None,
                   ) -> list[Faction]:
        stmt = select(FactionOrm)

        if simulation_id:
            stmt = stmt.where(FactionOrm.simulation_id == simulation_id)

        if faction_ids:
            stmt = stmt.where(FactionOrm.id.in_(faction_ids))

        async with self._session_factory() as session:
            result = await session.scalars(stmt.order_by(FactionOrm.id.asc()))
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self,
                     faction: Faction,
                     simulation_id: int,
                     ) -> Faction:
        payload = faction.model_dump(mode="json", exclude={"id"})
        new_faction = FactionOrm(simulation_id=simulation_id, **payload)

        async with self._session_factory() as session:
            session.add(new_faction)
            await session.commit()

            return self._to_model(new_faction)

    async def update(self, faction_id: int, patched_data: dict):
        async with self._session_factory() as session:
            await session.execute(
                update(FactionOrm).where(FactionOrm.id == faction_id).values(patched_data)
            )
            await session.commit()

    async def delete(self, faction_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(FactionOrm).where(FactionOrm.id == faction_id)
            )
            await session.commit()


class FactionRelationshipRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: FactionRelationshipOrm) -> FactionRelationship:
        payload = {
            column.name: getattr(record, column.name)
            for column in FactionRelationshipOrm.__table__.columns
            if column.name != "id"
        }
        return FactionRelationship.model_validate(payload)

    async def list(self,
                   entity_refs: list[tuple[FactionRelationshipEntity, int]] | None = None,
                   simulation_id: int | None = None,
                   private: bool | None = None,
                   ) -> list[FactionRelationship]:
        stmt = select(FactionRelationshipOrm)

        if simulation_id is not None:
            from_faction = aliased(FactionOrm)
            from_item = aliased(ItemOrm)
            from_character = aliased(CharacterOrm)
            to_faction = aliased(FactionOrm)
            to_item = aliased(ItemOrm)
            to_character = aliased(CharacterOrm)

            stmt = (
                stmt
                .outerjoin(
                    from_faction,
                    and_(
                        FactionRelationshipOrm.from_type == FactionRelationshipEntity.FACTION.value,
                        FactionRelationshipOrm.from_id == from_faction.id,
                    ),
                )
                .outerjoin(
                    from_item,
                    and_(
                        FactionRelationshipOrm.from_type == FactionRelationshipEntity.ITEM.value,
                        FactionRelationshipOrm.from_id == from_item.id,
                    ),
                )
                .outerjoin(
                    from_character,
                    and_(
                        FactionRelationshipOrm.from_type == FactionRelationshipEntity.CHARACTER.value,
                        FactionRelationshipOrm.from_id == from_character.id,
                    ),
                )
                .outerjoin(
                    to_faction,
                    and_(
                        FactionRelationshipOrm.to_type == FactionRelationshipEntity.FACTION.value,
                        FactionRelationshipOrm.to_id == to_faction.id,
                    ),
                )
                .outerjoin(
                    to_item,
                    and_(
                        FactionRelationshipOrm.to_type == FactionRelationshipEntity.ITEM.value,
                        FactionRelationshipOrm.to_id == to_item.id,
                    ),
                )
                .outerjoin(
                    to_character,
                    and_(
                        FactionRelationshipOrm.to_type == FactionRelationshipEntity.CHARACTER.value,
                        FactionRelationshipOrm.to_id == to_character.id,
                    ),
                )
            )

            stmt = stmt.where(
                or_(
                    and_(
                        FactionRelationshipOrm.from_type == FactionRelationshipEntity.FACTION.value,
                        from_faction.simulation_id == simulation_id,
                    ),
                    and_(
                        FactionRelationshipOrm.from_type == FactionRelationshipEntity.ITEM.value,
                        from_item.simulation_id == simulation_id,
                    ),
                    and_(
                        FactionRelationshipOrm.from_type == FactionRelationshipEntity.CHARACTER.value,
                        from_character.simulation_id == simulation_id,
                    ),
                ),
                or_(
                    and_(
                        FactionRelationshipOrm.to_type == FactionRelationshipEntity.FACTION.value,
                        to_faction.simulation_id == simulation_id,
                    ),
                    and_(
                        FactionRelationshipOrm.to_type == FactionRelationshipEntity.ITEM.value,
                        to_item.simulation_id == simulation_id,
                    ),
                    and_(
                        FactionRelationshipOrm.to_type == FactionRelationshipEntity.CHARACTER.value,
                        to_character.simulation_id == simulation_id,
                    ),
                ),
            )

        if entity_refs:
            clauses = []
            for entity_type, entity_id in entity_refs:
                entity_type_value = entity_type.value
                clauses.extend([
                    (FactionRelationshipOrm.from_type == entity_type_value)
                    & (FactionRelationshipOrm.from_id == entity_id),
                    (FactionRelationshipOrm.to_type == entity_type_value)
                    & (FactionRelationshipOrm.to_id == entity_id),
                ])
            stmt = stmt.where(or_(*clauses))

        if private is not None:
            stmt = stmt.where(FactionRelationshipOrm.private == private)

        async with self._session_factory() as session:
            result = await session.scalars(stmt.order_by(FactionRelationshipOrm.id.asc()))
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self, relationship: FactionRelationship) -> FactionRelationship:
        payload = relationship.model_dump(mode="json")
        new_relationship = FactionRelationshipOrm(**payload)

        async with self._session_factory() as session:
            session.add(new_relationship)
            await session.commit()

            return self._to_model(new_relationship)

    async def update(self, relationship_id: int, patched_data: dict):
        async with self._session_factory() as session:
            await session.execute(
                update(FactionRelationshipOrm).where(FactionRelationshipOrm.id == relationship_id).values(patched_data)
            )
            await session.commit()

    async def delete(self, relationship_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(FactionRelationshipOrm).where(FactionRelationshipOrm.id == relationship_id)
            )
            await session.commit()
