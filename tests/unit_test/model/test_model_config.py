from pydantic import TypeAdapter

from world_simulation_engine.model import (
    ChatModelConfigUnion,
    EmbedModelConfigUnion,
    OllamaChatModelConfig,
    OllamaEmbedModelConfig,
    OpenAiChatModelConfig,
    OpenAiEmbedModelConfig,
)


def test_chat_model_configs_expose_provider_discriminator():
    ollama_config = OllamaChatModelConfig(
        name="Local Chat",
        model="llama3.1",
    )
    openai_config = OpenAiChatModelConfig(
        name="OpenAI Chat",
        model="gpt-test",
    )

    assert ollama_config.model_dump()["provider"] == "ollama"
    assert openai_config.model_dump()["provider"] == "openai"


def test_chat_model_config_union_uses_provider_discriminator():
    adapter = TypeAdapter(ChatModelConfigUnion)

    ollama_config = adapter.validate_python(
        {
            "provider": "ollama",
            "name": "Local Chat",
            "model": "llama3.1",
            "num_predict": 512,
        }
    )
    openai_config = adapter.validate_python(
        {
            "provider": "openai",
            "name": "OpenAI Chat",
            "model": "gpt-test",
        }
    )

    assert isinstance(ollama_config, OllamaChatModelConfig)
    assert isinstance(openai_config, OpenAiChatModelConfig)


def test_embed_model_configs_expose_provider_discriminator():
    ollama_config = OllamaEmbedModelConfig(
        model="nomic-embed-text",
        dimension=768,
        context_window=2048,
    )
    openai_config = OpenAiEmbedModelConfig(
        model="text-embedding-3-small",
        dimension=1536,
    )

    assert ollama_config.model_dump()["provider"] == "ollama"
    assert openai_config.model_dump()["provider"] == "openai"


def test_embed_model_config_union_uses_provider_discriminator():
    adapter = TypeAdapter(EmbedModelConfigUnion)

    ollama_config = adapter.validate_python(
        {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "dimension": 768,
            "context_window": 2048,
        }
    )
    openai_config = adapter.validate_python(
        {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimension": 1536,
        }
    )

    assert isinstance(ollama_config, OllamaEmbedModelConfig)
    assert isinstance(openai_config, OpenAiEmbedModelConfig)
