from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import ComponentType, ConnectionType
from world_simulation_engine.model import ConnectionConfig, OllamaChatModelConfig, OpenAiChatModelConfig, \
    OllamaEmbedModelConfig, OpenAiEmbedModelConfig, Simulation
from world_simulation_engine.service.database.config_store import ConfigStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_world


async def test_connection_config_crud(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.OPENAI,
        name="OpenAI",
        api_key="test-key",
    )

    assert await store.create_connection(connection) == connection
    assert await store.list_connections() == [connection]
    assert await store.get_connection(connection.id) == connection

    updated_connection = await store.update_connection(
        connection.id,
        {
            "name": "Updated OpenAI",
            "base_url": "https://api.example.com",
        },
    )

    assert updated_connection == ConnectionConfig(
        id=connection.id,
        type=connection.type,
        name="Updated OpenAI",
        base_url="https://api.example.com",
        api_key=connection.api_key,
    )
    assert await store.delete_connection(connection.id) is True
    assert await store.get_connection(connection.id) is None
    assert await store.delete_connection(connection.id) is False


async def test_chat_config_crud_and_connection_link(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.OLLAMA,
        name="Local Ollama",
        base_url="http://localhost:11434",
    )
    ollama_chat = OllamaChatModelConfig(
        id=str(uuid4()),
        name="Local Chat",
        model="llama3.1",
        temperature=0.5,
        context_window=4096,
        num_predict=512,
    )
    openai_chat = OpenAiChatModelConfig(
        id=str(uuid4()),
        name="OpenAI Chat",
        model="gpt-test",
        temperature=0.2,
        context_window=8192,
    )

    await store.create_connection(connection)
    assert await store.create_chat(ollama_chat) == ollama_chat
    assert await store.create_chat(openai_chat) == openai_chat
    assert await store.list_chats() == [ollama_chat, openai_chat]
    assert await store.get_chat(ollama_chat.id) == ollama_chat
    assert await store.link_connection(ollama_chat.id, connection.id) == connection
    assert await store.get_connection_by_source(ollama_chat.id) == connection
    assert await store.unlink_connection(ollama_chat.id) is True
    assert await store.get_connection_by_source(ollama_chat.id) is None
    assert await store.unlink_connection(str(uuid4())) is False
    assert await store.link_connection(ollama_chat.id, connection.id) == connection

    updated_chat = await store.update_chat(
        ollama_chat.id,
        {
            "temperature": 0.7,
            "repeat_penalty": 1.1,
        },
    )

    assert updated_chat == OllamaChatModelConfig(
        **{
            **ollama_chat.model_dump(),
            "temperature": 0.7,
            "repeat_penalty": 1.1,
        },
    )
    assert await store.delete_chat(ollama_chat.id) is True
    assert await store.get_chat(ollama_chat.id) is None


async def test_embed_config_crud_and_connection_link(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.OPENAI,
        name="OpenAI",
        api_key="test-key",
    )
    ollama_embed = OllamaEmbedModelConfig(
        id=str(uuid4()),
        model="nomic-embed-text",
        dimension=768,
        context_window=2048,
    )
    openai_embed = OpenAiEmbedModelConfig(
        id=str(uuid4()),
        model="text-embedding-test",
        dimension=1536,
    )

    await store.create_connection(connection)
    assert await store.create_embed(ollama_embed) == ollama_embed
    assert await store.create_embed(openai_embed) == openai_embed
    assert await store.list_embeds() == [ollama_embed, openai_embed]
    assert await store.get_embed(ollama_embed.id) == ollama_embed
    assert await store.link_connection(ollama_embed.id, connection.id) == connection
    assert await store.get_connection_by_embed_source(ollama_embed.id) == connection
    assert await store.unlink_connection(ollama_embed.id) is True
    assert await store.get_connection_by_embed_source(ollama_embed.id) is None
    assert await store.link_connection(ollama_embed.id, connection.id) == connection

    updated_embed = await store.update_embed(
        ollama_embed.id,
        {
            "dimension": 1024,
        },
    )

    assert updated_embed == OllamaEmbedModelConfig(
        **{
            **ollama_embed.model_dump(),
            "dimension": 1024,
        },
    )
    assert await store.delete_embed(ollama_embed.id) is True
    assert await store.get_embed(ollama_embed.id) is None


async def test_simulation_links_to_chat_and_embed_configs_by_component(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Config Simulation",
        description="A simulation configured with model configs",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    store = ConfigStore(clean_neo4j)
    chat_config = OpenAiChatModelConfig(
        id=str(uuid4()),
        name="Narrator Chat",
        model="gpt-test",
    )
    replacement_chat_config = OpenAiChatModelConfig(
        id=str(uuid4()),
        name="Replacement Chat",
        model="gpt-test-2",
    )
    embed_config = OpenAiEmbedModelConfig(
        id=str(uuid4()),
        model="text-embedding-test",
    )

    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    await store.create_chat(chat_config)
    await store.create_chat(replacement_chat_config)
    await store.create_embed(embed_config)

    assert await store.link_chat(simulation.id, chat_config.id, ComponentType.NARRATOR) == chat_config
    assert await store.get_chat_by_source(simulation.id, ComponentType.NARRATOR) == chat_config
    assert await store.link_chat(simulation.id, replacement_chat_config.id, ComponentType.NARRATOR) == \
        replacement_chat_config
    assert await store.get_chat_by_source(simulation.id, ComponentType.NARRATOR) == replacement_chat_config
    assert await store.link_embed(simulation.id, embed_config.id, ComponentType.CHARACTER_SIMULATOR) == embed_config
    assert await store.get_embed_by_source(simulation.id, ComponentType.CHARACTER_SIMULATOR) == embed_config
    assert await store.unlink_chat(simulation.id, ComponentType.NARRATOR) is True
    assert await store.get_chat_by_source(simulation.id, ComponentType.NARRATOR) is None
    assert await store.unlink_chat(str(uuid4()), ComponentType.NARRATOR) is False
    assert await store.unlink_embed(simulation.id, ComponentType.CHARACTER_SIMULATOR) is True
    assert await store.get_embed_by_source(simulation.id, ComponentType.CHARACTER_SIMULATOR) is None
    assert await store.unlink_embed(str(uuid4()), ComponentType.CHARACTER_SIMULATOR) is False
