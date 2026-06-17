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
                base_url=self._connection.base_url,
                api_key=self._connection.api_key,
            )
