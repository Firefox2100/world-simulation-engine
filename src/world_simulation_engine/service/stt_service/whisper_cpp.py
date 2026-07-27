from httpx import AsyncClient, Timeout

from .stt_result import SttTranscriptionResult

# Transcription is a single synchronous call that blocks until the whole file is decoded
# server-side - httpx's 5s default read timeout is routinely too short for longer audio,
# especially on CPU-only whisper.cpp deployments.
_REQUEST_TIMEOUT = Timeout(10.0, read=300.0)


class SttWhisperCpp:
    def __init__(self,
                 base_url: str | None = None,
                 language: str | None = None,
                 translate: bool | None = None,
                 temperature: float | None = None,
                 temperature_inc: float | None = None,
                 initial_prompt: str | None = None,
                 carry_initial_prompt: bool | None = None,
                 ):
        self._base_url = base_url.strip("/") if base_url else "http://localhost:8080"
        self._language = language
        self._translate = translate
        self._temperature = temperature
        self._temperature_inc = temperature_inc
        self._initial_prompt = initial_prompt
        self._carry_initial_prompt = carry_initial_prompt

        self._client = AsyncClient(base_url=self._base_url, timeout=_REQUEST_TIMEOUT)

    @staticmethod
    def _bool_str(value: bool) -> str:
        return "true" if value else "false"

    async def transcribe(self,
                         audio: bytes,
                         *,
                         filename: str = "audio.wav",
                         content_type: str | None = None,
                         language: str | None = None,
                         ) -> SttTranscriptionResult:
        resolved_language = language if language is not None else self._language

        data: dict[str, str] = {"response_format": "json"}
        if resolved_language is not None:
            data["language"] = resolved_language
        if self._translate is not None:
            data["translate"] = self._bool_str(self._translate)
        if self._temperature is not None:
            data["temperature"] = str(self._temperature)
        if self._temperature_inc is not None:
            data["temperature_inc"] = str(self._temperature_inc)
        if self._initial_prompt is not None:
            data["prompt"] = self._initial_prompt
        if self._carry_initial_prompt is not None:
            data["carry_initial_prompt"] = self._bool_str(self._carry_initial_prompt)

        files = {"file": (filename, audio, content_type or "application/octet-stream")}

        response = await self._client.post("/inference", data=data, files=files)
        response.raise_for_status()
        result = response.json()

        text = result.get("text")
        if text is None:
            raise RuntimeError(f"whisper.cpp server response did not include transcribed text: {result}")

        return SttTranscriptionResult(text=text.strip(), language=resolved_language)
