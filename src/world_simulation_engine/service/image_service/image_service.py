from typing import Union, Any

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import ComfyUiImageModelConfig, ImageModelConfigUnion, \
    ConnectionConfig

from .comfy_ui import ImageComfyUi


class ImageService:
    def __init__(self,
                 model_config: ImageModelConfigUnion,
                 connection_config: ConnectionConfig,
                 workflow: dict[str, Any],
                 ):
        self._model_config = model_config
        self._connection_config = connection_config
        self._workflow = workflow

        self._model: Union[ImageComfyUi, None] = None

    def _create_model(self) -> Union[ImageComfyUi]:
        if self._connection_config.type == ConnectionType.COMFYUI:
            if not isinstance(self._model_config, ComfyUiImageModelConfig):
                raise ValueError(
                    "Model config class mismatch: connection config is COMFYUI while model config "
                    f"is {type(self._model_config)}"
                )

            return ImageComfyUi(
                base_url=self._connection_config.base_url,
                workflow=self._workflow,
                vae=self._model_config.vae,
                clip=self._model_config.clip,
                seed=self._model_config.seed,
                steps=self._model_config.steps,
                cfg=self._model_config.cfg,
            )

        raise ValueError(f"Unsupported provider: {self._connection_config.type}")

    @property
    def model(self) -> Union[ImageComfyUi]:
        if self._model is None:
            self._model = self._create_model()

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    async def generate_image(self,
                             positive_prompt: str,
                             negative_prompt: str | None = None,
                             model: str | None = None,
                             ) -> bytes:
        result = await self.model.generate(
            prompt=positive_prompt,
            negative_prompt=negative_prompt,
            model=model,
            size=f"{self._model_config.image_width}x{self._model_config.image_height}"
                if self._model_config.image_width and self._model_config.image_height else "auto",
        )

        return result
