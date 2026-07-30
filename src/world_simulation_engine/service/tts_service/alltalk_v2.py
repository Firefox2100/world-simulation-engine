import asyncio
from typing import Any, AsyncIterator
from httpx import AsyncClient, Timeout

from .tts_result import TtsFileResult

# TTS generation is a single synchronous call that blocks until the audio is fully rendered
# server-side - httpx's 5s default read timeout is routinely too short for real narration-length
# text, especially under concurrent GPU contention (see WSE_TTS_MAX_CONCURRENCY).
_REQUEST_TIMEOUT = Timeout(10.0, read=120.0)


class TtsAllTalkV2:
    def __init__(self,
                 base_url: str | None = None,
                 language: str | None = None,
                 text_filtering: str | None = None,
                 text_not_inside: str | None = None,
                 narrator_enabled: bool | None = None,
                 narrator_voice: str | None = None,
                 rvc_narrator_voice: str | None = None,
                 rvc_narrator_pitch: int | None = None,
                 output_file_timestamp: bool | None = None,
                 autoplay: bool | None = None,
                 autoplay_volume: float | None = None,
                 speed: float | None = None,
                 pitch: int | None = None,
                 temperature: float | None = None,
                 repetition_penalty: float | None = None,
                 ):
        self._base_url = base_url.strip("/") if base_url else "http://localhost:7851"
        self._language = language
        self._text_filtering = text_filtering
        self._text_not_inside = text_not_inside
        self._narrator_enabled = narrator_enabled
        self._narrator_voice = narrator_voice
        self._rvc_narrator_voice = rvc_narrator_voice
        self._rvc_narrator_pitch = rvc_narrator_pitch
        self._output_file_timestamp = output_file_timestamp
        self._autoplay = autoplay
        self._autoplay_volume = autoplay_volume
        self._speed = speed
        self._pitch = pitch
        self._temperature = temperature
        self._repetition_penalty = repetition_penalty

        self._client = AsyncClient(base_url=self._base_url, timeout=_REQUEST_TIMEOUT)

    async def get_status(self) -> dict[str, Any]:
        """
        Fetch AllTalk's live, currently-loaded engine/model and capability flags, plus the voices and RVC
        voices actually present on the server. This app never switches AllTalk's own engine/model - it only
        reads this to know which inference-time parameters are valid and which voices exist, so config
        editors can be driven by what the server actually has instead of a guessed/stale list.
        """
        settings_response, voices_response, rvc_response = await asyncio.gather(
            self._client.get("/api/currentsettings"),
            self._client.get("/api/voices"),
            self._client.get("/api/rvcvoices"),
        )
        settings_response.raise_for_status()
        voices_response.raise_for_status()
        rvc_response.raise_for_status()

        settings = settings_response.json()
        voices = voices_response.json()
        rvc_voices = rvc_response.json()

        return {
            "engine": settings.get("current_engine_loaded"),
            "model": settings.get("current_model_loaded"),
            "models_available": [
                model["name"] for model in settings.get("models_available", []) if model.get("name")
            ],
            "languages_capable": bool(settings.get("languages_capable")),
            "temperature_capable": bool(settings.get("temperature_capable")),
            "repetition_penalty_capable": bool(settings.get("repetitionpenalty_capable")),
            "generation_speed_capable": bool(settings.get("generationspeed_capable")),
            "voices": voices.get("voices", []),
            "rvc_voices": rvc_voices.get("rvcvoices", []),
        }

    @staticmethod
    def _bool_str(value: bool) -> str:
        return "true" if value else "false"

    def _generation_payload(self,
                            text: str,
                            character_voice: str | None,
                            language: str | None,
                            output_file_name: str | None,
                            rvc_character_voice: str | None,
                            rvc_character_pitch: int | None,
                            ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text_input": text,
        }

        resolved_language = language if language is not None else self._language

        if character_voice is not None:
            payload["character_voice_gen"] = character_voice
        if resolved_language is not None:
            payload["language"] = resolved_language
        if output_file_name is not None:
            payload["output_file_name"] = output_file_name
        if rvc_character_voice is not None:
            payload["rvccharacter_voice_gen"] = rvc_character_voice
        if rvc_character_pitch is not None:
            payload["rvccharacter_pitch"] = rvc_character_pitch
        if self._text_filtering is not None:
            payload["text_filtering"] = self._text_filtering
        if self._text_not_inside is not None:
            payload["text_not_inside"] = self._text_not_inside
        if self._narrator_enabled is not None:
            payload["narrator_enabled"] = self._bool_str(self._narrator_enabled)
        if self._narrator_voice is not None:
            payload["narrator_voice_gen"] = self._narrator_voice
        if self._rvc_narrator_voice is not None:
            payload["rvcnarrator_voice_gen"] = self._rvc_narrator_voice
        if self._rvc_narrator_pitch is not None:
            payload["rvcnarrator_pitch"] = self._rvc_narrator_pitch
        if self._output_file_timestamp is not None:
            payload["output_file_timestamp"] = self._bool_str(self._output_file_timestamp)
        if self._autoplay is not None:
            payload["autoplay"] = self._bool_str(self._autoplay)
        if self._autoplay_volume is not None:
            payload["autoplay_volume"] = self._autoplay_volume
        if self._speed is not None:
            payload["speed"] = self._speed
        if self._pitch is not None:
            payload["pitch"] = self._pitch
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        if self._repetition_penalty is not None:
            payload["repetition_penalty"] = self._repetition_penalty

        return payload

    async def generate_file(self,
                            text: str,
                            *,
                            character_voice: str | None = None,
                            language: str | None = None,
                            output_file_name: str | None = None,
                            rvc_character_voice: str | None = None,
                            rvc_character_pitch: int | None = None,
                            ) -> TtsFileResult:
        payload = self._generation_payload(
            text, character_voice, language, output_file_name, rvc_character_voice, rvc_character_pitch,
        )

        response = await self._client.post("/api/tts-generate", data=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("status") != "generate-success":
            raise RuntimeError(f"AllTalk TTS generation failed: {result}")

        output_file_url = result.get("output_file_url")
        if not output_file_url:
            raise RuntimeError(f"AllTalk TTS response did not include an output_file_url: {result}")

        audio_response = await self._client.get(output_file_url)
        audio_response.raise_for_status()

        return TtsFileResult(
            audio=audio_response.content,
            content_type=audio_response.headers.get("content-type", "audio/wav"),
            source_url=f"{self._base_url}{output_file_url}",
            cache_url=f"{self._base_url}{result['output_cache_url']}" if result.get("output_cache_url") else None,
        )

    async def generate_stream(self,
                              text: str,
                              *,
                              character_voice: str | None = None,
                              language: str | None = None,
                              output_file_name: str | None = None,
                              ) -> AsyncIterator[bytes]:
        # AllTalk's streaming endpoint has no RVC pipeline (see AllTalk V2 docs), so it only ever takes
        # voice/language/output_file - rvc_character_voice/rvc_character_pitch are file-mode only.
        resolved_language = language if language is not None else self._language

        if character_voice is None:
            raise ValueError("A character voice must be configured or passed to stream TTS audio")
        if resolved_language is None:
            raise ValueError("A language must be configured or passed to stream TTS audio")

        params = {
            "text": text,
            "voice": character_voice,
            "language": resolved_language,
            "output_file": output_file_name or "stream_output",
        }

        # AllTalk's streaming endpoint only returns audio on GET; POST just queues generation and
        # replies with a small JSON confirmation instead of streaming the audio body.
        async with self._client.stream("GET", "/api/tts-generate-streaming", params=params) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk
