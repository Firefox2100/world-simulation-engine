from uuid import uuid4
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ConnectionType
from .connection_config import ConnectionConfig


class ChatModelConfig(BaseModel):
    """
    The configuration for a LLM chat model. This decides the model to use, sampling parameters, etc.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the model",
    )
    name: str = Field(
        ...,
        description="The name of the chat config",
    )
    model: str = Field(
        ...,
        description="The model to use for the chat",
    )
    temperature: float = Field(
        1.0,
        description="The temperature to use for the chat",
    )
    context_window: int = Field(
        8192,
        description="The context window to use for the chat",
    )
    seed: Optional[int] = Field(
        None,
        description="The seed to use for the chat",
    )
    reasoning: Optional[str | bool] = Field(
        None,
        description="Whether to enable reasoning for the chat. Set to True or False to enable/disable reasoning, "
                    "or `'low'`, `'medium'`, `'high'` to set the reasoning level. Leave None to use the default "
                    "model reasoning level",
    )
    stop_tokens: Optional[list[str]] = Field(
        None,
        description="The stop tokens to use for the chat",
    )
    connection: Optional[ConnectionConfig] = Field(
        None,
        description="The provider connection used by this chat model config",
    )


class OllamaChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with Ollama.
    """

    provider: Literal[ConnectionType.OLLAMA] = Field(
        ConnectionType.OLLAMA,
        description="Provider for this chat model config",
    )
    mirostat: Optional[int] = Field(
        None,
        description="Enable Mirostat sampling for controlling perplexity.",
    )
    mirostat_eta: Optional[float] = Field(
        None,
        description="Influences how quickly the algorithm responds to feedback from generated text.",
    )
    mirostat_tau: Optional[float] = Field(
        None,
        description="Controls the balance between coherence and diversity of the output.",
    )
    num_predict: Optional[int] = Field(
        None,
        description="Maximum number of tokens to predict when generating text.",
    )
    repeat_penalty_window: Optional[int] = Field(
        None,
        description="Sets how far back for the model to look back to prevent repetition.",
    )
    repeat_penalty: Optional[float] = Field(
        None,
        description="Sets how strongly to penalize repetitions.",
    )


class OpenAiChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with OpenAI.
    """

    provider: Literal[ConnectionType.OPENAI] = Field(
        ConnectionType.OPENAI,
        description="Provider for this chat model config",
    )


ChatModelConfigUnion = Annotated[
    Union[
        OllamaChatModelConfig,
        OpenAiChatModelConfig,
    ],
    Field(discriminator="provider"),
]
