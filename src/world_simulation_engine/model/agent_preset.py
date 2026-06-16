from typing import Optional, Union
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import SystemMessagePolicy
from .prompt_message import PromptMessage


class AgentBackendConfiguration(BaseModel):
    """
    An agent configuration profile for a specific agent, configuring the connection (backend) and parameters
    that are specific to the agent's LLM usage.
    """
    connection: Optional[int] = Field(
        None,
        description="The connection profile ID to use. This may be None when exported/imported.",
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


class OllamaAgentBackendConfiguration(AgentBackendConfiguration):
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


class OpenAiAgentBackendConfiguration(AgentBackendConfiguration):
    pass


AgentBackendConfigurations = Union[
    OllamaAgentBackendConfiguration,
    OpenAiAgentBackendConfiguration,
]


class AgentProfile(BaseModel):
    """
    A profile for a specific role of an agent.
    """
    backend_configuration: AgentBackendConfigurations = Field(
        ...,
        description="The backend configuration for the agent.",
    )
    remove_empty_messages: bool = Field(
        True,
        description="Whether to remove empty messages from the prompt.",
    )
    merge_adjacent_user: bool = Field(
        True,
        description="Whether to merge adjacent user messages into one.",
    )
    merge_adjacent_assistant: bool = Field(
        False,
        description="Whether to merge adjacent assistant messages into one.",
    )
    merge_assistant_with_tool_calls: bool = Field(
        False,
        description="If merging assistant messages, should the message with tool calls be merged too."
    )
    system_message_policy: SystemMessagePolicy = Field(
        SystemMessagePolicy.MERGE_TO_TOP,
        description="How to post-process the system message sequence.",
    )
    message_merge_separator: str = Field(
        "\n\n",
        description="What separator to use when merging messages."
    )

    max_tool_rounds: int = Field(
        3,
        description="The maximum number of tool rounds to use for the agent."
    )


class DirectorAgentProfile(AgentProfile):
    generation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to decide whether to call generation tools."
    )
    planning_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use after generation, and ask it to output the plan."
    )


class WorldGeneratorAgentProfile(AgentProfile):
    location_generation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate a location."
    )
    item_generation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate an item."
    )
    equipment_generation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate an equipment."
    )
    entity_generation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate an entity."
    )
    world_entry_generation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate a world entry."
    )
    generation_package_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate a generation package."
    )


class MemoryAgentProfile(AgentProfile):
    briefing_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate a briefing for character actions."
    )
    summary_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate a summary for turns."
    )


class CharacterAgentProfile(AgentProfile):
    action_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate an action for a character."
    )
    reaction_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to generate a reaction after failed actions."
    )


class ResolverAgentProfile(AgentProfile):
    resolve_character_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to resolve character actions."
    )
    resolve_reaction_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to resolve character reactions."
    )
    resolve_user_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to resolve user input."
    )


class CommitterAgentProfile(AgentProfile):
    mutation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when ask it to generate new mutations for the world states."
    )
    validation_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to validate the mutations."
    )


class NarratorAgentProfile(AgentProfile):
    narrate_resolved_turn_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to narrate a resolved turn."
    )
    narrate_user_input_failure_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to narrate a user input failure."
    )
    narrate_wait_for_user_prompt: list[PromptMessage] = Field(
        ...,
        description="The prompts to use when asking it to narrate a scenario to wait for user prompt."
    )


class AgentPreset(BaseModel):
    """
    An agent preset is a set of user-supplied agent configurations for each agent, persisted in the database
    and bound to a game session / world.
    """
    director: DirectorAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the director.",
    )
    memory: MemoryAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the memory agent.",
    )
    character: CharacterAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the character agent.",
    )
    resolver: ResolverAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the resolver agent.",
    )
    committer: CommitterAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the committer agent.",
    )
    narrator: NarratorAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the narrator agent.",
    )

    world_generator: WorldGeneratorAgentProfile = Field(
        ...,
        description="The agent configuration profiles for the world generator.",
    )
