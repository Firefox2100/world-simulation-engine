import os
import pytest

from world_simulation_engine.model import OllamaChatModelConfig, OllamaEmbedModelConfig


@pytest.fixture(scope="session")
def ollama_chat_model_config():
    return OllamaChatModelConfig(
        name=
    )

