"""Builds `ConnectionConfig`/chat model config objects from the same `WSE_EVAL_*` environment
variables the evaluation_test suite already uses (see `conftest.py`'s `evaluation_connection_config`
/`evaluation_chat_model_config` fixtures, which are thin wrappers around the functions here).

Extracted into its own module (rather than living only in `conftest.py`) so non-pytest consumers -
currently `scripts/build_card_world_bundle.py` - can build the exact same config from the exact
same `.env` without going through pytest fixtures or a real database: this is the one config
source both consumers share, kept in one place so they can never drift apart.
"""

import os

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import (
    ChatModelConfigUnion,
    ConnectionConfig,
    OllamaChatModelConfig,
    OpenAiChatModelConfig,
)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None or value == "" else float(value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None or value == "" else int(value)


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    return None if value is None or value == "" else int(value)


def _env_optional_float(name: str) -> float | None:
    value = os.getenv(name)
    return None if value is None or value == "" else float(value)


def _env_optional_str(name: str) -> str | None:
    value = os.getenv(name)
    return None if value is None or value == "" else value


def build_evaluation_connection_config() -> ConnectionConfig:
    provider = os.getenv("WSE_EVAL_LLM_PROVIDER", "ollama").lower()
    if provider not in {"ollama", "openai"}:
        raise ValueError("WSE_EVAL_LLM_PROVIDER must be either 'ollama' or 'openai'")

    default_base_url = "http://localhost:11434" if provider == "ollama" else None
    return ConnectionConfig(
        id=os.getenv("WSE_EVAL_CONNECTION_ID", "eval_connection"),
        type=ConnectionType(provider),
        name=os.getenv("WSE_EVAL_CONNECTION_NAME", "Evaluation connection"),
        base_url=_env_optional_str("WSE_EVAL_LLM_BASE_URL") or default_base_url,
        api_key=_env_optional_str("WSE_EVAL_LLM_API_KEY"),
    )


def build_evaluation_chat_model_config(connection_config: ConnectionConfig) -> ChatModelConfigUnion:
    if connection_config.type == ConnectionType.OPENAI:
        return OpenAiChatModelConfig(
            id=os.getenv("WSE_EVAL_CHAT_CONFIG_ID", "eval_chat"),
            name=os.getenv("WSE_EVAL_CHAT_CONFIG_NAME", "Evaluation chat"),
            model=os.getenv("WSE_EVAL_CHAT_MODEL", "gpt-4.1-mini"),
            temperature=_env_float("WSE_EVAL_CHAT_TEMPERATURE", 0),
            context_window=_env_int("WSE_EVAL_CHAT_CONTEXT_WINDOW", 65536),
            seed=_env_optional_int("WSE_EVAL_CHAT_SEED"),
            reasoning=_env_optional_str("WSE_EVAL_CHAT_REASONING"),
        )

    return OllamaChatModelConfig(
        id=os.getenv("WSE_EVAL_CHAT_CONFIG_ID", "eval_chat"),
        name=os.getenv("WSE_EVAL_CHAT_CONFIG_NAME", "Evaluation chat"),
        model=os.getenv("WSE_EVAL_CHAT_MODEL", "llama3"),
        temperature=_env_float("WSE_EVAL_CHAT_TEMPERATURE", 0),
        context_window=_env_int("WSE_EVAL_CHAT_CONTEXT_WINDOW", 8192),
        seed=_env_optional_int("WSE_EVAL_CHAT_SEED"),
        reasoning=_env_optional_str("WSE_EVAL_CHAT_REASONING"),
        mirostat=_env_optional_int("WSE_EVAL_OLLAMA_MIROSTAT"),
        mirostat_eta=_env_optional_float("WSE_EVAL_OLLAMA_MIROSTAT_ETA"),
        mirostat_tau=_env_optional_float("WSE_EVAL_OLLAMA_MIROSTAT_TAU"),
        num_predict=_env_optional_int("WSE_EVAL_OLLAMA_NUM_PREDICT"),
        repeat_penalty_window=_env_optional_int("WSE_EVAL_OLLAMA_REPEAT_PENALTY_WINDOW"),
        repeat_penalty=_env_optional_float("WSE_EVAL_OLLAMA_REPEAT_PENALTY"),
    )
