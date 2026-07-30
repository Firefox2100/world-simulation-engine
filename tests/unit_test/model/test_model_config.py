import pytest
from pydantic import TypeAdapter, ValidationError

from world_simulation_engine.model import (
    AllTalkF5ttsModelConfig,
    AllTalkParlerModelConfig,
    AllTalkPiperModelConfig,
    AllTalkVitsModelConfig,
    AllTalkXttsModelConfig,
    ChatModelConfigUnion,
    CharacterTtsConfig,
    EmbedModelConfigUnion,
    OllamaChatModelConfig,
    OllamaEmbedModelConfig,
    OpenAiChatModelConfig,
    OpenAiEmbedModelConfig,
    TtsGenerationConfig,
    TtsModelConfigUnion,
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


def test_tts_model_configs_expose_provider_and_engine_discriminators():
    xtts_config = AllTalkXttsModelConfig(language="en", temperature=0.75)
    piper_config = AllTalkPiperModelConfig(speed=1.1)

    dumped_xtts = xtts_config.model_dump()
    dumped_piper = piper_config.model_dump()
    assert dumped_xtts["provider"] == "alltalk"
    assert dumped_xtts["engine"] == "xtts"
    assert dumped_piper["provider"] == "alltalk"
    assert dumped_piper["engine"] == "piper"


def test_tts_model_config_union_uses_engine_discriminator():
    adapter = TypeAdapter(TtsModelConfigUnion)

    xtts_config = adapter.validate_python(
        {
            "provider": "alltalk",
            "engine": "xtts",
            "language": "en",
            "temperature": 0.75,
        }
    )
    piper_config = adapter.validate_python(
        {
            "provider": "alltalk",
            "engine": "piper",
            "speed": 1.1,
        }
    )
    vits_config = adapter.validate_python(
        {
            "provider": "alltalk",
            "engine": "vits",
        }
    )
    parler_config = adapter.validate_python(
        {
            "provider": "alltalk",
            "engine": "parler",
            "temperature": 0.6,
        }
    )
    f5tts_config = adapter.validate_python(
        {
            "provider": "alltalk",
            "engine": "f5tts",
            "language": "en",
        }
    )

    assert isinstance(xtts_config, AllTalkXttsModelConfig)
    assert isinstance(piper_config, AllTalkPiperModelConfig)
    assert isinstance(vits_config, AllTalkVitsModelConfig)
    assert isinstance(parler_config, AllTalkParlerModelConfig)
    assert isinstance(f5tts_config, AllTalkF5ttsModelConfig)


def test_tts_backend_configs_do_not_carry_any_voice_fields():
    # character_voice and its RVC settings are per-character (CharacterTtsConfig); narrator_voice and
    # its RVC settings are per-simulation (TtsGenerationConfig). Neither belongs on the shared backend
    # config, so many characters/simulations can use the same backend with different voices.
    for config_cls in (
        AllTalkXttsModelConfig,
        AllTalkPiperModelConfig,
        AllTalkVitsModelConfig,
        AllTalkParlerModelConfig,
        AllTalkF5ttsModelConfig,
    ):
        assert "character_voice" not in config_cls.model_fields
        assert "rvc_character_voice" not in config_cls.model_fields
        assert "rvc_character_pitch" not in config_cls.model_fields
        assert "narrator_voice" not in config_cls.model_fields
        assert "rvc_narrator_voice" not in config_cls.model_fields
        assert "rvc_narrator_pitch" not in config_cls.model_fields
        assert "name" in config_cls.model_fields


def test_tts_generation_config_holds_the_narrator_voice():
    # The narrator isn't a specific character and has no CharacterTtsConfig, so its voice lives on
    # the per-simulation TtsGenerationConfig instead of the shared backend config.
    assert "narrator_voice" in TtsGenerationConfig.model_fields
    assert "rvc_narrator_voice" in TtsGenerationConfig.model_fields
    assert "rvc_narrator_pitch" in TtsGenerationConfig.model_fields


def test_character_tts_config_holds_per_character_voice_and_resolved_backend():
    xtts_backend = AllTalkXttsModelConfig(id="backend_1", language="en")
    character_config = CharacterTtsConfig(
        character_voice="female_01.wav",
        rvc_character_voice="voices/female.pth",
        rvc_character_pitch=2,
        backend=xtts_backend,
    )

    assert character_config.character_voice == "female_01.wav"
    assert character_config.rvc_character_pitch == 2
    assert character_config.backend == xtts_backend


def test_tts_engine_configs_only_expose_their_own_generation_parameters():
    # XTTS is sampling-based and multi-lingual: temperature/repetition_penalty/language are valid.
    assert "temperature" in AllTalkXttsModelConfig.model_fields
    assert "repetition_penalty" in AllTalkXttsModelConfig.model_fields
    assert "language" in AllTalkXttsModelConfig.model_fields
    # AllTalk reports xtts as not pitch-capable, so pitch isn't a field on any engine config.
    assert "pitch" not in AllTalkXttsModelConfig.model_fields

    # Piper is deterministic and single-language per model: only speed is tunable.
    assert "speed" in AllTalkPiperModelConfig.model_fields
    assert "temperature" not in AllTalkPiperModelConfig.model_fields
    assert "repetition_penalty" not in AllTalkPiperModelConfig.model_fields
    assert "language" not in AllTalkPiperModelConfig.model_fields

    # VITS: multi-language depends on the loaded model, but no sampling parameters.
    assert "language" in AllTalkVitsModelConfig.model_fields
    assert "temperature" not in AllTalkVitsModelConfig.model_fields

    # Parler describes voices in natural language and supports temperature, but not repetition penalty.
    assert "temperature" in AllTalkParlerModelConfig.model_fields
    assert "repetition_penalty" not in AllTalkParlerModelConfig.model_fields

    # F5-TTS is flow-matching (deterministic): only speed/language are tunable.
    assert "language" in AllTalkF5ttsModelConfig.model_fields
    assert "temperature" not in AllTalkF5ttsModelConfig.model_fields


def test_tts_model_config_union_rejects_unknown_engine():
    adapter = TypeAdapter(TtsModelConfigUnion)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "provider": "alltalk",
                "engine": "not_a_real_engine",
            }
        )
