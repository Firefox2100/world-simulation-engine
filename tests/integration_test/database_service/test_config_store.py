from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, ImageGenerationMode
from world_simulation_engine.model import ComfyUiImageModelConfig, ConnectionConfig, ImageGenerationConfig, \
    OllamaChatModelConfig, OpenAiChatModelConfig, OllamaEmbedModelConfig, OpenAiEmbedModelConfig, Simulation
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
    ollama_chat_with_connection = OllamaChatModelConfig(
        **{
            **ollama_chat.model_dump(),
            "connection": connection,
        },
    )
    assert await store.get_chat(ollama_chat.id) == ollama_chat_with_connection
    assert await store.list_chats() == [ollama_chat_with_connection, openai_chat]
    assert await store.get_connection_by_source(ollama_chat.id) == connection
    assert await store.unlink_connection(ollama_chat.id) is True
    assert await store.get_connection_by_source(ollama_chat.id) is None
    assert await store.unlink_connection(str(uuid4())) is False
    assert await store.link_connection(ollama_chat.id, connection.id) == connection
    assert await store.get_chat(ollama_chat.id) == ollama_chat_with_connection

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
            "connection": connection,
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
    ollama_embed_with_connection = OllamaEmbedModelConfig(
        **{
            **ollama_embed.model_dump(),
            "connection": connection,
        },
    )
    assert await store.get_embed(ollama_embed.id) == ollama_embed_with_connection
    assert await store.list_embeds() == [ollama_embed_with_connection, openai_embed]
    assert await store.get_connection_by_embed_source(ollama_embed.id) == connection
    assert await store.unlink_connection(ollama_embed.id) is True
    assert await store.get_connection_by_embed_source(ollama_embed.id) is None
    assert await store.link_connection(ollama_embed.id, connection.id) == connection
    assert await store.get_embed(ollama_embed.id) == ollama_embed_with_connection

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
            "connection": connection,
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
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.OPENAI,
        name="OpenAI",
        api_key="test-key",
    )
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
    await store.create_connection(connection)
    await store.create_chat(chat_config)
    await store.create_chat(replacement_chat_config)
    await store.create_embed(embed_config)
    await store.link_connection(replacement_chat_config.id, connection.id)
    replacement_chat_config_with_connection = OpenAiChatModelConfig(
        **{
            **replacement_chat_config.model_dump(),
            "connection": connection,
        },
    )

    assert await store.link_chat(simulation.id, chat_config.id, ComponentType.NARRATOR) == chat_config
    assert await store.get_chat_by_source(simulation.id, ComponentType.NARRATOR) == chat_config
    assert await store.link_chat(simulation.id, replacement_chat_config.id, ComponentType.NARRATOR) == \
        replacement_chat_config_with_connection
    assert await store.get_chat_by_source(simulation.id, ComponentType.NARRATOR) == replacement_chat_config_with_connection
    assert await store.link_embed(simulation.id, embed_config.id, ComponentType.CHARACTER_SIMULATOR) == embed_config
    assert await store.get_embed_by_source(simulation.id, ComponentType.CHARACTER_SIMULATOR) == embed_config
    assert await store.list_chats_by_source(simulation.id) == {
        ComponentType.NARRATOR: replacement_chat_config_with_connection,
    }
    assert await store.list_embeds_by_source(simulation.id) == {
        ComponentType.CHARACTER_SIMULATOR: embed_config,
    }
    assert await store.unlink_chat(simulation.id, ComponentType.NARRATOR) is True
    assert await store.get_chat_by_source(simulation.id, ComponentType.NARRATOR) is None
    assert await store.list_chats_by_source(simulation.id) == {}
    assert await store.unlink_chat(str(uuid4()), ComponentType.NARRATOR) is False
    assert await store.unlink_embed(simulation.id, ComponentType.CHARACTER_SIMULATOR) is True
    assert await store.get_embed_by_source(simulation.id, ComponentType.CHARACTER_SIMULATOR) is None
    assert await store.list_embeds_by_source(simulation.id) == {}
    assert await store.unlink_embed(str(uuid4()), ComponentType.CHARACTER_SIMULATOR) is False


