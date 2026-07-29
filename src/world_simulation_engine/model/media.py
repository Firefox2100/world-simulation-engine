from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ImageGenerationType, MediaType
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage


class MediaFile(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the media file",
    )
    type: MediaType = Field(
        ...,
        description="Type of the media file",
    )
    title: Optional[str] = Field(
        None,
        description="Title of the media file",
    )
    hash: str = Field(
        ...,
        description="Hash of the media file",
    )
    filename: str = Field(
        ...,
        description="Filename of the media file, no format suffix",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this media file was created, used to order galleries of generated media",
    )


class PromptMediaFile(MediaFile):
    type: MediaType = Field(
        MediaType.JSON,
        description="Type of the prompt media file",
    )
    prompt_name: str = Field(
        ...,
        description="Name of the prompt in package prompt data",
    )
    language: SupportedLanguage = Field(
        ...,
        description="Language of the prompt",
    )
    component: Optional[ComponentType] = Field(
        None,
        description="Simulator component this prompt is intended for",
    )


class WorkflowMediaFile(MediaFile):
    type: MediaType = Field(
        MediaType.JSON,
        description="Type of the workflow media file",
    )
    workflow_name: str = Field(
        ...,
        description="Name of the workflow in package workflow data",
    )


class GeneratedImageMediaFile(MediaFile):
    type: MediaType = Field(
        MediaType.PNG,
        description="Type of the generated image media file",
    )
    generation_type: ImageGenerationType = Field(
        ...,
        description="What kind of generation produced this image",
    )
    component: ComponentType = Field(
        ...,
        description="The image generator component that produced this image",
    )
    workflow_name: str = Field(
        ...,
        description="Name of the ComfyUI workflow used to produce this image",
    )
    canonical_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Short tag-style keywords for this entity's permanent identity (look, build, hair, "
            "fixed environment features, permanent objects), reused unchanged across generations "
            "to prevent visual drift"
        ),
    )
    canonical_description: str = Field(
        "",
        description="Natural language description of this entity's permanent identity, reused unchanged across generations",
    )
    transient_tags: list[str] = Field(
        default_factory=list,
        description="Short tag-style keywords for this specific image's situational state (clothing, expression, activity, time of day, temporary props)",
    )
    transient_description: str = Field(
        "",
        description="Natural language description of this specific image's pose, relationship, and interaction",
    )
    negative_prompt: Optional[str] = Field(
        None,
        description="Negative prompt used to steer the generation away from unwanted qualities",
    )


class GeneratedVoiceMediaFile(MediaFile):
    type: MediaType = Field(
        MediaType.WAV,
        description="Type of the generated voice media file",
    )
    presentation_block_id: str = Field(
        ...,
        description="The turn presentation block (narration or speech segment) this voice clip was generated for",
    )
    turn_id: str = Field(
        ...,
        description="The turn this voice clip belongs to",
    )
    character_id: Optional[str] = Field(
        None,
        description="The speaking character's id, for a speech segment. None for a narration segment",
    )
    text: str = Field(
        ...,
        description="The exact text that was synthesized",
    )
    voice_reference: Optional[str] = Field(
        None,
        description="The character or narrator voice reference used for this generation",
    )
