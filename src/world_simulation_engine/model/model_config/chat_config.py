from uuid import uuid4
from typing import Annotated, Any, Literal, Optional, Union
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
    validate_model_on_init: bool = Field(
        False,
        description="Whether to validate that the model exists in Ollama on initialization.",
    )
    num_gpu: Optional[int] = Field(
        None,
        description="The number of GPUs to use.",
    )
    num_thread: Optional[int] = Field(
        None,
        description="The number of threads to use during computation.",
    )
    logprobs: Optional[bool] = Field(
        None,
        description="Whether to return log probabilities.",
    )
    top_logprobs: Optional[int] = Field(
        None,
        description="Number of most likely tokens to return at each token position.",
    )
    tfs_z: Optional[float] = Field(
        None,
        description="Tail free sampling value used to reduce the impact of less probable tokens.",
    )
    top_k: Optional[int] = Field(
        None,
        description="Limits token sampling to the top K likely tokens.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    format: Optional[Literal["", "json"] | dict[str, Any]] = Field(
        None,
        description="Output format to request from Ollama, such as 'json' or a JSON schema.",
    )
    keep_alive: Optional[int | str] = Field(
        None,
        description="How long the model will stay loaded into memory.",
    )
    client_kwargs: Optional[dict[str, Any]] = Field(
        None,
        description="Additional keyword arguments for both Ollama sync and async clients.",
    )
    async_client_kwargs: Optional[dict[str, Any]] = Field(
        None,
        description="Additional keyword arguments for the Ollama async client.",
    )
    sync_client_kwargs: Optional[dict[str, Any]] = Field(
        None,
        description="Additional keyword arguments for the Ollama sync client.",
    )


class OpenAiChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with OpenAI.
    """

    provider: Literal[ConnectionType.OPENAI] = Field(
        ConnectionType.OPENAI,
        description="Provider for this chat model config",
    )
    reasoning: Optional[dict[str, Any]] = Field(
        None,
        description="Reasoning configuration for OpenAI reasoning models.",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to OpenAI.",
    )
    organization: Optional[str] = Field(
        None,
        description="OpenAI organization to use for requests.",
    )
    openai_proxy: Optional[str] = Field(
        None,
        description="Proxy URL to use for OpenAI requests.",
    )
    request_timeout: Optional[float | tuple[float, float]] = Field(
        None,
        description="Timeout for OpenAI requests, as seconds or a connect/read timeout tuple.",
    )
    stream_usage: Optional[bool] = Field(
        None,
        description="Whether to include usage metadata when streaming.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when generating.",
    )
    presence_penalty: Optional[float] = Field(
        None,
        description="Penalizes repeated tokens.",
    )
    frequency_penalty: Optional[float] = Field(
        None,
        description="Penalizes repeated tokens according to frequency.",
    )
    logprobs: Optional[bool] = Field(
        None,
        description="Whether to return log probabilities.",
    )
    top_logprobs: Optional[int] = Field(
        None,
        description="Number of most likely tokens to return at each token position.",
    )
    logit_bias: Optional[dict[int, int]] = Field(
        None,
        description="Modify the likelihood of specified tokens appearing in the completion.",
    )
    streaming: bool = Field(
        False,
        description="Whether to stream model responses.",
    )
    n: Optional[int] = Field(
        None,
        description="Number of chat completions to generate for each prompt.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    max_completion_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate.",
    )
    reasoning_effort: Optional[str] = Field(
        None,
        description="Constrains effort on reasoning for reasoning models.",
    )
    verbosity: Optional[str] = Field(
        None,
        description="Controls the verbosity level of responses for reasoning models.",
    )
    tiktoken_model_name: Optional[str] = Field(
        None,
        description="Model name to use when counting tokens with tiktoken.",
    )
    default_headers: Optional[dict[str, str]] = Field(
        None,
        description="Headers to include with every OpenAI request.",
    )
    default_query: Optional[dict[str, Any]] = Field(
        None,
        description="Query parameters to include with every OpenAI request.",
    )
    http_socket_options: Optional[list[tuple[int, int, int]]] = Field(
        None,
        description="Low-level socket options for the OpenAI HTTP client.",
    )
    stream_chunk_timeout: Optional[float] = Field(
        None,
        description="Timeout while waiting for the next stream chunk.",
    )
    extra_body: Optional[dict[str, Any]] = Field(
        None,
        description="Additional JSON properties to include in the OpenAI request body.",
    )
    include_response_headers: bool = Field(
        False,
        description="Whether to include response headers in response metadata.",
    )
    disabled_params: Optional[dict[str, Any]] = Field(
        None,
        description="OpenAI parameters to disable for this model.",
    )
    context_management: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Responses API context management configuration.",
    )
    include: Optional[list[str]] = Field(
        None,
        description="Additional output data to include in Responses API responses.",
    )
    service_tier: Optional[str] = Field(
        None,
        description="Latency tier for the request.",
    )
    store: Optional[bool] = Field(
        None,
        description="Whether OpenAI may store the response for later retrieval.",
    )
    truncation: Optional[str] = Field(
        None,
        description="Responses API truncation strategy.",
    )
    use_previous_response_id: bool = Field(
        False,
        description="Whether to pass previous response IDs during Responses API conversations.",
    )
    use_responses_api: Optional[bool] = Field(
        None,
        description="Whether to use the Responses API instead of the Chat Completions API.",
    )


class AnthropicChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with Anthropic.
    """

    provider: Literal[ConnectionType.ANTHROPIC] = Field(
        ConnectionType.ANTHROPIC,
        description="Provider for this chat model config",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to Anthropic.",
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate.",
    )
    timeout: Optional[float] = Field(
        None,
        description="Timeout for Anthropic requests, in seconds.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when generating.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    top_k: Optional[int] = Field(
        None,
        description="Limits token sampling to the top K likely tokens.",
    )
    thinking: Optional[dict[str, Any]] = Field(
        None,
        description="Extended thinking configuration for supported Claude models.",
    )
    output_config: Optional[dict[str, Any]] = Field(
        None,
        description="Anthropic output configuration, such as effort and task budgets.",
    )
    stream_usage: Optional[bool] = Field(
        None,
        description="Whether to include usage metadata when streaming.",
    )
    streaming: bool = Field(
        False,
        description="Whether to stream model responses.",
    )
    default_headers: Optional[dict[str, str]] = Field(
        None,
        description="Headers to include with every Anthropic request.",
    )
    betas: Optional[list[str]] = Field(
        None,
        description="Anthropic beta feature flags to enable.",
    )
    service_tier: Optional[str] = Field(
        None,
        description="Service tier for the request.",
    )
    mcp_servers: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Anthropic MCP server configuration.",
    )
    container: Optional[dict[str, Any] | str] = Field(
        None,
        description="Anthropic container configuration or container identifier.",
    )
    inference_geo: Optional[str] = Field(
        None,
        description="Inference geography for Anthropic data residency.",
    )


