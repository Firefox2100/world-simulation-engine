from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import MessageRole


class PromptMessage(BaseModel):
    role: MessageRole = Field(
        ...,
        description="The role of the message.",
    )
    content: str = Field(
        ...,
        description="The content of the message. Supports Jinja2 templating.",
    )
