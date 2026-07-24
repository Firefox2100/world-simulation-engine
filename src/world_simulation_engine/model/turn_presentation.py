"""Non-authoritative renderings attached to canonical turns."""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .turn import Turn


class PresentationBlockType(StrEnum):
    NARRATION = "narration"
    SPEECH = "speech"
    ACTION = "action"
    THOUGHT = "thought"
    SYSTEM_NOTICE = "system_notice"
    MEDIA = "media"


class PresentationCompletion(StrEnum):
    STREAMING = "streaming"
    COMPLETE = "complete"
    FAILED = "failed"


class TurnPresentationBlock(BaseModel):
    """One ordered display block; it never carries simulation authority."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    turn_id: str
    rendering_id: str = Field(default="default", min_length=1, max_length=100)
    locale: str | None = Field(default=None, max_length=35)
    sequence: int = Field(ge=0)
    type: PresentationBlockType
    text: str | None = Field(default=None, max_length=10000)
    speaker_id: str | None = None
    speaker_name: str | None = Field(default=None, max_length=200)
    media_id: str | None = None
    completion: PresentationCompletion = PresentationCompletion.COMPLETE
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_payload(self) -> "TurnPresentationBlock":
        if self.type == PresentationBlockType.MEDIA:
            if not self.media_id:
                raise ValueError("Media presentation blocks require media_id")
        elif not self.text or not self.text.strip():
            raise ValueError("Non-media presentation blocks require text")
        if self.type == PresentationBlockType.SPEECH and not (
                self.speaker_id or self.speaker_name
        ):
            raise ValueError("Speech presentation blocks require speaker attribution")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self


class TurnPresentationRendering(BaseModel):
    """A locale/variant-specific ordered rendering of one canonical turn."""

    model_config = ConfigDict(extra="forbid")

    turn_id: str
    rendering_id: str = Field(default="default", min_length=1, max_length=100)
    locale: str | None = Field(default=None, max_length=35)
    blocks: list[TurnPresentationBlock] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_blocks(self) -> "TurnPresentationRendering":
        sequences = [block.sequence for block in self.blocks]
        if len(sequences) != len(set(sequences)):
            raise ValueError("Presentation block sequences must be unique")
        if sequences and sorted(sequences) != list(range(len(sequences))):
            raise ValueError("Presentation block sequences must be contiguous from zero")
        for block in self.blocks:
            if (
                    block.turn_id != self.turn_id
                    or block.rendering_id != self.rendering_id
                    or block.locale != self.locale
            ):
                raise ValueError("All blocks must belong to the rendering")
        return self


class PresentedTurn(BaseModel):
    """API projection pairing authority with one explicitly non-authoritative rendering."""

    turn: Turn
    rendering_id: str = "default"
    locale: str | None = None
    presentation_blocks: list[TurnPresentationBlock] = Field(default_factory=list)
