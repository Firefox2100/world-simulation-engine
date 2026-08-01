from typing import Any, TypeVar, TYPE_CHECKING
from pydantic import BaseModel

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import CloudflareEmbedModelConfig, CohereEmbedModelConfig, ConnectionConfig, \
    EmbedModelConfigUnion, GoogleGenAiEmbedModelConfig, \
    MistralAiEmbedModelConfig, OllamaEmbedModelConfig, OpenAiEmbedModelConfig, PerplexityEmbedModelConfig


if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings


T = TypeVar("T", bound=BaseModel)


class EmbedService:
    def __init__(self,
                 model_config: EmbedModelConfigUnion,
                 connection_config: ConnectionConfig,
                 ):
        self._model_config = model_config
        self._connection_config = connection_config

        self._model: "Embeddings | None" = None

    @staticmethod
    def _without_none(**kwargs) -> dict[str, Any]:
        return {
            key: value
            for key, value in kwargs.items()
            if value is not None
        }

    def _api_kwargs(self) -> dict[str, Any]:
        return self._without_none(
            api_key=self._connection_config.api_key,
            base_url=self._connection_config.base_url,
        )

    def _expect_config(self, expected_type: type[T]) -> T:
        if not isinstance(self._model_config, expected_type):
            raise ValueError(
                "Model config class mismatch: connection config is "
                f"{self._connection_config.type} while model config is {type(self._model_config)}"
            )
        return self._model_config

    def _create_ollama_model(self) -> "Embeddings":
        config = self._expect_config(OllamaEmbedModelConfig)
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(**self._without_none(
            model=config.model,
            dimensions=config.dimension,
            base_url=self._connection_config.base_url,
            num_ctx=config.context_window,
            validate_model_on_init=config.validate_model_on_init,
            client_kwargs=config.client_kwargs,
            async_client_kwargs=config.async_client_kwargs,
            sync_client_kwargs=config.sync_client_kwargs,
            mirostat=config.mirostat,
            mirostat_eta=config.mirostat_eta,
            mirostat_tau=config.mirostat_tau,
            num_gpu=config.num_gpu,
            keep_alive=config.keep_alive,
            num_thread=config.num_thread,
            repeat_last_n=config.repeat_last_n,
            repeat_penalty=config.repeat_penalty,
            temperature=config.temperature,
            stop=config.stop,
            tfs_z=config.tfs_z,
            top_k=config.top_k,
            top_p=config.top_p,
        ))

    def _create_openai_model(self) -> "Embeddings":
        config = self._expect_config(OpenAiEmbedModelConfig)
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(**self._without_none(
            model=config.model,
            dimensions=config.dimension,
            deployment=config.deployment,
            api_version=config.api_version,
            openai_api_type=config.openai_api_type,
            openai_proxy=config.openai_proxy,
            embedding_ctx_length=config.embedding_ctx_length,
            organization=config.organization,
            allowed_special=config.allowed_special,
            disallowed_special=config.disallowed_special,
            chunk_size=config.chunk_size,
            max_retries=config.max_retries,
            timeout=config.request_timeout,
            headers=config.headers,
            tiktoken_enabled=config.tiktoken_enabled,
            tiktoken_model_name=config.tiktoken_model_name,
            show_progress_bar=config.show_progress_bar,
            model_kwargs=config.model_kwargs,
            skip_empty=config.skip_empty,
            default_headers=config.default_headers,
            default_query=config.default_query,
            retry_min_seconds=config.retry_min_seconds,
            retry_max_seconds=config.retry_max_seconds,
            check_embedding_ctx_length=config.check_embedding_ctx_length,
            **self._api_kwargs(),
        ))

    def _create_google_genai_model(self) -> "Embeddings":
        config = self._expect_config(GoogleGenAiEmbedModelConfig)
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(**self._without_none(
            model=config.model,
            task_type=config.task_type,
            google_api_key=self._connection_config.api_key,
            vertexai=config.vertexai,
            project=config.project,
            location=config.location,
            base_url=self._connection_config.base_url,
            additional_headers=config.additional_headers,
            client_args=config.client_args,
            api_version=config.api_version,
            request_options=config.request_options,
            output_dimensionality=config.dimension,
        ))

    def _create_mistralai_model(self) -> "Embeddings":
        config = self._expect_config(MistralAiEmbedModelConfig)
        from langchain_mistralai import MistralAIEmbeddings

        return MistralAIEmbeddings(**self._without_none(
            model=config.model,
            mistral_api_key=self._connection_config.api_key,
            endpoint=config.endpoint or self._connection_config.base_url,
            max_retries=config.max_retries,
            timeout=config.timeout,
            wait_time=config.wait_time,
            max_concurrent_requests=config.max_concurrent_requests,
        ))

    def _create_cohere_model(self) -> "Embeddings":
        config = self._expect_config(CohereEmbedModelConfig)
        from langchain_cohere import CohereEmbeddings

        return CohereEmbeddings(**self._without_none(
            model=config.model,
            cohere_api_key=self._connection_config.api_key,
            base_url=self._connection_config.base_url,
            truncate=config.truncate,
            embedding_types=config.embedding_types,
            max_retries=config.max_retries,
            request_timeout=config.request_timeout,
            user_agent=config.user_agent,
        ))

    def _create_perplexity_model(self) -> "Embeddings":
        config = self._expect_config(PerplexityEmbedModelConfig)
        from langchain_perplexity import PerplexityEmbeddings

        return PerplexityEmbeddings(**self._without_none(
            model=config.model,
            pplx_api_key=self._connection_config.api_key,
            request_timeout=config.request_timeout,
            max_retries=config.max_retries,
        ))

    def _create_cloudflare_model(self) -> "Embeddings":
        config = self._expect_config(CloudflareEmbedModelConfig)
        from langchain_cloudflare.embeddings import CloudflareWorkersAIEmbeddings

        return CloudflareWorkersAIEmbeddings(**self._without_none(
            model_name=config.model,
            account_id=config.account_id,
            api_token=self._connection_config.api_key,
            api_base_url=config.api_base_url or self._connection_config.base_url,
            batch_size=config.batch_size,
            strip_new_lines=config.strip_new_lines,
            headers=config.headers,
        ))

    def _create_model(self) -> "Embeddings":
        if self._connection_config.type == ConnectionType.OLLAMA:
            return self._create_ollama_model()
        if self._connection_config.type == ConnectionType.OPENAI:
            return self._create_openai_model()
        if self._connection_config.type == ConnectionType.GOOGLE_GENAI:
            return self._create_google_genai_model()
        if self._connection_config.type == ConnectionType.MISTRALAI:
            return self._create_mistralai_model()
        if self._connection_config.type == ConnectionType.COHERE:
            return self._create_cohere_model()
        if self._connection_config.type == ConnectionType.PERPLEXITY:
            return self._create_perplexity_model()
        if self._connection_config.type == ConnectionType.CLOUDFLARE:
            return self._create_cloudflare_model()

        raise ValueError(f"Unsupported provider: {self._connection_config.type}")

    @property
    def model(self) -> "Embeddings":
        if self._model is None:
            self._model = self._create_model()

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.model.aembed_documents(texts)

    async def embed_keywords(self, keywords: list[str]) -> list[float] | None:
        if not keywords:
            return None

        return (await self.embed_texts(["\n".join(keywords)]))[0]
