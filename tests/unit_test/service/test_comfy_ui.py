from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from world_simulation_engine.service.image_service.comfy_ui import ImageComfyUi


class FakeResponse:
    def __init__(self, *, payload=None, content: bytes = b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


async def test_generate_queues_polls_history_and_downloads_image(monkeypatch):
    workflow = {
        "positive_prompt": "/6/inputs/text",
        "negative_prompt": "/7/inputs/text",
        "model": "/4/inputs/ckpt_name",
        "image_width": "/5/inputs/width",
        "image_height": "/5/inputs/height",
        "vae": "/8/inputs/vae",
        "clip": "/6/inputs/clip",
        "seed": "/3/inputs/seed",
        "steps": "/3/inputs/steps",
        "cfg": "/3/inputs/cfg",
    }

    comfy = ImageComfyUi(workflow=workflow, base_url="http://127.0.0.1:8188")
    post = AsyncMock(return_value=FakeResponse(payload={"prompt_id": "prompt-1"}))
    get = AsyncMock(side_effect=[
        FakeResponse(payload={}),
        FakeResponse(payload={
            "prompt-1": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"},
                        ],
                    },
                },
            },
        }),
        FakeResponse(content=b"png-bytes"),
    ])
    comfy._client = SimpleNamespace(post=post, get=get)
    monkeypatch.setattr(
        "world_simulation_engine.service.image_service.comfy_ui.asyncio.sleep",
        AsyncMock(),
    )

    result = await comfy.generate(
        prompt="test prompt",
        negative_prompt="bad",
        model="model.safetensors",
        size="768x512",
    )

    assert result == b"png-bytes"
    assert post.await_args.args[0] == "/prompt"
    assert get.await_args_list[0].args[0] == "/history/prompt-1"
    assert get.await_args_list[2].args[0] == "/view"
    assert get.await_args_list[2].kwargs["params"] == {
        "filename": "ComfyUI_00001_.png",
        "subfolder": "",
        "type": "output",
    }


async def test_generate_raises_when_history_has_no_images(monkeypatch):
    workflow = {
        "positive_prompt": "/6/inputs/text",
        "seed": "/3/inputs/seed",
    }
    comfy = ImageComfyUi(workflow=workflow, base_url="http://127.0.0.1:8188")
    comfy._client = SimpleNamespace(
        post=AsyncMock(return_value=FakeResponse(payload={"prompt_id": "prompt-1"})),
        get=AsyncMock(return_value=FakeResponse(payload={"prompt-1": {"outputs": {}}})),
    )
    monkeypatch.setattr(
        "world_simulation_engine.service.image_service.comfy_ui.asyncio.sleep",
        AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="without image output"):
        await comfy.generate(prompt="test prompt")
