from typing import TypeVar, Generic, Union
from world_simulation_engine.misc.enums import ImageGenerationProvider
from world_simulation_engine.model import ImageGeneratorProfile, ComfyUiBackendConfiguration, \
    ImageGenerationConnectionProfile
from .image_backend import ComfyUiBackend


ImageGeneratorProfileT = TypeVar("ImageGeneratorProfileT", bound="ImageGeneratorProfile")


class ImageGenerator(Generic[ImageGeneratorProfileT]):
    def __init__(self,
                 profile: ImageGeneratorProfileT,
                 connection: ImageGenerationConnectionProfile,
                 ):
        self._profile = profile
        self._connection = connection

        self._backend: Union["ComfyUiBackend", None] = None

    def _create_backend(self) -> Union["ComfyUiBackend"]:
        if self._connection.provider == ImageGenerationProvider.COMFY_UI:
            if not isinstance(self._profile.backend_configuration, ComfyUiBackendConfiguration):
                raise ValueError(
                    f"Profile class mismatch: connection profile is ComfyUI while profile is {type(self._profile)}"
                )

            return ComfyUiBackend(
                workflow_json=self._profile.backend_configuration.workflow,
                checkpoint_loader_id=self._profile.backend_configuration.checkpoint_loader_id,
                positive_prompt_id=self._profile.backend_configuration.positive_prompt_id,
                checkpoint=self._profile.backend_configuration.checkpoint,
                loras=self._profile.backend_configuration.loras,
                negative_prompt_id=self._profile.backend_configuration.negative_prompt_id,
                k_sampler_id=self._profile.backend_configuration.k_sampler_id,
                latent_image_id=self._profile.backend_configuration.latent_image_id,
                seed=self._profile.backend_configuration.seed,
                steps=self._profile.backend_configuration.steps,
                width=self._profile.backend_configuration.width,
                height=self._profile.backend_configuration.height,
                base_url=self._connection.base_url,
                api_key=self._connection.api_key,
            )

    @property
    def profile(self) -> ImageGeneratorProfileT:
        return self._profile.model_copy()

    @property
    def backend(self) -> Union["ComfyUiBackend"]:
        if self._backend is None:
            self._backend = self.create_backend()

        if self._backend is None:
            raise ValueError("Backend is not initialized.")

        return self._backend
