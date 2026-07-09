from uuid import uuid4
from typing import Optional, Union
from pydantic import BaseModel, Field


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


class OllamaEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Ollama.
    """

    context_window: Optional[int] = Field(
        None,
        description="The context window to use for embedding"
    )


class OpenAiEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with OpenAI.
    """


EmbedModelConfigUnion = Union[
    OllamaEmbedModelConfig,
    OpenAiEmbedModelConfig,
]
