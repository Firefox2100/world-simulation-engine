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

            return Location(
                id=location.id,
                primary_location=location.primary_location,
                detailed_location=location.detailed_location,
                scene=location.scene,
                description=location.description,
                attributes=location.attributes,
                stats=location.stats,
                entities=[
                    Entity(
                        id=e.id,
                        name=e.name,
                        type=e.type,
                        description=e.description,
                        status=e.status,
                        interactions=e.interactions,
                    ) for e in entity_records
                ],
            )

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
                stmt = stmt.where(LocationOrm.id == simulation_id)

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
                Location(
                    id=l.id,
                    primary_location=l.primary_location,
                    detailed_location=l.detailed_location,
                    scene=l.scene,
                    description=l.description,
                    attributes=l.attributes,
                    stats=l.stats,
                    entities=entity_by_location.get(l.id, []),
                ) for l in location_records
            ]