async def test_image_config_crud_and_connection_link(clean_neo4j):
    store = ConfigStore(clean_neo4j)
    connection = ConnectionConfig(
        id=str(uuid4()),
        type=ConnectionType.COMFYUI,
        name="Local ComfyUI",
        base_url="http://localhost:8188",
    )
    image_config = ComfyUiImageModelConfig(
        id=str(uuid4()),
        model="anima-base-v1.0.safetensors",
        image_width=1024,
        image_height=1024,
        steps=30,
    )

    await store.create_connection(connection)
    assert await store.create_image(image_config) == image_config
    assert await store.list_images() == [image_config]
    assert await store.get_image(image_config.id) == image_config
    assert await store.link_connection(image_config.id, connection.id) == connection
    image_config_with_connection = ComfyUiImageModelConfig(
        **{
            **image_config.model_dump(),
            "connection": connection,
        },
    )
    assert await store.get_image(image_config.id) == image_config_with_connection
    assert await store.list_images() == [image_config_with_connection]
    assert await store.get_connection_by_image_source(image_config.id) == connection
    assert await store.unlink_connection(image_config.id) is True
    assert await store.get_connection_by_image_source(image_config.id) is None
    assert await store.link_connection(image_config.id, connection.id) == connection

    updated_image = await store.update_image(
        image_config.id,
        {
            "steps": 40,
            "cfg": 6,
        },
    )

    assert updated_image == ComfyUiImageModelConfig(
        **{
            **image_config.model_dump(),
            "steps": 40,
            "cfg": 6,
            "connection": connection,
        },
    )
    assert await store.delete_image(image_config.id) is True
    assert await store.get_image(image_config.id) is None


async def test_simulation_links_to_image_config_by_component(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Image Config Simulation",
        description="A simulation configured with an image model config",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    store = ConfigStore(clean_neo4j)
    image_config = ComfyUiImageModelConfig(
        id=str(uuid4()),
        model="anima-base-v1.0.safetensors",
    )
    replacement_image_config = ComfyUiImageModelConfig(
        id=str(uuid4()),
        model="qwen-image.safetensors",
    )

    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    await store.create_image(image_config)
    await store.create_image(replacement_image_config)

    assert await store.link_image(
        simulation.id, image_config.id, ComponentType.CHARACTER_IMAGE_GENERATOR,
    ) == image_config
    assert await store.get_image_by_source(
        simulation.id, ComponentType.CHARACTER_IMAGE_GENERATOR,
    ) == image_config
    assert await store.link_image(
        simulation.id, replacement_image_config.id, ComponentType.CHARACTER_IMAGE_GENERATOR,
    ) == replacement_image_config
    assert await store.get_image_by_source(
        simulation.id, ComponentType.CHARACTER_IMAGE_GENERATOR,
    ) == replacement_image_config
    assert await store.list_images_by_source(simulation.id) == {
        ComponentType.CHARACTER_IMAGE_GENERATOR: replacement_image_config,
    }
    assert await store.unlink_image(simulation.id, ComponentType.CHARACTER_IMAGE_GENERATOR) is True
    assert await store.get_image_by_source(simulation.id, ComponentType.CHARACTER_IMAGE_GENERATOR) is None
    assert await store.list_images_by_source(simulation.id) == {}
    assert await store.unlink_image(str(uuid4()), ComponentType.CHARACTER_IMAGE_GENERATOR) is False


async def test_image_generation_config_get_and_set(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Auto Image Generation Simulation",
        description="A simulation configured with auto image generation triggers",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    store = ConfigStore(clean_neo4j)
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)

    assert await store.get_image_generation_config(simulation.id) is None

    config = ImageGenerationConfig(mode=ImageGenerationMode.AUTO, fallback_turns=5)
    saved = await store.set_image_generation_config(simulation.id, config)

    assert saved == config
    assert await store.get_image_generation_config(simulation.id) == config

    updated_config = ImageGenerationConfig(id=config.id, mode=ImageGenerationMode.ALWAYS, fallback_turns=20)
    resaved = await store.set_image_generation_config(simulation.id, updated_config)

    assert resaved == updated_config
    assert await store.get_image_generation_config(simulation.id) == updated_config
    assert await store.get_image_generation_config(str(uuid4())) is None
