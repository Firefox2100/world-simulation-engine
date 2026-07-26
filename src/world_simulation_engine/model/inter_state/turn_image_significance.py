from pydantic import BaseModel, ConfigDict, Field


class TurnImageSignificanceDecision(BaseModel):
    """Lightweight LLM verdict on whether a turn's scene is worth illustrating with a generated image."""

    model_config = ConfigDict(extra="forbid")

    significant: bool = Field(
        description="Whether this turn's scene changed enough visually to be worth generating an image for.",
    )
    reason: str = Field(
        min_length=1,
        description="Brief one-sentence justification for the verdict.",
    )
