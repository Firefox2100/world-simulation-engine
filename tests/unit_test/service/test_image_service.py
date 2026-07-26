import os
from unittest.mock import AsyncMock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

import pytest

from world_simulation_engine.misc.consts import WORKFLOWS
from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import ComfyUiImageModelConfig, ConnectionConfig, OllamaChatModelConfig
from world_simulation_engine.service.image_service.image_service import ImageService


def make_service(**model_kwargs) -> ImageService:
    return ImageService(
        model_config=ComfyUiImageModelConfig(id="image_1", **model_kwargs),
        connection_config=ConnectionConfig(
            id="connection_1",
            type=ConnectionType.COMFYUI,
            name="Local ComfyUI",
            base_url="http://127.0.0.1:8188",
        ),
        workflow=WORKFLOWS["character"],
    )


async def test_generate_image_delegates_to_comfy_ui_with_configured_size():
    service = make_service(image_width=768, image_height=512, vae="v", clip="c", seed=1, steps=10, cfg=6)
    service.model.generate = AsyncMock(return_value=b"png-bytes")

    result = await service.generate_image(positive_prompt="a castle", negative_prompt="blurry")

    assert result == b"png-bytes"
    service.model.generate.assert_awaited_once_with(
        prompt="a castle",
        negative_prompt="blurry",
        model=None,
        size="768x512",
    )


async def test_generate_image_uses_auto_size_when_dimensions_are_not_configured():
    service = make_service()
    service.model.generate = AsyncMock(return_value=b"png-bytes")

    await service.generate_image(positive_prompt="a castle")

    service.model.generate.assert_awaited_once_with(
        prompt="a castle",
        negative_prompt=None,
        model=None,
        size="auto",
    )


def test_model_property_rejects_mismatched_config_and_connection():
    service = ImageService(
        model_config=OllamaChatModelConfig(
            id="chat_1", name="Chat", model="llama3.1", temperature=0.5, context_window=4096,
        ),
        connection_config=ConnectionConfig(
            id="connection_1", type=ConnectionType.COMFYUI, name="Local ComfyUI",
        ),
        workflow=WORKFLOWS["character"],
    )

    with pytest.raises(ValueError, match="Model config class mismatch"):
        _ = service.model


def test_model_property_rejects_unsupported_provider():
    service = ImageService(
        model_config=ComfyUiImageModelConfig(id="image_1"),
        connection_config=ConnectionConfig(id="connection_1", type=ConnectionType.OLLAMA, name="Ollama"),
        workflow=WORKFLOWS["character"],
    )

    with pytest.raises(ValueError, match="Unsupported provider"):
        _ = service.model
