from uuid import uuid4
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ConnectionType
from .connection_config import ConnectionConfig


class ImageModelConfig(BaseModel):
    """
    The configuration for an image generation model. This decides the model to use, sampling parameters, etc.
    """

    model: Optional[str] = Field(
        None,
        description="Name of the model to use",
    )
    connection: Optional[ConnectionConfig] = Field(
        None,
        description="The provider connection used by this image model config",
    )


class ComfyUiImageModelConfig(ImageModelConfig):
    """
    The specialised configuration for using an image generation model with ComfyUI.
    """

    provider: Literal[ConnectionType.COMFYUI] = Field(
        ConnectionType.COMFYUI,
        description="Provider for this image model config",
    )

    vae: Optional[str] = Field(
        None,
        description="Name of the vae model to use",
    )
    clip: Optional[str] = Field(
        None,
        description="Name of the clip model to use",
    )
    image_width: Optional[int] = Field(
        None,
        description="Width of the image to generate",
    )
    image_height: Optional[int] = Field(
        None,
        description="Height of the image to generate",
    )
    seed: Optional[int] = Field(
        None,
        description="Seed for the random number generator",
    )
    steps: Optional[int] = Field(
        None,
        description="Number of steps to generate for each image",
    )
    cfg: Optional[int] = Field(
        None,
        description="Configuration parameters",
    )


ImageModelConfigUnion = Annotated[
    Union[
        ComfyUiImageModelConfig,
    ],
    Field(discriminator="provider"),
]
