from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from world_simulation_engine.misc.enums import EventInvolvement, IntentHorizon, IntentStatus, IntentType, \
    MemoryStance, MemorySupportType, Salience


class MemoryCharacterLinkProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str
    confidence: float = Field(ge=0, le=1)
    salience: Salience
    stance: MemoryStance
    behavioural_relevance: str | None = None


class EventInvolvementProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str
    involvement: EventInvolvement


class ProposedEventCreation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["create_event"] = "create_event"
    proposed_id: str | None = None
    name: str
    summary: str
    turn_ids: list[str] = Field(default_factory=list)
    involved_characters: list[EventInvolvementProposal] = Field(default_factory=list)
    reason: str


class ProposedTurnEventLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["link_turn_to_event"] = "link_turn_to_event"
    event_id: str
    turn_id: str
    reason: str


class ProposedEventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_event"] = "update_event"
    event_id: str
    name: str | None = None
    summary: str | None = None
    involved_characters: list[EventInvolvementProposal] = Field(default_factory=list)
    reason: str


class ProposedMemoryCreation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["create_memory"] = "create_memory"
    proposed_id: str | None = None
    event_id: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    support_type: MemorySupportType
    character_links: list[MemoryCharacterLinkProposal] = Field(default_factory=list)
    reason: str


class ProposedExistingMemoryLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["link_existing_memory"] = "link_existing_memory"
    memory_id: str
    character_link: MemoryCharacterLinkProposal
    reason: str


class ProposedIntentCreation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["create_intent"] = "create_intent"
    proposed_id: str | None = None
    character_id: str
    intent_type: IntentType
    name: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    priority: float = Field(ge=0, le=1)
    urgency: float = Field(ge=0, le=1)
    status: IntentStatus
    desired_state: str | None = None
    success_conditions: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    maintenance_conditions: list[str] = Field(default_factory=list)
    deadline: datetime | None = None
    horizon: IntentHorizon
    constraints: list[str] = Field(default_factory=list)
    current_plan: list[str] = Field(default_factory=list)
    next_action_biases: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    created_by_event_id: str | None = None
    reason: str


class ProposedIntentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["update_intent"] = "update_intent"
    intent_id: str
    status: IntentStatus | None = None
    priority: float | None = Field(default=None, ge=0, le=1)
    urgency: float | None = Field(default=None, ge=0, le=1)
    current_plan: list[str] | None = None
    next_action_biases: list[str] | None = None
    blockers: list[str] | None = None
    open_threads: list[str] | None = None
    event_id: str | None = None
    event_relationship: Literal["contributes_to", "creates"] | None = None
    reason: str


class ProposedNoAbstractChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["no_abstract_change"] = "no_abstract_change"
    reason: str


MemorySummaryOperation = Annotated[
    ProposedEventCreation
    | ProposedTurnEventLink
    | ProposedEventUpdate
    | ProposedMemoryCreation
    | ProposedExistingMemoryLink
    | ProposedIntentCreation
    | ProposedIntentUpdate
    | ProposedNoAbstractChange,
    Field(discriminator="type"),
]


class MemorySummaryProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def infer_missing_operation_types(cls, value: Any) -> Any:
        """Repair discriminator omissions that are unambiguous from operation fields."""
        if not isinstance(value, dict) or not isinstance(value.get("operations"), list):
            return value

        inferred_operations = []
        for operation in value["operations"]:
            if not isinstance(operation, dict) or operation.get("type"):
                inferred_operations.append(operation)
                continue

            inferred_type = cls._infer_operation_type(operation)
            inferred_operations.append(
                {"type": inferred_type, **operation}
                if inferred_type else operation
            )
        return {**value, "operations": inferred_operations}

    @staticmethod
    def _infer_operation_type(operation: dict[str, Any]) -> str | None:
        fields = set(operation)
        if {"character_id", "intent_type", "horizon"} <= fields:
            return "create_intent"
        if {"name", "summary", "turn_ids", "involved_characters"} <= fields:
            return "create_event"
        if {"event_id", "turn_id"} <= fields:
            return "link_turn_to_event"
        if {"memory_id", "character_link"} <= fields:
            return "link_existing_memory"
        if "intent_id" in fields:
            return "update_intent"
        if {"event_id", "support_type", "character_links"} <= fields:
            return "create_memory"
        if "event_id" in fields and ({"name", "summary", "involved_characters"} & fields):
            return "update_event"
        if fields <= {"reason"} and "reason" in fields:
            return "no_abstract_change"
        return None

    operations: list[MemorySummaryOperation] = Field(default_factory=list)
    summarizer_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )
