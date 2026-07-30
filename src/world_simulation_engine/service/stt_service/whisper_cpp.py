import asyncio

from httpx import AsyncClient, Timeout

from .stt_result import SttTranscriptionResult

# Transcription is a single synchronous call that blocks until the whole file is decoded
# server-side - httpx's 5s default read timeout is routinely too short for longer audio,
# especially on CPU-only whisper.cpp deployments.
_REQUEST_TIMEOUT = Timeout(10.0, read=300.0)

# whisper.cpp's /inference endpoint reads raw PCM WAV itself and only understands other
# containers (webm/ogg/mp4, whatever a browser's MediaRecorder produces) if the server was
# started with --convert, which most deployments (including the bundled docker-compose one)
# are not. Transcoding client-side to the exact format whisper.cpp expects - 16kHz mono
# 16-bit PCM WAV - here makes the request work against a stock whisper.cpp server regardless
# of what the browser recorded.
_FFMPEG_TIMEOUT = 60.0


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

    @staticmethod
    async def _to_wav(audio: bytes) -> bytes:
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-i", "pipe:0",
                "-f", "wav",
                "-ar", "16000",
                "-ac", "1",
                "-acodec", "pcm_s16le",
                "pipe:1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg is required to convert recorded audio for whisper.cpp but was not found "
                "on PATH"
            ) from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(audio), timeout=_FFMPEG_TIMEOUT
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise RuntimeError("ffmpeg timed out converting audio for whisper.cpp") from exc

        if process.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed to convert audio to WAV: {stderr.decode(errors='replace').strip()}"
            )

        return stdout

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

        wav_audio = await self._to_wav(audio)
        wav_filename = f"{filename.rsplit('.', 1)[0]}.wav" if "." in filename else f"{filename}.wav"
        files = {"file": (wav_filename, wav_audio, "audio/wav")}

        response = await self._client.post("/inference", data=data, files=files)
        response.raise_for_status()
        result = response.json()

        text = result.get("text")
        if text is None:
            raise RuntimeError(f"whisper.cpp server response did not include transcribed text: {result}")

        return SttTranscriptionResult(text=text.strip(), language=resolved_language)
