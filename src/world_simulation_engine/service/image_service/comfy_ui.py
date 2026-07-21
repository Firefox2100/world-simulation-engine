import asyncio
import random
import uuid
from copy import deepcopy
from typing import Any
from httpx import AsyncClient


class ImageComfyUi:
    def __init__(self,
                 workflow: dict[str, Any],
                 base_url: str | None = None,
                 vae: str | None = None,
                 clip: str | None = None,
                 seed: int | None = None,
                 steps: int | None = None,
                 cfg: int | None = None,
                 ):
        self._base_url = base_url.strip("/") if base_url else "http://localhost:8188"
        self._workflow = workflow
        self._vae = vae
        self._clip = clip
        self._seed = seed
        self._steps = steps
        self._cfg = cfg

        self._client = AsyncClient(base_url=self._base_url)

    def _compile_workflow(self,
                          path_map: dict[str, Any],
                          ) -> dict[str, Any]:
        """
        Compile the workflow template with the path_map
        :param path_map: A dict with JSON pointer as key, and value to insert as value
        :return: The compiled workflow
        """
        compiled_workflow = deepcopy(self._workflow)

        for path, value in path_map.items():
            keys = path.strip("/").split("/")
            d = compiled_workflow
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = value

        return compiled_workflow

    async def generate(self,
                       prompt: str,
                       negative_prompt: str | None = None,
                       model: str | None = None,
                       size: str = "auto",
                       ) -> bytes:
        path_map: dict[str, Any] = {
            self._workflow["positive_prompt"]: prompt,
        }

        if negative_prompt is not None:
            path_map[self._workflow["negative_prompt"]] = negative_prompt
        if model is not None:
            path_map[self._workflow["model"]] = model
        if size != "auto":
            width, height = map(int, size.split("x"))
            path_map[self._workflow["image_width"]] = width
            path_map[self._workflow["image_height"]] = height

        if self._vae is not None:
            path_map[self._workflow["vae"]] = self._vae
        if self._clip is not None:
            path_map[self._workflow["clip"]] = self._clip
        if self._seed is not None:
            path_map[self._workflow["seed"]] = self._seed
        else:
            # Randomise the seed
            path_map[self._workflow["seed"]] = random.randint(0, 2**32 - 1)
        if self._steps is not None:
            path_map[self._workflow["steps"]] = self._steps
        if self._cfg is not None:
            path_map[self._workflow["cfg"]] = self._cfg

        compiled_workflow = self._compile_workflow(path_map)
        queue_response = await self._client.post(
            "/prompt",
            json={
                "prompt": compiled_workflow,
                "client_id": str(uuid.uuid4()),
            },
        )
        queue_response.raise_for_status()
        prompt_id = queue_response.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id when queueing prompt")

        timeout_seconds = 300.0
        poll_interval_seconds = 0.5
        elapsed = 0.0
        prompt_history: dict[str, Any] | None = None
        while elapsed < timeout_seconds:
            history_response = await self._client.get(f"/history/{prompt_id}")
            history_response.raise_for_status()
            history_data = history_response.json()

            if isinstance(history_data, dict):
                if prompt_id in history_data:
                    prompt_history = history_data[prompt_id]
                    break
                if "outputs" in history_data:
                    prompt_history = history_data
                    break

            await asyncio.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds

        if prompt_history is None:
            raise TimeoutError(f"ComfyUI prompt {prompt_id} did not finish within {timeout_seconds} seconds")

        status = prompt_history.get("status", {})
        if isinstance(status, dict):
            status_details = status.get("status_str")
            if status_details and status_details not in {"success", "completed"}:
                messages = status.get("messages")
                raise RuntimeError(
                    f"ComfyUI prompt {prompt_id} ended with status {status_details}: {messages}"
                )

        outputs = prompt_history.get("outputs", {})
        first_image: dict[str, Any] | None = None
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images", [])
            if images:
                first_image = images[0]
                break

        if not first_image:
            raise RuntimeError(f"ComfyUI prompt {prompt_id} completed without image output")

        image_response = await self._client.get(
            "/view",
            params={
                "filename": first_image["filename"],
                "subfolder": first_image["subfolder"],
                "type": first_image["type"],
            },
        )
        image_response.raise_for_status()
        return image_response.content
