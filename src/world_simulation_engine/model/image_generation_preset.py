from typing import Optional, Union
from pydantic import BaseModel, Field


class ImageBackendConfiguration(BaseModel):
    connection: Optional[int] = Field(
        None,
        description="The connection profile ID to use. This may be None when exported/imported.",
    )


class ComfyUiLora(BaseModel):
    name: str = Field(
        ...,
        description="The name of the LoRa to use.",
    )
    strength: float = Field(
        1.0,
        description="The strength of the LoRa.",
        ge=0.0,
        le=1.0,
    )


class ComfyUiBackendConfiguration(ImageBackendConfiguration):
    workflow: dict = Field(
        ...,
        description="The workflow to use, in ComfyUI API format.",
    )

    checkpoint_loader_id: str = Field(
        ...,
        description="The id of the checkpoint loader node.",
    )
    positive_prompt_id: str = Field(
        ...,
        description="The id of the positive prompt node.",
    )
    negative_prompt_id: Optional[str] = Field(
        None,
        description="The id of the negative prompt node.",
    )
    k_sampler_id: Optional[str] = Field(
        None,
        description="The id of the k sampler node.",
    )

    checkpoint: str = Field(
        ...,
        description="The checkpoint to use when generating images.",
    )
    loras: list[ComfyUiLora] = Field(
        default_factory=list,
        description="The list of LoRas to use when generating images.",
    )
    seed: Optional[int] = Field(
        None,
        description="The seed to use when generating images.",
    )
    steps: Optional[int] = Field(
        None,
        description="The number of steps to run when generating images.",
    )
    width: Optional[int] = Field(
        None,
        description="The width of the image to generate.",
    )
    height: Optional[int] = Field(
        None,
        description="The height of the image to generate.",
    )


ImageBackendConfigurations = Union[
    ComfyUiBackendConfiguration,
]


class ImageGeneratorProfile(BaseModel):
    backend_configuration: ImageBackendConfigurations = Field(
        ...,
        description="The backend configuration for the image generator.",
    )
