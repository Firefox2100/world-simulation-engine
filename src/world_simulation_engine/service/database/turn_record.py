from typing import List
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import TurnRecord, TurnRecordCreate
from .tables import TurnRecordOrm


class TurnRecordRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: TurnRecordOrm) -> TurnRecord:
        payload = {column.name: getattr(record, column.name) for column in TurnRecordOrm.__table__.columns}
        return TurnRecord.model_validate(payload)

    async def get(self, record_id: int) -> TurnRecord | None:
        async with self._session_factory() as session:
            record = await session.get(TurnRecordOrm, record_id)

            if not record:
                return None

            return self._to_model(record)

    async def list(self,
                   simulation_id: int | None = None,
                   turn_type: TurnType | None = None,
                   ) -> list[TurnRecord]:
        async with self._session_factory() as session:
            stmt = select(TurnRecordOrm)
            if simulation_id:
                stmt = stmt.where(TurnRecordOrm.simulation_id == simulation_id)
            if turn_type:
                stmt = stmt.where(TurnRecordOrm.type == turn_type)

            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def get_last_records(self,
                               simulation_id: int,
                               last_n: int = 1,
                               start_from: int | None = None,
                               ) -> List[TurnRecord]:
        if last_n < 1:
            raise ValueError(f"Requested last {last_n} messages for simulation id {simulation_id}")

        async with self._session_factory() as session:
            stmt = (
                select(TurnRecordOrm)
                .where(TurnRecordOrm.simulation_id == simulation_id)
                .order_by(desc(TurnRecordOrm.turn_number))
                .limit(last_n)
            )

            if start_from is not None:
                stmt = stmt.where(TurnRecordOrm.id < start_from)

            result = await session.scalars(stmt)
            records = list(reversed(result.all()))

            if not records:
                return []

            return [self._to_model(record) for record in records]

    async def create(self, record: TurnRecordCreate) -> TurnRecord:
        payload = record.model_dump(mode="json")

        async with self._session_factory() as session:
            new_record = TurnRecordOrm(**payload)
            session.add(new_record)

            await session.commit()
            return self._to_model(new_record)
