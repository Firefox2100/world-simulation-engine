from uuid import uuid4
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from .connection_config import ConnectionConfig


class EmbedModelConfig(BaseModel):
    """
    The configuration for a embedding model. This decides the model to use, vector dimension, etc.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the model",
    )
    model: str = Field(
        ...,
        description="The model to use for embedding",
    )
    dimension: Optional[int] = Field(
        None,
        description="The dimensionality of the model. Not all models support this parameter",
    )
    connection: Optional[ConnectionConfig] = Field(
        None,
        description="The provider connection used by this embedding model config",
    )


class OllamaEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Ollama.
    """

    provider: Literal["ollama"] = Field(
        "ollama",
        description="Provider for this embedding model config",
    )
    context_window: Optional[int] = Field(
        None,
        description="The context window to use for embedding"
    )


class OpenAiEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with OpenAI.
    """

    provider: Literal["openai"] = Field(
        "openai",
        description="Provider for this embedding model config",
    )

EmbedModelConfigUnion = Annotated[
    Union[
        OllamaEmbedModelConfig,
        OpenAiEmbedModelConfig,
    ],
    Field(discriminator="provider"),
]