class OpenRouterChatModelConfig(OpenAiChatModelConfig):
    """
    The specialised configuration for using a chat model with OpenRouter.
    """

    provider: Literal[ConnectionType.OPENROUTER] = Field(
        ConnectionType.OPENROUTER,
        description="Provider for this chat model config",
    )


class Ai21ChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with AI21.
    """

    provider: Literal[ConnectionType.AI21] = Field(
        ConnectionType.AI21,
        description="Provider for this chat model config",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to AI21.",
    )
    streaming: bool = Field(
        False,
        description="Whether to stream model responses.",
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate.",
    )
    min_tokens: Optional[int] = Field(
        None,
        description="Minimum number of tokens to generate.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    num_results: Optional[int] = Field(
        None,
        description="How many completions to generate for each prompt.",
    )
    logit_bias: Optional[dict[str, float]] = Field(
        None,
        description="Adjust the probability of specific tokens being generated.",
    )
    presence_penalty: Optional[dict[str, Any]] = Field(
        None,
        description="AI21 presence penalty configuration.",
    )
    count_penalty: Optional[dict[str, Any]] = Field(
        None,
        description="AI21 count penalty configuration.",
    )
    frequency_penalty: Optional[dict[str, Any]] = Field(
        None,
        description="AI21 frequency penalty configuration.",
    )


class GoogleGenAiChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with Google GenAI.
    """

    provider: Literal[ConnectionType.GOOGLE_GENAI] = Field(
        ConnectionType.GOOGLE_GENAI,
        description="Provider for this chat model config",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to Google GenAI.",
    )
    max_output_tokens: Optional[int] = Field(
        None,
        description="Maximum number of output tokens to generate.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    top_k: Optional[int] = Field(
        None,
        description="Limits token sampling to the top K likely tokens.",
    )
    n: Optional[int] = Field(
        None,
        description="Number of candidate responses to generate.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when generating.",
    )
    timeout: Optional[float] = Field(
        None,
        description="Timeout for Google GenAI requests, in seconds.",
    )
    safety_settings: Optional[dict[str, Any] | list[dict[str, Any]]] = Field(
        None,
        description="Google GenAI safety settings.",
    )
    response_mime_type: Optional[str] = Field(
        None,
        description="Response MIME type to request from Google GenAI.",
    )
    response_schema: Optional[dict[str, Any]] = Field(
        None,
        description="Schema for structured responses.",
    )
    cached_content: Optional[str] = Field(
        None,
        description="Identifier for cached content to use in the request.",
    )
    thinking_budget: Optional[int] = Field(
        None,
        description="Thinking token budget for supported Gemini models.",
    )
    include_thoughts: Optional[bool] = Field(
        None,
        description="Whether to include model thoughts for supported Gemini models.",
    )
    transport: Optional[str] = Field(
        None,
        description="Transport to use for Google GenAI requests.",
    )
    client_options: Optional[dict[str, Any]] = Field(
        None,
        description="Client options to pass to Google GenAI.",
    )


class MistralAiChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with Mistral AI.
    """

    provider: Literal[ConnectionType.MISTRALAI] = Field(
        ConnectionType.MISTRALAI,
        description="Provider for this chat model config",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to Mistral AI.",
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    random_seed: Optional[int] = Field(
        None,
        description="Random seed to use for generation.",
    )
    safe_mode: Optional[bool] = Field(
        None,
        description="Whether to enable Mistral safe mode.",
    )
    streaming: bool = Field(
        False,
        description="Whether to stream model responses.",
    )
    endpoint: Optional[str] = Field(
        None,
        description="Mistral endpoint URL override.",
    )
    timeout: Optional[int] = Field(
        None,
        description="Timeout for Mistral requests, in seconds.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when generating.",
    )
    max_concurrent_requests: Optional[int] = Field(
        None,
        description="Maximum number of concurrent Mistral requests.",
    )


class CohereChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with Cohere.
    """

    provider: Literal[ConnectionType.COHERE] = Field(
        ConnectionType.COHERE,
        description="Provider for this chat model config",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to Cohere.",
    )
    preamble: Optional[str] = Field(
        None,
        description="Preamble to pass to Cohere chat models.",
    )
    streaming: bool = Field(
        False,
        description="Whether to stream model responses.",
    )
    user_agent: Optional[str] = Field(
        None,
        description="Identifier for the application making the request.",
    )
    timeout_seconds: Optional[float] = Field(
        None,
        description="Timeout for Cohere requests, in seconds.",
    )


class PerplexityChatModelConfig(OpenAiChatModelConfig):
    """
    The specialised configuration for using a chat model with Perplexity.
    """

    provider: Literal[ConnectionType.PERPLEXITY] = Field(
        ConnectionType.PERPLEXITY,
        description="Provider for this chat model config",
    )


class GroqChatModelConfig(OpenAiChatModelConfig):
    """
    The specialised configuration for using a chat model with Groq.
    """

    provider: Literal[ConnectionType.GROQ] = Field(
        ConnectionType.GROQ,
        description="Provider for this chat model config",
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate.",
    )
    reasoning_format: Optional[Literal["parsed", "raw", "hidden"]] = Field(
        None,
        description="Format for reasoning output from supported Groq models.",
    )
    response_format: Optional[dict[str, Any]] = Field(
        None,
        description="Response format to request from Groq.",
    )
    parallel_tool_calls: Optional[bool] = Field(
        None,
        description="Whether to enable parallel function calling during tool use.",
    )


class DeepSeekChatModelConfig(OpenAiChatModelConfig):
    """
    The specialised configuration for using a chat model with DeepSeek.
    """

    provider: Literal[ConnectionType.DEEPSEEK] = Field(
        ConnectionType.DEEPSEEK,
        description="Provider for this chat model config",
    )


class XAiChatModelConfig(OpenAiChatModelConfig):
    """
    The specialised configuration for using a chat model with xAI.
    """

    provider: Literal[ConnectionType.XAI] = Field(
        ConnectionType.XAI,
        description="Provider for this chat model config",
    )
    search_parameters: Optional[dict[str, Any]] = Field(
        None,
        description="xAI live search parameters for supported models.",
    )


class CloudflareChatModelConfig(ChatModelConfig):
    """
    The specialised configuration for using a chat model with Cloudflare Workers AI.
    """

    provider: Literal[ConnectionType.CLOUDFLARE] = Field(
        ConnectionType.CLOUDFLARE,
        description="Provider for this chat model config",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to Cloudflare Workers AI.",
    )
    account_id: Optional[str] = Field(
        None,
        description="Cloudflare account identifier.",
    )
    endpoint_format: Optional[Literal["workers_ai", "openai_compatible"]] = Field(
        None,
        description="Cloudflare endpoint format to use.",
    )
    ai_gateway: Optional[str] = Field(
        None,
        description="Cloudflare AI Gateway slug to route requests through.",
    )
    max_tokens: Optional[int] = Field(
        None,
        description="Maximum number of tokens to generate.",
    )
    top_p: Optional[float] = Field(
        None,
        description="Nucleus sampling probability mass.",
    )
    top_k: Optional[int] = Field(
        None,
        description="Limits token sampling to the top K likely tokens.",
    )
    streaming: bool = Field(
        False,
        description="Whether to stream model responses.",
    )


ChatModelConfigUnion = Annotated[
    Union[
        OllamaChatModelConfig,
        OpenAiChatModelConfig,
        AnthropicChatModelConfig,
        OpenRouterChatModelConfig,
        Ai21ChatModelConfig,
        GoogleGenAiChatModelConfig,
        MistralAiChatModelConfig,
        CohereChatModelConfig,
        PerplexityChatModelConfig,
        GroqChatModelConfig,
        DeepSeekChatModelConfig,
        XAiChatModelConfig,
        CloudflareChatModelConfig,
    ],
    Field(discriminator="provider"),
]
