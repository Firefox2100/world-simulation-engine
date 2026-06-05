from typing import Optional, Any
from pydantic import BaseModel, Field


class DataPresetModel(BaseModel):
    """
    A model inside a preset.
    """
    id: int = Field(
        ...,
        description="The database generated ID of the model.",
    )
    name: str = Field(
        ...,
        description="The name of the model.",
    )
    version: int = Field(
        None,
        description="The version of the model.",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the model.",
    )
    schema: dict[str, Any] = Field(
        ...,
        description="The JSON schema of the model.",
    )


class DataPreset(BaseModel):
    """
    A preset is a set of user-supplied data models that describes the world session. Each preset must
    at least have some core models, which contains at least some core fields, but the models can be
    extended freely to accommodate more complicated data.
    """
    id: int = Field(
        ...,
        description="The database generated ID of the preset.",
    )
    preset_id: str = Field(
        ...,
        description="The creator specified ID of the preset, reverse domain notation recommended."
    )
    version: int = Field(
        ...,
        description="The version of the preset. This is combined with the preset ID as the unique "
                    "identifier of the preset.",
    )
    name: str = Field(
        ...,
        description="The name of the preset.",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the preset.",
    )

    models: dict[str, DataPresetModel] = Field(
        ...,
        description="The models in the preset.",
    )
