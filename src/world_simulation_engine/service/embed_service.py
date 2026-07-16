from typing import Union, TYPE_CHECKING

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import ConnectionConfig, OllamaEmbedModelConfig, OpenAiEmbedModelConfig, \
    EmbedModelConfigUnion


if TYPE_CHECKING:
    from langchain_ollama import OllamaEmbeddings
    from langchain_openai import OpenAIEmbeddings


class EmbedService:
    def __init__(self,
                 model_config: EmbedModelConfigUnion,
                 connection_config: ConnectionConfig,
                 ):
        self._model_config = model_config
        self._connection_config = connection_config

        self._model: Union["OllamaEmbeddings", "OpenAIEmbeddings", None] = None

    def _create_model(self) -> Union["OllamaEmbeddings", "OpenAIEmbeddings"]:
        if self._connection_config.type == ConnectionType.OLLAMA:
            if not isinstance(self._model_config, OllamaEmbedModelConfig):
                raise ValueError(
                    "Model config class mismatch: connection config is Ollama while model config "
                    f"is {type(self._model_config)}"
                )

            from langchain_ollama import OllamaEmbeddings

            return OllamaEmbeddings(
                model=self._model_config.model,
                dimensions=self._model_config.dimension,
                base_url=self._connection_config.base_url,
                num_ctx=self._model_config.context_window,
            )
        if self._connection_config.type == ConnectionType.OPENAI:
            if not isinstance(self._model_config, OpenAiEmbedModelConfig):
                raise ValueError(
                    "Model config class mismatch: connection config is OpenAI while model config "
                    f"is {type(self._model_config)}"
                )

            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(
                model=self._model_config.model,
                dimensions=self._model_config.dimension,
                base_url=self._connection_config.base_url,
                api_key=lambda: self._connection_config.api_key,
            )

        raise ValueError(f"Unsupported provider: {self._connection_config.type}")

    @property
    def model(self) -> Union["OllamaEmbeddings", "OpenAIEmbeddings"]:
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
