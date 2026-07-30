from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import TtsGenerationMode


class TtsGenerationConfig(BaseModel):
    """
    Per-simulation configuration for automatically triggering TTS generation after a turn, and for the
    narrator's own voice. The narrator isn't a specific character, so it has no CharacterTtsConfig to hold
    its voice - since it is a per-simulation concept, its voice lives here instead of on the shared backend
    config, letting many simulations share one backend while each picking its own narrator voice.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the configuration",
    )
    mode: TtsGenerationMode = Field(
        TtsGenerationMode.MANUAL,
        description="manual: voice must be generated per-segment on demand. auto: every narration/speech "
                    "segment of a turn is voiced automatically once the turn is committed.",
    )
    autoplay_in_browser: bool = Field(
        False,
        description="Whether the frontend should automatically play a turn's narration/speech segments "
                    "back-to-back in the browser once auto-generation finishes, without requiring the "
                    "user to click each segment. Only meaningful when mode is 'auto'. Distinct from "
                    "AllTalkTtsModelConfig.autoplay, which plays audio at the AllTalk server's own "
                    "terminal, not in the user's browser.",
    )
    narrator_voice: Optional[str] = Field(
        None,
        description="Reference to the narrator's voice, used for narration segments and speech with no "
                    "attributed speaker",
    )
    rvc_narrator_voice: Optional[str] = Field(
        None,
        description="RVC voice model for the narrator, as 'folder/file.pth', or 'Disabled' to skip RVC",
    )
    rvc_narrator_pitch: Optional[int] = Field(
        None,
        ge=-24,
        le=24,
        description="Pitch adjustment applied to the narrator RVC voice",
    )
