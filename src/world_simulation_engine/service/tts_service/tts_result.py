from pydantic import BaseModel, Field


class TtsFileResult(BaseModel):
    """
    The result of a file-based TTS generation call.
    """

    audio: bytes = Field(
        ...,
        description="The generated audio content",
    )
    content_type: str = Field(
        "audio/wav",
        description="MIME type of the generated audio",
    )
    source_url: str | None = Field(
        None,
        description="Absolute URL where the generated audio can be downloaded from the provider, if available",
    )
    cache_url: str | None = Field(
        None,
        description="Absolute URL where the provider caches the generated audio, if available",
    )
