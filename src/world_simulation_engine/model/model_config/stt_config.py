from uuid import uuid4
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ConnectionType
from .connection_config import ConnectionConfig


class SttModelConfig(BaseModel):
    """
    The configuration for an STT (speech-to-text) model. This decides the model to use and
    transcription parameters.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the model",
    )
    model: Optional[str] = Field(
        None,
        description="Name of the model to use, for providers that support switching the underlying STT model",
    )
    connection: Optional[ConnectionConfig] = Field(
        None,
        description="The provider connection used by this STT model config",
    )


class WhisperCppSttModelConfig(SttModelConfig):
    """
    Configuration for whisper.cpp's official HTTP server (examples/server). The server loads one
    model at startup, so `model` is informational only here rather than sent per-request.
    """

    provider: Literal[ConnectionType.WHISPERCPP] = Field(
        ConnectionType.WHISPERCPP,
        description="Provider for this STT model config",
    )
    language: Optional[str] = Field(
        None,
        description="Spoken language code, e.g. 'en' or 'auto' to detect. Server defaults to 'en' if omitted",
    )
    translate: Optional[bool] = Field(
        None,
        description="Whether to translate the transcription into English",
    )
    temperature: Optional[float] = Field(
        None,
        description="Sampling temperature for decoding",
    )
    temperature_inc: Optional[float] = Field(
        None,
        description="Temperature increment used on decoding fallback",
    )
    initial_prompt: Optional[str] = Field(
        None,
        description="Initial prompt text to bias vocabulary/context for the transcription",
    )
    carry_initial_prompt: Optional[bool] = Field(
        None,
        description="Whether to always prepend the initial prompt, rather than only on the first window",
    )


SttModelConfigUnion = Annotated[
    Union[
        WhisperCppSttModelConfig,
    ],
    Field(discriminator="provider"),
]
