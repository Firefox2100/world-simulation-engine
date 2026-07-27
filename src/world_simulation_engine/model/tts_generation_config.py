from uuid import uuid4
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import TtsGenerationMode


class TtsGenerationConfig(BaseModel):
    """
    Per-simulation configuration for automatically triggering TTS generation after a turn.
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
