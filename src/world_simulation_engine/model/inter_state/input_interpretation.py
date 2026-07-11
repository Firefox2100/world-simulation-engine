from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

from .action_proposal import ProposedAction


class UserActionSequenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["action"] = "action"
    action: ProposedAction
    source_text: str = Field(
        description="The exact source span corresponding to this proposed action.",
    )


class OOCCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["ooc"] = "ooc"
    command_text: str = Field(
        description="Text inside the OOC marker, excluding the [/OOC: and closing ].",
    )
    normalized_intent: str = Field(
        description=(
            "Brief interpretation of what the user wants the system to do, "
            "without executing it."
        ),
    )
    source_text: str = Field(
        description="The complete original OOC marker including delimiters.",
    )


InputSequenceItem = Annotated[
    UserActionSequenceItem | OOCCommand,
    Field(discriminator="type"),
]


class InputInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InputSequenceItem] = Field(
        description="All interpreted actions and OOC commands in exact source order.",
    )
    unparsed_text: list[str] = Field(
        default_factory=list,
        description="Source fragments that could not be safely classified or converted.",
    )
    parser_notes: list[str] = Field(
        default_factory=list,
        description=(
            "Brief diagnostic notes about ambiguity or assumptions. "
            "Do not include hidden chain-of-thought."
        ),
    )
