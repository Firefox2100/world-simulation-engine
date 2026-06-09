from typing import Optional
from pydantic import BaseModel, Field

from .connection_profile import LlmConnectionProfile


class EmbeddingProfile(BaseModel):
    """
    An embedding profile is a configuration to use a specific embedding model with a provider.
    """
    connection: Optional[LlmConnectionProfile] = Field(
        None,
        description="The connection profile to use. This may be None when exported/imported.",
    )
    model: str = Field(
        ...,
        description="The model to use for embedding.",
    )
    dimensions: Optional[int] = Field(
        None,
        description="The dimensionality of the embedding. Some models support setting this.",
    )
    context_window: Optional[int] = Field(
        None,
        description="The context window to use for the embedding. Some provider support setting this.",
    )
