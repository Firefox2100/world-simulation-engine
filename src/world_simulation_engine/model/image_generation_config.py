from uuid import uuid4
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ImageGenerationMode


class ImageGenerationConfig(BaseModel):
    """
    Per-simulation configuration for automatically triggering image generation after a turn.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the configuration",
    )
    mode: ImageGenerationMode = Field(
        ImageGenerationMode.MANUAL,
        description="manual: no auto generation. auto: a deterministic/LLM significance check decides per turn. "
                    "always: every turn generates images.",
    )
    fallback_turns: int = Field(
        10,
        ge=1,
        description="In auto mode, force a generation if this many consecutive turns passed without one, "
                    "regardless of the significance check.",
    )
