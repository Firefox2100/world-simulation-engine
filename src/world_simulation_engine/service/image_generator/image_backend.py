from abc import ABC, abstractmethod
import asyncio
import time
from copy import deepcopy
from uuid import uuid4
from httpx import AsyncClient

from world_simulation_engine.model import ComfyUiLora


class ImageBackend(ABC):
    def __init__(self,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 client: AsyncClient | None = None,
                 ):
        self._base_url = base_url
        self._api_key = api_key

        self._client = client or AsyncClient()

    @abstractmethod
    async def generate_image(self,
                             positive_prompt: str,
                             negative_prompt: str,
                             ):
        pass


class ComfyUiBackend(ImageBackend):
    def __init__(self,
                 workflow_json: dict,
                 checkpoint_loader_id: str,
                 positive_prompt_id: str,
                 checkpoint: str,
                 loras: list[ComfyUiLora] | None = None,
                 negative_prompt_id: str | None = None,
                 k_sampler_id: str | None = None,
                 latent_image_id: str | None = None,
                 seed: int | None = None,
                 steps: int | None = None,
                 width: int | None = None,
                 height: int | None = None,
                 base_url: str | None = None,
                 api_key: str | None = None,
                 client: AsyncClient | None = None,
                 ):
        super().__init__(
            base_url=base_url.strip("/") if base_url else "http://localhost:8188",
            api_key=api_key,
            client=client,
        )

        self._workflow_json = workflow_json
        self._checkpoint_loader_id = checkpoint_loader_id
        self._positive_prompt_id = positive_prompt_id
        self._negative_prompt_id = negative_prompt_id
        self._k_sampler_id = k_sampler_id
        self._latent_image_id = latent_image_id

        self._checkpoint = checkpoint
        self._loras = loras or []
        self._seed = seed
        self._steps = steps
        self._width = width
        self._height = height

    @staticmethod
    def _next_node_id(workflow: dict) -> str:
        numeric_ids = [
            int(node_id)
            for node_id in workflow.keys()
            if str(node_id).isdigit()
        ]

        if not numeric_ids:
            return "1"

        return str(max(numeric_ids) + 1)

    def _insert_loras(self, workflow: dict) -> None:
        if not self._loras:
            return

        if not self._k_sampler_id:
            raise ValueError("k_sampler_id is required when using LoRAs")

        current_model_ref = [self._checkpoint_loader_id, 0]
        current_clip_ref = [self._checkpoint_loader_id, 1]

        next_id = int(self._next_node_id(workflow))

        for lora in self._loras:
            node_id = str(next_id)
            next_id += 1

            workflow[node_id] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": current_model_ref,
                    "clip": current_clip_ref,
                    "lora_name": lora.name,
                    "strength_model": lora.strength,
                    "strength_clip": lora.strength,
                },
            }

            current_model_ref = [node_id, 0]
            current_clip_ref = [node_id, 1]

        workflow[self._k_sampler_id]["inputs"]["model"] = current_model_ref
        workflow[self._positive_prompt_id]["inputs"]["clip"] = current_clip_ref

        if self._negative_prompt_id:
            workflow[self._negative_prompt_id]["inputs"]["clip"] = current_clip_ref

    def _build_workflow(self,
                        positive_prompt: str,
                        negative_prompt: str | None = None,
                        ) -> dict:
        workflow = deepcopy(self._workflow_json)

        workflow[self._checkpoint_loader_id]["inputs"]["ckpt_name"] = self._checkpoint
        workflow[self._positive_prompt_id]["inputs"]["text"] = positive_prompt

        if self._negative_prompt_id and negative_prompt is not None:
            workflow[self._negative_prompt_id]["inputs"]["text"] = negative_prompt

        if self._k_sampler_id:
            sampler_inputs = workflow[self._k_sampler_id]["inputs"]
            if self._seed is not None:
                sampler_inputs["seed"] = self._seed
            if self._steps is not None:
                sampler_inputs["steps"] = self._steps

        if self._latent_image_id:
            latent_inputs = workflow[self._latent_image_id]["inputs"]
            if self._width is not None:
                latent_inputs["width"] = self._width
            if self._height is not None:
                latent_inputs["height"] = self._height

        self._insert_loras(workflow)

        return workflow

    async def _queue_generation(self,
                                workflow: dict,
                                client_id: str,
                                ) -> str:
        payload = {
            "prompt": workflow,
            "client_id": client_id,
        }

        result = await self._client.post(
            f"{self._base_url}/prompt",
            json=payload,
        )
        result.raise_for_status()

        data = result.json()

        if data.get("node_errors"):
            raise RuntimeError(f"Node errors occurred: {data['node_errors']}")

        return data["prompt_id"]

    async def _wait_till_done(self,
                              prompt_id: str,
                              timeout: int = 300,
                              interval: float = 2.0,
                              ) -> dict:
        started_at = time.monotonic()

        while time.monotonic() - started_at < timeout:
            result = await self._client.get(
                f"{self._base_url}/history/{prompt_id}"
            )
            result.raise_for_status()

            data = result.json()

            if prompt_id in data and "outputs" in data[prompt_id]:
                return data[prompt_id]

            await asyncio.sleep(interval)

        raise RuntimeError(f"Timeout occurred while waiting for {prompt_id}")

    async def _download_image(self,
                              file_name: str,
                              sub_folder: str,
                              folder_type: str,
                              ) -> bytes:
        result = await self._client.get(
            f"{self._base_url}/view",
            params={
                "filename": file_name,
                "subfolder": sub_folder,
                "type": folder_type,
            },
        )

        result.raise_for_status()
        return result.content

    async def generate_image(self,
                             positive_prompt: str,
                             negative_prompt: str | None = None,
                             ) -> list[bytes]:
        workflow = self._build_workflow(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        )

        client_id = str(uuid4())
        prompt_id = await self._queue_generation(workflow, client_id)
        history = await self._wait_till_done(prompt_id)

        images: list[bytes] = []

        for node_output in history.get("outputs", {}).values():
            for image in node_output.get("images", []):
                if image["type"] == "output":
                    image_data = await self._download_image(
                        file_name=image["filename"],
                        sub_folder=image["subfolder"],
                        folder_type=image["type"],
                    )
                    images.append(image_data)

        return images
