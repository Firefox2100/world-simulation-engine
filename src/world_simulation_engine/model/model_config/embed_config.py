from uuid import uuid4
from typing import Annotated, Any, Literal, Optional, Union
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ConnectionType
from .connection_config import ConnectionConfig


class EmbedModelConfig(BaseModel):
    """
    The configuration for a embedding model. This decides the model to use, vector dimension, etc.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the model",
    )
    name: Optional[str] = Field(
        None,
        description="Display name of the embedding config, falls back to the model identifier when unset",
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

    provider: Literal[ConnectionType.OLLAMA] = Field(
        ConnectionType.OLLAMA,
        description="Provider for this embedding model config",
    )
    context_window: Optional[int] = Field(
        None,
        description="The context window to use for embedding",
    )
    validate_model_on_init: bool = Field(
        False,
        description="Whether to validate that the model exists in Ollama on initialization.",
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
    mirostat: Optional[int] = Field(
        None,
        description="Enable Mirostat sampling for controlling perplexity.",
    )
    mirostat_eta: Optional[float] = Field(
        None,
        description="Influences how quickly the Mirostat algorithm responds to feedback.",
    )
    mirostat_tau: Optional[float] = Field(
        None,
        description="Controls the balance between coherence and diversity.",
    )
    num_gpu: Optional[int] = Field(
        None,
        description="The number of GPUs to use.",
    )
    keep_alive: Optional[int] = Field(
        None,
        description="How long the model will stay loaded into memory.",
    )
    num_thread: Optional[int] = Field(
        None,
        description="The number of threads to use during computation.",
    )
    repeat_last_n: Optional[int] = Field(
        None,
        description="Sets how far back the model looks to prevent repetition.",
    )
    repeat_penalty: Optional[float] = Field(
        None,
        description="Sets how strongly to penalize repetitions.",
    )
    temperature: Optional[float] = Field(
        None,
        description="Sampling temperature used by embedding-capable Ollama models.",
    )
    stop: Optional[list[str]] = Field(
        None,
        description="Stop tokens to pass to Ollama.",
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


class OpenAiEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with OpenAI.
    """

    provider: Literal[ConnectionType.OPENAI] = Field(
        ConnectionType.OPENAI,
        description="Provider for this embedding model config",
    )
    deployment: Optional[str] = Field(
        None,
        description="OpenAI embedding deployment name, mainly for Azure-compatible deployments.",
    )
    api_version: Optional[str] = Field(
        None,
        description="OpenAI API version, mainly for Azure-compatible deployments.",
    )
    openai_api_type: Optional[str] = Field(
        None,
        description="OpenAI API type override.",
    )
    openai_proxy: Optional[str] = Field(
        None,
        description="Proxy URL to use for OpenAI embedding requests.",
    )
    embedding_ctx_length: Optional[int] = Field(
        None,
        description="Maximum input token length to embed before splitting.",
    )
    organization: Optional[str] = Field(
        None,
        description="OpenAI organization to use for requests.",
    )
    allowed_special: Optional[Literal["all"] | set[str]] = Field(
        None,
        description="Special tokens allowed by the tokenizer.",
    )
    disallowed_special: Optional[Literal["all"] | list[str]] = Field(
        None,
        description="Special tokens disallowed by the tokenizer.",
    )
    chunk_size: Optional[int] = Field(
        None,
        description="Maximum number of texts to embed in a single batch.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when embedding.",
    )
    request_timeout: Optional[float | tuple[float, float]] = Field(
        None,
        description="Timeout for OpenAI requests, as seconds or a connect/read timeout tuple.",
    )
    headers: Optional[dict[str, Any]] = Field(
        None,
        description="Headers to include with embedding requests.",
    )
    tiktoken_enabled: Optional[bool] = Field(
        None,
        description="Whether to use tiktoken for token-aware splitting.",
    )
    tiktoken_model_name: Optional[str] = Field(
        None,
        description="Model name to use when counting tokens with tiktoken.",
    )
    show_progress_bar: Optional[bool] = Field(
        None,
        description="Whether to display a progress bar for batched embedding.",
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional model parameters to pass to OpenAI embeddings.",
    )
    skip_empty: Optional[bool] = Field(
        None,
        description="Whether to skip empty strings instead of raising an error.",
    )
    default_headers: Optional[dict[str, str]] = Field(
        None,
        description="Headers to include with every OpenAI request.",
    )
    default_query: Optional[dict[str, Any]] = Field(
        None,
        description="Query parameters to include with every OpenAI request.",
    )
    retry_min_seconds: Optional[int] = Field(
        None,
        description="Minimum wait between retries.",
    )
    retry_max_seconds: Optional[int] = Field(
        None,
        description="Maximum wait between retries.",
    )
    check_embedding_ctx_length: Optional[bool] = Field(
        None,
        description="Whether to split inputs that exceed the embedding context length.",
    )


class GoogleGenAiEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Google GenAI.
    """

    provider: Literal[ConnectionType.GOOGLE_GENAI] = Field(
        ConnectionType.GOOGLE_GENAI,
        description="Provider for this embedding model config",
    )
    task_type: Optional[str] = Field(
        None,
        description="Google embedding task type, such as RETRIEVAL_QUERY or RETRIEVAL_DOCUMENT.",
    )
    vertexai: Optional[bool] = Field(
        None,
        description="Whether to use Vertex AI instead of the Gemini Developer API.",
    )
    project: Optional[str] = Field(
        None,
        description="Google Cloud project ID for Vertex AI.",
    )
    location: Optional[str] = Field(
        None,
        description="Google Cloud location for Vertex AI.",
    )
    additional_headers: Optional[dict[str, str]] = Field(
        None,
        description="Additional HTTP headers to include in Google GenAI requests.",
    )
    client_args: Optional[dict[str, Any]] = Field(
        None,
        description="Additional arguments for the underlying Google GenAI HTTP client.",
    )
    api_version: Optional[str] = Field(
        None,
        description="Google GenAI API version path segment override.",
    )
    request_options: Optional[dict[str, Any]] = Field(
        None,
        description="Request options to pass to the Google GenAI client.",
    )


class MistralAiEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Mistral AI.
    """

    provider: Literal[ConnectionType.MISTRALAI] = Field(
        ConnectionType.MISTRALAI,
        description="Provider for this embedding model config",
    )
    endpoint: Optional[str] = Field(
        None,
        description="Mistral API endpoint override.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when embedding.",
    )
    timeout: Optional[int] = Field(
        None,
        description="Timeout for Mistral embedding requests, in seconds.",
    )
    wait_time: Optional[int] = Field(
        None,
        description="Seconds to wait before retrying after a rate limit error.",
    )
    max_concurrent_requests: Optional[int] = Field(
        None,
        description="Maximum number of concurrent Mistral embedding requests.",
    )


class CohereEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Cohere.
    """

    provider: Literal[ConnectionType.COHERE] = Field(
        ConnectionType.COHERE,
        description="Provider for this embedding model config",
    )
    truncate: Optional[str] = Field(
        None,
        description="How to truncate inputs that are too long: NONE, START, or END.",
    )
    embedding_types: Optional[list[str]] = Field(
        None,
        description="The embedding types to return from Cohere.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when embedding.",
    )
    request_timeout: Optional[float] = Field(
        None,
        description="Timeout for Cohere embedding requests, in seconds.",
    )
    user_agent: Optional[str] = Field(
        None,
        description="Application user agent to send to Cohere.",
    )


class PerplexityEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Perplexity.
    """

    provider: Literal[ConnectionType.PERPLEXITY] = Field(
        ConnectionType.PERPLEXITY,
        description="Provider for this embedding model config",
    )
    request_timeout: Optional[float | tuple[float, float]] = Field(
        None,
        description="Timeout for Perplexity embedding requests.",
    )
    max_retries: Optional[int] = Field(
        None,
        description="Maximum number of retries to make when embedding.",
    )


class CloudflareEmbedModelConfig(EmbedModelConfig):
    """
    The specialised configuration for using an embedding model with Cloudflare Workers AI.
    """

    provider: Literal[ConnectionType.CLOUDFLARE] = Field(
        ConnectionType.CLOUDFLARE,
        description="Provider for this embedding model config",
    )
    account_id: Optional[str] = Field(
        None,
        description="Cloudflare account ID for Workers AI.",
    )
    batch_size: Optional[int] = Field(
        None,
        description="Number of texts to send in each Cloudflare embedding request.",
    )
    strip_new_lines: Optional[bool] = Field(
        None,
        description="Whether to strip newlines from texts before embedding.",
    )
    api_base_url: Optional[str] = Field(
        None,
        description="Cloudflare API base URL override.",
    )
    headers: Optional[dict[str, str]] = Field(
        None,
        description="Headers to include with Cloudflare embedding requests.",
    )

EmbedModelConfigUnion = Annotated[
    Union[
        OllamaEmbedModelConfig,
        OpenAiEmbedModelConfig,
        GoogleGenAiEmbedModelConfig,
        MistralAiEmbedModelConfig,
        CohereEmbedModelConfig,
        PerplexityEmbedModelConfig,
        CloudflareEmbedModelConfig,
    ],
    Field(discriminator="provider"),
]
