from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field


class MemoryAtom(BaseModel):
    """
    A memory atom is a recallable minimum unit of character memory, scoped to individual characters
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="The unique identifier of the memory atom",
    )
    summary: str = Field(
        ...,
        description="A brief summary of the memory content"
    )

    keywords: list[str] = Field(
        ...,
        description="A list of keywords associated with the memory content, used for recall",
    )
    embedding: Optional[list[float]] = Field(
        ...,
        description="The embedding of the keywords",
    )
