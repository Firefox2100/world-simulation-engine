from typing import Union

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import ConnectionConfig, SttModelConfigUnion, WhisperCppSttModelConfig

from .whisper_cpp import SttWhisperCpp
from .stt_result import SttTranscriptionResult


class SttService:
    def __init__(self,
                 model_config: SttModelConfigUnion,
                 connection_config: ConnectionConfig,
                 ):
        self._model_config = model_config
        self._connection_config = connection_config

        self._driver: Union[SttWhisperCpp, None] = None

    def _create_driver(self) -> Union[SttWhisperCpp]:
        if self._connection_config.type == ConnectionType.WHISPERCPP:
            if not isinstance(self._model_config, WhisperCppSttModelConfig):
                raise ValueError(
                    "Model config class mismatch: connection config is WHISPERCPP while model config "
                    f"is {type(self._model_config)}"
                )

            return SttWhisperCpp(
                base_url=self._connection_config.base_url,
                language=self._model_config.language,
                translate=self._model_config.translate,
                temperature=self._model_config.temperature,
                temperature_inc=self._model_config.temperature_inc,
                initial_prompt=self._model_config.initial_prompt,
                carry_initial_prompt=self._model_config.carry_initial_prompt,
            )

        raise ValueError(f"Unsupported provider: {self._connection_config.type}")

    @property
    def driver(self) -> Union[SttWhisperCpp]:
        if self._driver is None:
            self._driver = self._create_driver()

        if self._driver is None:
            raise ValueError("Driver is not initialized.")

        return self._driver

    async def transcribe(self,
                         audio: bytes,
                         *,
                         filename: str = "audio.wav",
                         content_type: str | None = None,
                         language: str | None = None,
                         ) -> SttTranscriptionResult:
        return await self.driver.transcribe(
            audio,
            filename=filename,
            content_type=content_type,
            language=language,
        )
