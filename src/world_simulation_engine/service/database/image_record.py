from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model.image_record import ImageRecordCreate, ImageRecord
from .tables import ImageRecordOrm


class ImageRecordRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: ImageRecordOrm) -> ImageRecord:
        payload = {column.name: getattr(record, column.name) for column in ImageRecordOrm.__table__.columns}
        return ImageRecord.model_validate(payload)

    async def get(self, record_id: int) -> ImageRecord | None:
        async with self._session_factory() as session:
            record = await session.get(ImageRecordOrm, record_id)

            if not record:
                return None

            return self._to_model(record)

    async def list(self,
                   simulation_id: int | None = None,
                   target: str | None = None,
                   category: str | None = None,
                   target_id: int | None = None,
                   ) -> list[ImageRecord]:
        async with self._session_factory() as session:
            stmt = select(ImageRecordOrm)
            if simulation_id:
                stmt = stmt.where(ImageRecordOrm.simulation_id == simulation_id)
            if target:
                stmt = stmt.where(ImageRecordOrm.target == target)
            if category:
                stmt = stmt.where(ImageRecordOrm.category == category)
            if target_id:
                stmt = stmt.where(ImageRecordOrm.target_id == target_id)

            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self, record: ImageRecordCreate) -> ImageRecord:
        payload = record.model_dump(mode="json")

        async with self._session_factory() as session:
            result = await session.execute(
                insert(ImageRecordOrm).values(**payload).on_conflict_do_update(
                    index_elements=["simulation_id", "target", "category", "target_id"],
                    set_={
                        k: v for k, v in payload.items()
                        if k not in {"simulation_id", "target", "category", "target_id"}
                    }
                ).returning(ImageRecordOrm)
            )

            new_record = result.scalar_one()
            await session.commit()
            return self._to_model(new_record)
