from uuid import uuid4

from world_simulation_engine.misc.enums import ComponentType, ConnectionType
from world_simulation_engine.model import (
    ConnectionConfig,
    OllamaChatModelConfig,
    OpenAiChatModelConfig,
)
from world_simulation_engine.service.database.config_store import ConfigStore
from tests.integration_test.database_service.helpers import create_world


async def test_missing_config_returns_none(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    missing_id = str(uuid4())

    assert await store.get_connection(missing_id) is None
    assert await store.get_connection_by_source(missing_id) is None
    assert await store.get_chat(missing_id) is None
    assert await store.get_chat_by_source(missing_id, ComponentType.CHARACTER_SIMULATOR) is None


async def test_create_connection(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.OPENAI,
        name="OpenAI",
        base_url=None,
        api_key="test-key",
    )

    await store.create_connection(connection)

    assert await store.get_connection(connection.id) == connection


async def test_create_chat_configs(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    ollama_chat = OllamaChatModelConfig(
        id=str(uuid4()),
        model="llama3",
        temperature=0.7,
        context_window=4096,
        seed=123,
        reasoning=False,
        stop_tokens=["END"],
        mirostat=1,
        mirostat_eta=0.1,
        mirostat_tau=5.0,
        num_predict=200,
        repeat_penalty_window=64,
        repeat_penalty=1.1,
    )
    openai_chat = OpenAiChatModelConfig(
        id=str(uuid4()),
        model="gpt-test",
        temperature=0.2,
        context_window=8192,
        seed=None,
        reasoning="low",
        stop_tokens=None,
    )

    await store.create_chat(ollama_chat)
    await store.create_chat(openai_chat)

    assert await store.get_chat(ollama_chat.id) == ollama_chat
    assert await store.get_chat(openai_chat.id) == openai_chat


async def test_connection_and_chat_links(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ConfigStore(clean_neo4j)
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.OPENAI,
        name="OpenAI",
        base_url=None,
        api_key="test-key",
    )
    ollama_chat = OllamaChatModelConfig(id=str(uuid4()), model="llama3")
    openai_chat = OpenAiChatModelConfig(id=str(uuid4()), model="gpt-test")

    await store.create_connection(connection)
    await store.create_chat(ollama_chat)
    await store.create_chat(openai_chat)
    await store.link_connection(ollama_chat.id, connection.id)
    await store.link_chat(world.id, openai_chat.id, ComponentType.CHARACTER_SIMULATOR)

    assert await store.get_connection_by_source(ollama_chat.id) == connection
    assert await store.get_chat_by_source(world.id, ComponentType.CHARACTER_SIMULATOR) == openai_chat
