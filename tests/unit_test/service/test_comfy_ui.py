import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.misc.consts import WORKFLOWS
from world_simulation_engine.service.image_service.comfy_ui import ImageComfyUi


class FakeResponse:
    def __init__(self, *, payload=None, content: bytes = b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def make_comfy(**kwargs) -> ImageComfyUi:
    """Use the real builtin 'character' workflow template, not a synthetic flat dict.

    The template's metadata keys (positive_prompt, model, ...) are JSON pointers relative to the
    node graph nested under its "workflow" key; a synthetic flat dict without that nesting would
    not catch a regression where paths get compiled against the wrong object.
    """
    return ImageComfyUi(workflow=WORKFLOWS["character"], base_url="http://127.0.0.1:8188", **kwargs)


async def test_generate_compiles_the_nested_node_graph_not_the_template(monkeypatch):
    comfy = make_comfy(vae="custom_vae.safetensors", clip="custom_clip.safetensors", seed=42, steps=20, cfg=7)
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
        prompt="a knight in shining armor",
        negative_prompt="blurry, low quality",
        size="768x512",
    )

    assert result == b"png-bytes"
    submitted_graph = post.await_args.kwargs["json"]["prompt"]

    # The compiled object must be the node graph itself (real ComfyUI class_type/inputs/_meta
    # shape preserved), not the flat metadata+graph template wrapper.
    assert "positive_prompt" not in submitted_graph
    assert "workflow" not in submitted_graph
    assert submitted_graph["4"]["class_type"] == "CLIPTextEncode"
    assert submitted_graph["4"]["inputs"]["text"] == "a knight in shining armor"
    assert submitted_graph["4"]["inputs"]["clip"] == ["3", 0]
    assert submitted_graph["5"]["inputs"]["text"] == "blurry, low quality"
    assert submitted_graph["6"]["inputs"]["width"] == 768
    assert submitted_graph["6"]["inputs"]["height"] == 512
    assert submitted_graph["1"]["inputs"]["vae_name"] == "custom_vae.safetensors"
    assert submitted_graph["3"]["inputs"]["clip_name"] == "custom_clip.safetensors"
    assert submitted_graph["8"]["inputs"]["seed"] == 42
    assert submitted_graph["8"]["inputs"]["steps"] == 20
    assert submitted_graph["8"]["inputs"]["cfg"] == 7
    # Untouched nodes (e.g. the UNETLoader) must still carry their original fields intact.
    assert submitted_graph["7"]["class_type"] == "UNETLoader"
    assert submitted_graph["7"]["inputs"]["unet_name"] == "anima-base-v1.0.safetensors"

    assert post.await_args.args[0] == "/prompt"
    assert get.await_args_list[0].args[0] == "/history/prompt-1"
    assert get.await_args_list[2].args[0] == "/view"
    assert get.await_args_list[2].kwargs["params"] == {
        "filename": "ComfyUI_00001_.png",
        "subfolder": "",
        "type": "output",
    }


async def test_generate_randomises_seed_when_not_configured(monkeypatch):
    comfy = make_comfy()
    post = AsyncMock(return_value=FakeResponse(payload={"prompt_id": "prompt-1"}))
    get = AsyncMock(side_effect=[
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

    await comfy.generate(prompt="test prompt")

    submitted_graph = post.await_args.kwargs["json"]["prompt"]
    assert isinstance(submitted_graph["8"]["inputs"]["seed"], int)
    assert 0 <= submitted_graph["8"]["inputs"]["seed"] < 2 ** 32


async def test_generate_raises_when_history_has_no_images(monkeypatch):
    comfy = make_comfy()
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


def test_init_rejects_a_workflow_template_without_a_node_graph():
    with pytest.raises(ValueError, match="node graph"):
        ImageComfyUi(workflow={"positive_prompt": "/4/inputs/text"})
