from itertools import groupby
from operator import attrgetter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Location, Entity
from .tables import LocationOrm, EntityOrm


class LocationRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_entity(record: EntityOrm) -> Entity:
        payload = {
            column.name: getattr(record, column.name)
            for column in EntityOrm.__table__.columns
            if column.name != "location_id"
        }
        return Entity.model_validate(payload)

    def _to_location(self, location: LocationOrm, entities: list[EntityOrm]) -> Location:
        payload = {
            column.name: getattr(location, column.name)
            for column in LocationOrm.__table__.columns
            if column.name != "simulation_id"
        }
        payload["entities"] = [self._to_entity(entity) for entity in entities]
        return Location.model_validate(payload)

    async def get(self, location_id: int) -> Location | None:
        """
        Fetch a location by its ID
        :param location_id: The ID of the location
        :return: The location object if found, else None
        """
        async with self._session_factory() as session:
            location = await session.get(LocationOrm, location_id)
            if location is None:
                return None

            result = await session.scalars(select(EntityOrm).where(EntityOrm.location_id == location_id))
            entity_records = result.all()

            return self._to_location(location, entity_records)

    async def list(self,
                   simulation_id: int | None = None,
                   ) -> list[Location]:
        """
        List all locations, optionally filtered by simulation_id
        :param simulation_id: The ID of the simulation to filter by
        :return: A list of Location objects
        """
        async with self._session_factory() as session:
            stmt = select(LocationOrm)
            if simulation_id:
                stmt = stmt.where(LocationOrm.simulation_id == simulation_id)

            result = await session.scalars(stmt.order_by(LocationOrm.id.asc()))
            location_records = result.all()
            if not location_records:
                return []

            location_ids = [location.id for location in location_records]

            result = await session.scalars(
                select(EntityOrm).where(EntityOrm.location_id.in_(location_ids)).order_by(EntityOrm.location_id.asc())
            )
            entity_records = result.all()

            entity_by_location = {
                loc_id: list(entities)
                for loc_id, entities in groupby(entity_records, key=attrgetter("location_id"))
            }

            return [
                self._to_location(location, entity_by_location.get(location.id, []))
                for location in location_records
            ]

    async def create(self,
                     location: Location,
                     simulation_id: int,
                     ) -> Location:
        location_payload = location.model_dump(mode="json", exclude={"entities"})
        new_location = LocationOrm(simulation_id=simulation_id, **location_payload)

        async with self._session_factory() as session:
            session.add(new_location)

            await session.flush()

            new_entities = [
                EntityOrm(location_id=new_location.id, **entity.model_dump(mode="json"))
                for entity in location.entities
            ]

            session.add_all(new_entities)
            await session.commit()

            return self._to_location(new_location, new_entities)
