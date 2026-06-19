from world_simulation_engine.misc.enums import LlmProvider, ImageGenerationProvider
from world_simulation_engine.model.connection_profile import (
    LlmConnectionCreate,
    LlmConnectionProfile,
    ImageGenerationConnectionCreate,
    ImageGenerationConnectionProfile,
)


async def test_create_llm_connection(db):
    profile = LlmConnectionCreate(
        provider=LlmProvider.OLLAMA,
        name=None,
        base_url="http://localhost:11434",
        api_key=None,
    )
    result = await db.connection.llm.create(profile)

    assert isinstance(result, LlmConnectionProfile)
    assert result.id == 1
    assert result.provider == LlmProvider.OLLAMA
    assert result.name is None
    assert result.base_url == "http://localhost:11434"
    assert result.api_key is None


async def test_create_llm_connection_with_optional_values(db):
    profile = LlmConnectionCreate(
        provider=LlmProvider.OLLAMA,
        name="Test Connection",
        base_url="http://localhost:11434",
        api_key="dummy-api-key",
    )
    result = await db.connection.llm.create(profile)

    assert isinstance(result, LlmConnectionProfile)
    assert result.id == 1
    assert result.provider == LlmProvider.OLLAMA
    assert result.name == "Test Connection"
    assert result.base_url == "http://localhost:11434"
    assert result.api_key == "dummy-api-key"


async def test_get_llm_connection(db):
    profile = LlmConnectionCreate(
        provider=LlmProvider.OLLAMA,
        name="Test Connection",
        base_url="http://localhost:11434",
        api_key="dummy-api-key",
    )
    result = await db.connection.llm.create(profile)

    fetched = await db.connection.llm.get(result.id)
    assert isinstance(fetched, LlmConnectionProfile)
    assert fetched.id == result.id
    assert fetched.provider == LlmProvider.OLLAMA
    assert fetched.name == "Test Connection"
    assert fetched.base_url == "http://localhost:11434"
    assert fetched.api_key == "dummy-api-key"


async def test_get_llm_connection_not_found(db):
    fetched = await db.connection.llm.get(1)
    assert fetched is None


async def test_list_llm_connections(db):
    await db.connection.llm.create(LlmConnectionCreate(
        provider=LlmProvider.OLLAMA,
        name="Test Connection 1",
        base_url="http://localhost:11434",
        api_key="dummy-api-key",
    ))
    await db.connection.llm.create(LlmConnectionCreate(
        provider=LlmProvider.OLLAMA,
        name="Test Connection 2",
        base_url="http://localhost:11435",
        api_key="another-dummy-api-key",
    ))

    connections = await db.connection.llm.list()
    assert len(connections) == 2
    assert connections[0].name == "Test Connection 1"
    assert connections[0].base_url == "http://localhost:11434"
    assert connections[0].api_key == "dummy-api-key"
    assert connections[1].name == "Test Connection 2"
    assert connections[1].base_url == "http://localhost:11435"
    assert connections[1].api_key == "another-dummy-api-key"


async def test_create_image_generation_connection(db):
    profile = ImageGenerationConnectionCreate(
        provider=ImageGenerationProvider.COMFY_UI,
        name="Image Connection",
        base_url="http://localhost:8188",
        api_key=None,
    )
    result = await db.connection.image.create(profile)

    assert isinstance(result, ImageGenerationConnectionProfile)
    assert result.id == 1
    assert result.provider == ImageGenerationProvider.COMFY_UI
    assert result.name == "Image Connection"
    assert result.base_url == "http://localhost:8188"
    assert result.api_key is None


async def test_get_image_generation_connection(db):
    profile = ImageGenerationConnectionCreate(
        provider=ImageGenerationProvider.COMFY_UI,
        name="Image Connection",
        base_url="http://localhost:8188",
        api_key="image-key",
    )
    result = await db.connection.image.create(profile)

    fetched = await db.connection.image.get(result.id)

    assert isinstance(fetched, ImageGenerationConnectionProfile)
    assert fetched.id == result.id
    assert fetched.provider == ImageGenerationProvider.COMFY_UI
    assert fetched.name == "Image Connection"
    assert fetched.base_url == "http://localhost:8188"
    assert fetched.api_key == "image-key"


async def test_list_image_generation_connections(db):
    await db.connection.image.create(ImageGenerationConnectionCreate(
        provider=ImageGenerationProvider.COMFY_UI,
        name="Image Connection 1",
        base_url="http://localhost:8188",
        api_key="image-key-1",
    ))
    await db.connection.image.create(ImageGenerationConnectionCreate(
        provider=ImageGenerationProvider.COMFY_UI,
        name="Image Connection 2",
        base_url="http://localhost:8189",
        api_key="image-key-2",
    ))

    connections = await db.connection.image.list()
    assert len(connections) == 2
    assert connections[0].name == "Image Connection 1"
    assert connections[0].base_url == "http://localhost:8188"
    assert connections[0].api_key == "image-key-1"
    assert connections[1].name == "Image Connection 2"
    assert connections[1].base_url == "http://localhost:8189"
    assert connections[1].api_key == "image-key-2"


async def test_get_image_generation_connection_not_found(db):
    fetched = await db.connection.image.get(1)
    assert fetched is None


async def test_update_image_generation_connection(db):
    created = await db.connection.image.create(ImageGenerationConnectionCreate(
        provider=ImageGenerationProvider.COMFY_UI,
        name="Image Connection",
        base_url="http://localhost:8188",
        api_key=None,
    ))

    await db.connection.image.update(
        connection_id=created.id,
        patched_data={
            "name": "Updated Image Connection",
            "api_key": "updated-image-key",
        },
    )

    fetched = await db.connection.image.get(created.id)
    assert fetched is not None
    assert fetched.name == "Updated Image Connection"
    assert fetched.base_url == "http://localhost:8188"
    assert fetched.api_key == "updated-image-key"


async def test_delete_image_generation_connection(db):
    created = await db.connection.image.create(ImageGenerationConnectionCreate(
        provider=ImageGenerationProvider.COMFY_UI,
        name="Image Connection",
        base_url="http://localhost:8188",
        api_key=None,
    ))

    await db.connection.image.delete(created.id)

    fetched = await db.connection.image.get(created.id)
    assert fetched is None


