from sqlalchemy import select

from world_simulation_engine.model.data_preset import DataPresetModel, DataPreset
from .tables import DataPresetModelTable, DataPresetTable


class DataPresetRepository:
    def __init__(self,
                 session_factory,
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _record_to_model(record) -> DataPresetModel:
        return DataPresetModel(
            id=record.id,
            name=record.name,
            version=record.version,
            description=record.description,
            schema=record.schema,
        )

    @classmethod
    def _record_to_preset(cls, preset_record, model_records) -> DataPreset:
        return DataPreset(
            id=preset_record.id,
            preset_id=preset_record.preset_id,
            version=preset_record.version,
            name=preset_record.name,
            description=preset_record.description,
            models=[
                cls._record_to_model(r) for r in model_records
            ],
        )

    async def get_preset(self, preset_id: int) -> DataPreset | None:
        async with self._session_factory() as session:
            data_preset_record = (
                await session.execute(
                    select(DataPresetTable).where(DataPresetTable.id == preset_id)
                )
            ).scalar_one_or_none()

            if data_preset_record is None:
                return None

            model_records = (
                await session.execute(
                    select(DataPresetModelTable).where(DataPresetModelTable.preset_id == preset_id)
                )
            ).scalars().all()

            return self._record_to_preset(data_preset_record, model_records)

    async def get_preset_by_preset_id(self, preset_id: str, version: int) -> DataPreset | None:
        async with self._session_factory() as session:
            data_preset_record = (
                await session.execute(
                    select(DataPresetTable).where(
                        DataPresetTable.preset_id == preset_id,
                        DataPresetTable.version == version,
                    )
                )
            ).scalar_one_or_none()

            if data_preset_record is None:
                return None

            model_records = (
                await session.execute(
                    select(DataPresetModelTable).where(DataPresetModelTable.preset_id == data_preset_record.id)
                )
            ).scalars().all()

            return self._record_to_preset(data_preset_record, model_records)

    async def list_presets(self,
                           preset_id: str | None = None,
                           ) -> list[DataPreset]:
        async with self._session_factory() as session:
            query = select(DataPresetTable)

            if preset_id is not None:
                query = query.where(DataPresetTable.__table__.c.preset_id == preset_id)

            preset_records = (await session.execute(query)).scalars().all()

            preset_models = (
                await session.execute(
                    select(
                        DataPresetModelTable
                    ).where(DataPresetModelTable.preset_id.in_([r.id for r in preset_records]))
                )
            ).scalars().all()

            # Group models by preset ID
            preset_id_to_models = {}
            for model in preset_models:
                preset_id_to_models.setdefault(model.preset_id, []).append(model)

            presets = [
                self._record_to_preset(preset_record, preset_id_to_models.get(preset_record.id, []))
                for preset_record in preset_records
            ]

            return presets
