import pytest

from world_simulation_engine.model import OllamaChatModelConfig, OllamaEmbedModelConfig


@pytest.fixture(scope="session")
def ollama_chat_model_config():
    return OllamaChatModelConfig(
        name="Evaluation chat",
        model="llama3",
    )


@pytest.fixture(scope="session")
def ollama_embed_model_config():
    return OllamaEmbedModelConfig(
        model="nomic-embed-text",
    )
