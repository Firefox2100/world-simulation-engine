from typing import Union, Optional, Any, TYPE_CHECKING

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model import EmbeddingProfile

if TYPE_CHECKING:
    from langchain_ollama import OllamaEmbeddings
    from langchain_openai import OpenAIEmbeddings


class EmbeddingService:
    def __init__(self,
                 profile: EmbeddingProfile,
                 ):
        self._profile = profile
        self._model: Union["OllamaEmbeddings", "OpenAIEmbeddings", None] = None

    @staticmethod
    def _create_model(profile: EmbeddingProfile) -> Union["OllamaEmbeddings", "OpenAIEmbeddings"]:
        if profile.connection is None:
            raise ValueError("Connection profile is required for creating a model.")

        if profile.connection.provider == LlmProvider.OLLAMA:
            from langchain_ollama import OllamaEmbeddings

            return OllamaEmbeddings(
                model=profile.model,
                dimensions=profile.dimensions,
                base_url=profile.connection.base_url,
                num_ctx=profile.context_window,
            )
        if profile.connection.provider == LlmProvider.OPENAI:
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model=profile.model,
                dimensions=profile.dimensions,
                base_url=profile.connection.base_url,
                api_key=lambda: profile.connection.api_key,
            )

        raise ValueError(f"Unsupported provider: {profile.connection.provider}")

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile.model_copy()

    @property
    def model(self) -> Union["OllamaEmbeddings", "OpenAIEmbeddings"]:
        if self._model is None:
            self._model = self._create_model(self._profile)

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.model.aembed_documents(texts)
