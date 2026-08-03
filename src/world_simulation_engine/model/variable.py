"""Arbitrary, sparingly-used tracked attributes on a single entity (health, mana, ...).

One `EntityVariableSet` node holds every tracked variable for one entity (a character, item,
equipment, ...), mirroring how a SillyTavern MVU/Zod variable schema field is typed, defaulted,
described, and bounded - so a card's variable schema can be represented without inventing a new
node per variable.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .inter_state.state_commit import PhysicalEntityType


class VariableValueType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


class VariableDefinition(BaseModel):
    """One tracked attribute: its type, current/default value, and update guidance."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    value_type: VariableValueType
    value: str | int | float | bool
    default_value: str | int | float | bool
    description: str = Field(
        "",
        description="What this variable means and how it should change - sent to the LLM "
                    "proposing updates as the update rule for this variable.",
    )
    minimum: float | None = Field(
        default=None,
        description="Inclusive lower bound, for integer/float variables only.",
    )
    maximum: float | None = Field(
        default=None,
        description="Inclusive upper bound, for integer/float variables only.",
    )
    allowed_values: list[str] = Field(
        default_factory=list,
        description="Non-empty only for enum-like string variables; the closed set of legal values.",
    )

    @staticmethod
    def matches_value_type(candidate, value_type: VariableValueType) -> bool:
        # bool is a subclass of int in Python, so isinstance(x, bool) must be checked explicitly
        # rather than folded into the int/float branches below.
        if value_type == VariableValueType.BOOLEAN:
            return isinstance(candidate, bool)
        if isinstance(candidate, bool):
            return False
        if value_type == VariableValueType.INTEGER:
            return isinstance(candidate, int)
        if value_type == VariableValueType.FLOAT:
            return isinstance(candidate, (int, float))
        return isinstance(candidate, str)

    @model_validator(mode="after")
    def _validate_value_shapes(self) -> "VariableDefinition":
        for field_name, candidate in (("value", self.value), ("default_value", self.default_value)):
            if not self.matches_value_type(candidate, self.value_type):
                raise ValueError(
                    f"VariableDefinition {self.name!r}: {field_name} does not match value_type "
                    f"{self.value_type.value!r}"
                )
        if self.allowed_values and self.value_type != VariableValueType.STRING:
            raise ValueError(
                f"VariableDefinition {self.name!r}: allowed_values only applies to string variables"
            )
        if (self.minimum is not None or self.maximum is not None) and self.value_type not in (
                VariableValueType.INTEGER, VariableValueType.FLOAT,
        ):
            raise ValueError(
                f"VariableDefinition {self.name!r}: minimum/maximum only applies to integer/float variables"
            )
        return self


class EntityVariableSet(BaseModel):
    """All arbitrary tracked variables for one entity, as a single node."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str = Field(description="The World or Simulation this entity - and its variables - belong to.")
    owner_type: PhysicalEntityType
    owner_id: str
    variables: list[VariableDefinition] = Field(default_factory=list)
    last_updated_at: datetime
    version: int = Field(default=1, ge=1)


class ProposedVariableChange(BaseModel):
    """Small local-model output: one variable's new value, grounded in cited evidence."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    new_value: str | int | float | bool
    evidence_memory_ids: list[str] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=1)


class VariableUpdateProposal(BaseModel):
    """Bounded set of variable changes for one entity and one committed turn."""

    model_config = ConfigDict(extra="forbid")

    changes: list[ProposedVariableChange] = Field(default_factory=list, max_length=4)
    updater_notes: list[str] = Field(default_factory=list, max_length=2)


class VariableChangeAudit(BaseModel):
    """Immutable provenance record for one applied variable-set version."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    variable_set_id: str
    source_id: str
    owner_id: str
    turn_id: str
    evidence_memory_ids: list[str] = Field(min_length=1)
    changed_at: datetime
    change_type: Literal["create", "update"]
    previous_version: int | None = None
    new_version: int
    previous_state: dict | None = None
    new_state: dict
