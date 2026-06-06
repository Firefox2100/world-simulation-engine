from fastapi import APIRouter

from world_simulation_engine.model.data_preset import DataPreset
from .utils import db_dep


data_preset_router = APIRouter(
    prefix="/presets/models",
    tags=["Data Model Preset"]
)


@data_preset_router.get("", response_model=list[DataPreset],)
async def list_data_presets(db: db_dep):
    presets = await db.data_preset.list_presets()

    return presets
