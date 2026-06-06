from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import LlmProvider


class LlmConnectionProfile(BaseModel):
    """
    A configuration profile for a LLM provider.
    """
    provider: LlmProvider = Field(
        ...,
        description="The LLM provider.",
    )
