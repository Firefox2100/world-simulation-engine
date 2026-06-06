from typing import Optional, Union
from pydantic import BaseModel, Field

from .connection_profile import LlmConnectionProfile
from .prompt_message import PromptMessage


class AgentProfile(BaseModel):
    """
    An agent configuration profile for a specific agent, configuring the connection (backend), generation
    parameters, prompt history, and other settings. Should be subclassed for specific providers.
    """
    profile: Optional[LlmConnectionProfile] = Field(
        None,
        description="The connection profile to use. This may be None when exported/imported.",
    )

    model: str = Field(
        ...,
        description="The model to use for the agent.",
    )
    temperature: float = Field(
        1.0,
        description="The temperature to use for the agent.",
    )
    context_window: int = Field(
        8192,
        description="The context window to use for the agent.",
    )
    seed: Optional[int] = Field(
        None,
        description="The seed to use for the agent.",
    )
    reasoning: Optional[str | bool] = Field(
        None,
        description="Whether to enable reasoning for the agent. Set to True or False to enable/disable reasoning, "
                    "or `'low'`, `'medium'`, `'high'` to set the reasoning level. Leave None to use the default "
                    "model reasoning level.",
    )
    stop_tokens: Optional[list[str]] = Field(
        None,
        description="The stop tokens to use for the agent.",
    )

    prompts: list[PromptMessage] = Field(
        ...,
        description="The prompt to use for the agent, allowing multiple messages to be constructed.",
    )


class OllamaAgentProfile(AgentProfile):
    """
    A configuration profile exposing Ollama-specific parameters.
    """
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


class OpenAiAgentProfile(AgentProfile):
    pass


AgentProfiles = Union[
    OllamaAgentProfile,
    OpenAiAgentProfile,
]


class AgentPreset(BaseModel):
    """
    An agent preset is a set of user-supplied agent configurations for each agent, persisted in the database
    and bound to a game session / world.
    """
    id: int = Field(
        ...,
        description="The database generated ID of the preset.",
    )
    director: AgentProfiles = Field(
        ...,
        description="The agent configuration profiles for the director.",
    )
