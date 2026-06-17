from typing import Optional, Union
from pydantic import BaseModel, Field


class ImageBackendConfiguration(BaseModel):
    connection: Optional[int] = Field(
        None,
        description="The connection profile ID to use. This may be None when exported/imported.",
    )


class ComfyUiBackendConfiguration(ImageBackendConfiguration):
    pass


ImageBackendConfigurations = Union[
    ComfyUiBackendConfiguration,
]


class ImageGeneratorProfile(BaseModel):
    backend_configuration: ImageBackendConfigurations = Field(
        ...,
        description="The backend configuration for the image generator.",
    )
