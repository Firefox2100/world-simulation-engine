from pydantic import BaseModel, ConfigDict, Field


class ActionSuggestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[str] = Field(
        min_length=3,
        max_length=5,
        description=(
            "Free-text suggestions for the user's next action, about 10-30 words each. "
            "These are not structured actions; the user may edit them before sending."
        ),
    )
