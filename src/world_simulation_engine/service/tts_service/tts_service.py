from typing import Union, AsyncIterator

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import AllTalkF5ttsModelConfig, AllTalkParlerModelConfig, \
    AllTalkPiperModelConfig, AllTalkTtsModelConfigUnion, AllTalkVitsModelConfig, AllTalkXttsModelConfig, \
    TtsModelConfigUnion, ConnectionConfig

from .alltalk_v2 import TtsAllTalkV2
from .tts_result import TtsFileResult


def _alltalk_common_kwargs(model_config: AllTalkTtsModelConfigUnion) -> dict:
    return {
        "text_filtering": model_config.text_filtering,
        "text_not_inside": model_config.text_not_inside,
        "narrator_enabled": model_config.narrator_enabled,
        "narrator_voice": model_config.narrator_voice,
        "rvc_narrator_voice": model_config.rvc_narrator_voice,
        "rvc_narrator_pitch": model_config.rvc_narrator_pitch,
        "output_file_timestamp": model_config.output_file_timestamp,
        "autoplay": model_config.autoplay,
        "autoplay_volume": model_config.autoplay_volume,
    }


class TtsService:
    def __init__(self,
                 model_config: TtsModelConfigUnion,
                 connection_config: ConnectionConfig,
                 ):
        self._model_config = model_config
        self._connection_config = connection_config

        self._driver: Union[TtsAllTalkV2, None] = None

    def _create_driver(self) -> Union[TtsAllTalkV2]:
        if self._connection_config.type == ConnectionType.ALLTALK:
            common_kwargs = {"base_url": self._connection_config.base_url}

            if isinstance(self._model_config, AllTalkXttsModelConfig):
                return TtsAllTalkV2(
                    **common_kwargs,
                    **_alltalk_common_kwargs(self._model_config),
                    language=self._model_config.language,
                    speed=self._model_config.speed,
                    temperature=self._model_config.temperature,
                    repetition_penalty=self._model_config.repetition_penalty,
                )
            if isinstance(self._model_config, AllTalkPiperModelConfig):
                return TtsAllTalkV2(
                    **common_kwargs,
                    **_alltalk_common_kwargs(self._model_config),
                    speed=self._model_config.speed,
                )
            if isinstance(self._model_config, AllTalkVitsModelConfig):
                return TtsAllTalkV2(
                    **common_kwargs,
                    **_alltalk_common_kwargs(self._model_config),
                    language=self._model_config.language,
                    speed=self._model_config.speed,
                )
            if isinstance(self._model_config, AllTalkParlerModelConfig):
                return TtsAllTalkV2(
                    **common_kwargs,
                    **_alltalk_common_kwargs(self._model_config),
                    speed=self._model_config.speed,
                    temperature=self._model_config.temperature,
                )
            if isinstance(self._model_config, AllTalkF5ttsModelConfig):
                return TtsAllTalkV2(
                    **common_kwargs,
                    **_alltalk_common_kwargs(self._model_config),
                    language=self._model_config.language,
                    speed=self._model_config.speed,
                )

            raise ValueError(
                "Model config class mismatch: connection config is AllTalk while model config "
                f"is {type(self._model_config)}"
            )

        raise ValueError(f"Unsupported provider: {self._connection_config.type}")

    @property
    def driver(self) -> Union[TtsAllTalkV2]:
        if self._driver is None:
            self._driver = self._create_driver()

        if self._driver is None:
            raise ValueError("Driver is not initialized.")

        return self._driver

    async def generate_file(self,
                            text: str,
                            voice: str | None = None,
                            rvc_voice: str | None = None,
                            rvc_pitch: int | None = None,
                            ) -> TtsFileResult:
        return await self.driver.generate_file(
            text,
            character_voice=voice,
            rvc_character_voice=rvc_voice,
            rvc_character_pitch=rvc_pitch,
        )

    async def generate_stream(self,
                              text: str,
                              voice: str | None = None,
                              ) -> AsyncIterator[bytes]:
        async for chunk in self.driver.generate_stream(
            text,
            character_voice=voice,
        ):
            yield chunk
