from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class NarrationBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["narration"]
    text: str = Field(
        ...,
        min_length=1,
        description="Observable narration that is not spoken by a character.",
    )


class SpeechBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["speech"]
    character_id: str = Field(
        ...,
        description="The id of the character who speaks.",
    )
    character_name: str | None = Field(
        default=None,
        description="The display name of the character who speaks, when known.",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Exact character utterance from the accepted action.",
    )


class SpeechAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(
        ge=0,
        description="Zero-based speech anchor index in scene order.",
    )
    character_id: str
    character_name: str | None = None
    text: str = Field(
        ...,
        min_length=1,
        description="Exact character utterance from the accepted action.",
    )
    action_summary: str


class NarrationInsertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int = Field(
        ge=0,
        description=(
            "Insertion slot in the fixed speech sequence. 0 means before speech 0; "
            "1 means between speech 0 and speech 1; len(speech_anchors) means after the last speech."
        ),
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Observable non-verbal narration to insert at this position.",
    )


class NarrationInsertionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insertions: list[NarrationInsertion] = Field(
        default_factory=list,
        description="Optional narration blocks inserted around fixed speech anchors.",
    )


NarrationOutputBlock = Annotated[
    NarrationBlock | SpeechBlock,
    Field(discriminator="type"),
]


class NarrationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks: list[NarrationOutputBlock] = Field(
        default_factory=list,
        description="Visible narration and exact character speech blocks in scene order.",
    )
