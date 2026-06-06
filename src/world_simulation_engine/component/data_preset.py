import json
import importlib.resources

from world_simulation_engine.model.data_preset import DataPreset, DataPresetModel


class DataPresetValidator:
    """
    A utility class for model validation.
    """
    _core_models: dict | None = None

    def __init__(self,
                 preset: DataPreset,
                 ):
        self._preset = preset

        if not self._validate_preset(preset):
            raise ValueError(
                "Invalid preset. All required core models must be present and have at least the required fields."
            )

    @classmethod
    def _validate_preset(cls, preset: DataPreset) -> bool:
        """
        Validate if a preset is valid by checking:
        - If all required core models are present.
        - If all core models have at least the required fields.
        """
        if cls._core_models is None:
            core_model_path = importlib.resources.files("world_simulation_engine.data.preset") / "core_models.json"
            with core_model_path.open(encoding="utf-8") as f:
                cls._core_models = json.load(f)

        for model_name, core_configuration in cls._core_models.items():
            if model_name not in preset.models:
                return False

            for field, field_configuration in core_configuration["fields"].items():
                if field not in preset.models[model_name].schema["properties"]:
                    return False

                if field_configuration["type"] != preset.models[model_name].schema["properties"][field]["type"]:
                    return False

        return True
