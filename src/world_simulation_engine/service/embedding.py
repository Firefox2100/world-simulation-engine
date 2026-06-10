from typing import Union, TYPE_CHECKING

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model import EmbeddingProfile, LlmConnectionProfile

if TYPE_CHECKING:
    from langchain_ollama import OllamaEmbeddings
    from langchain_openai import OpenAIEmbeddings


class EmbeddingService:
    def __init__(self,
                 profile: EmbeddingProfile,
                 connection: LlmConnectionProfile,
                 ):
        self._profile = profile
        self._connection = connection
        self._model: Union["OllamaEmbeddings", "OpenAIEmbeddings", None] = None

    def _create_model(self) -> Union["OllamaEmbeddings", "OpenAIEmbeddings"]:
        if self._connection.provider == LlmProvider.OLLAMA:
            from langchain_ollama import OllamaEmbeddings

            return OllamaEmbeddings(
                model=self._profile.model,
                dimensions=self._profile.dimensions,
                base_url=self._connection.base_url,
                num_ctx=self._profile.context_window,
            )
        if self._connection.provider == LlmProvider.OPENAI:
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model=self._profile.model,
                dimensions=self._profile.dimensions,
                base_url=self._connection.base_url,
                api_key=lambda: self._connection.api_key,
            )

        raise ValueError(f"Unsupported provider: {self._connection.provider}")

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile.model_copy()

    @property
    def model(self) -> Union["OllamaEmbeddings", "OpenAIEmbeddings"]:
        if self._model is None:
            self._model = self._create_model()

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.model.aembed_documents(texts)
