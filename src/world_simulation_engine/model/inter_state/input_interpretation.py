import re
from typing import Annotated, Any, ClassVar, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .action_proposal import ProposedAction


class UserActionSequenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _ACTION_FIELD_NAMES: ClassVar[set[str]] = {
        "label",
        "target_ids",
        "utterance",
        "intended_duration_seconds",
        "interruptible",
        "interruption_triggers",
        "required_preconditions",
        "expected_effects",
    }

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_action_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("type") != "action":
            return value

        normalized = dict(value)
        misplaced_fields = cls._ACTION_FIELD_NAMES.intersection(normalized)
        if not misplaced_fields:
            return normalized

        action = normalized.get("action")
        if isinstance(action, dict):
            normalized_action = dict(action)
        elif action is None:
            normalized_action = {"type": "other"}
        else:
            return normalized

        for field_name in misplaced_fields:
            normalized_action.setdefault(field_name, normalized.pop(field_name))

        normalized["action"] = normalized_action
        return normalized

    type: Literal["action"] = "action"
    action: ProposedAction
    source_text: str = Field(
        description="The exact source span corresponding to this proposed action.",
    )


class OOCCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _OOC_MARKER_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\[/OOC:(.*?)\]$", flags=re.DOTALL)

    @model_validator(mode="after")
    def validate_exact_ooc_marker(self) -> "OOCCommand":
        match = self._OOC_MARKER_PATTERN.fullmatch(self.source_text)
        if match is None:
            raise ValueError("OOC source_text must be an exact closed [/OOC: ...] marker.")

        marker_command = match.group(1).strip()
        if self.command_text != marker_command:
            raise ValueError("OOC command_text must exactly match the text inside source_text.")

        return self

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
    _SELF_CORRECTION_NOTE_MARKERS: ClassVar[tuple[str, ...]] = (
        "re-evaluating",
        "re-reading",
        "correction:",
        "i will",
        "i should",
        "let's",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_wrapper_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)

        if "items" not in normalized:
            for wrapper_key in ("input_interpretation", "interpretation"):
                if wrapper_key in normalized:
                    normalized["items"] = normalized.pop(wrapper_key)
                    break

        if normalized.get("type") == "InputInterpretation":
            normalized.pop("type")

        if "unparsed_text" in normalized and isinstance(normalized["unparsed_text"], list):
            normalized["unparsed_text"] = [
                fragment
                for fragment in normalized["unparsed_text"]
                if not isinstance(fragment, str) or fragment.strip()
            ]

        if "parser_notes" in normalized and isinstance(normalized["parser_notes"], list):
            normalized["parser_notes"] = [
                note
                for note in normalized["parser_notes"]
                if (
                    not isinstance(note, str)
                    or not any(
                        marker in note.lower()
                        for marker in cls._SELF_CORRECTION_NOTE_MARKERS
                    )
                )
            ]

        return normalized

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
