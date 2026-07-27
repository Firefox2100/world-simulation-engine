from pydantic import BaseModel, Field


class SttTranscriptionResult(BaseModel):
    """
    The result of a file-based STT transcription call.
    """

    text: str = Field(
        ...,
        description="The transcribed text",
    )
    language: str | None = Field(
        None,
        description="Language used for the transcription, if known",
    )
