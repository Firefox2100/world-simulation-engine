from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

from .model_config import TtsModelConfigUnion


class CharacterTtsConfig(BaseModel):
    """
    Per-character TTS voice selection.

    Character-specific bits (which voice a character speaks with, and any RVC tuning for that voice) live
    here. Engine/backend/sampling parameters are NOT duplicated per character - they live on the shared
    backend config this character config points to, so many characters can each pick their own voice while
    all sharing the same TTS backend: Character -[:HAS_CONFIG]-> CharacterTtsConfig -[:USE_CONFIG]->
    AllTalk*ModelConfig.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the character TTS config",
    )
    character_voice: Optional[str] = Field(
        None,
        description="Reference to this character's voice. Meaning depends on the backend's engine: a WAV "
                    "sample for voice-cloning engines (xtts, f5tts), a voice model name for piper/vits, or "
                    "a written voice description for parler",
    )
    rvc_character_voice: Optional[str] = Field(
        None,
        description="RVC voice model applied to this character's voice, as 'folder/file.pth', or "
                    "'Disabled' to skip RVC",
    )
    rvc_character_pitch: Optional[int] = Field(
        None,
        ge=-24,
        le=24,
        description="Pitch adjustment applied to this character's RVC voice",
    )
    backend: Optional[TtsModelConfigUnion] = Field(
        None,
        description="The shared TTS backend config this character's voice uses, resolved via USE_CONFIG",
    )
