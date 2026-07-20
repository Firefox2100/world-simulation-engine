import json
import re
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal

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
    _MAX_OPERATIONS: ClassVar[int] = 12

    operations: list[MemorySummaryOperation] = Field(default_factory=list)
    summarizer_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_model_output(cls, data: Any) -> Any:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return data

        if not isinstance(data, dict) or not isinstance(data.get("operations"), list):
            return data

        normalized_operations = []
        last_created_event_operation = None
        last_created_event_id = None
        last_created_event_involvements = []
        used_proposed_ids = set()
        operation_types = {
            "create_event",
            "link_turn_to_event",
            "update_event",
            "create_memory",
            "link_existing_memory",
            "create_intent",
            "update_intent",
            "no_abstract_change",
        }

        for raw_operation in data["operations"]:
            if not isinstance(raw_operation, dict):
                normalized_operations.append(raw_operation)
                continue

            operation = dict(raw_operation)
            operation_name = operation.get("name")
            if operation_name in operation_types:
                if operation.get("type") != operation_name:
                    operation["type"] = operation_name
                operation.pop("name", None)

            if operation.get("type") is None:
                operation["type"] = cls._infer_operation_type(operation)

            operation_type = operation.get("type")

            if operation_type == "create_event":
                operation["proposed_id"] = cls._normalize_proposed_id(
                    "evt",
                    operation.get("proposed_id"),
                    operation.get("summary") or operation.get("reason") or "event",
                    used_proposed_ids,
                )
                if not operation.get("name"):
                    operation["name"] = cls._compact_title(
                        operation.get("summary") or operation.get("reason") or "Event"
                    )
                operation["involved_characters"] = cls._normalize_event_involvements(
                    operation.get("involved_characters", [])
                )
                last_created_event_operation = operation
                last_created_event_id = operation.get("proposed_id")
                last_created_event_involvements = operation["involved_characters"]

            elif operation_type == "link_turn_to_event":
                turn_ids = operation.pop("turn_ids", None)
                turn_id = operation.get("turn_id") or cls._extract_uuid(
                    f"{operation.get('summary', '')} {operation.get('reason', '')}"
                )
                operation.pop("summary", None)
                operation.pop("involved_characters", None)

                if (
                    not operation.get("event_id")
                    and last_created_event_operation
                    and (isinstance(turn_ids, list) or turn_id)
                ):
                    event_turn_ids = list(last_created_event_operation.get("turn_ids") or [])
                    for current_turn_id in turn_ids or [turn_id]:
                        if isinstance(current_turn_id, str) and current_turn_id not in event_turn_ids:
                            event_turn_ids.append(current_turn_id)
                    last_created_event_operation["turn_ids"] = event_turn_ids
                    continue

                if not operation.get("event_id") and last_created_event_id:
                    operation["event_id"] = last_created_event_id
                if not operation.get("turn_id") and turn_id:
                    operation["turn_id"] = turn_id
                elif not operation.get("turn_id") and isinstance(turn_ids, list) and turn_ids:
                    operation["turn_id"] = turn_ids[0]
                if not operation.get("event_id") or not operation.get("turn_id"):
                    operation = {
                        "type": "no_abstract_change",
                        "reason": operation.get("reason") or "Skipped incomplete turn-event link proposal.",
                    }

            elif operation_type == "create_memory":
                if not operation.get("event_id") and last_created_event_id:
                    operation["event_id"] = last_created_event_id
                operation = cls._normalize_memory_creation(operation, last_created_event_involvements)
                if not operation.get("event_id"):
                    operation = {
                        "type": "no_abstract_change",
                        "reason": operation.get("reason") or "Skipped memory proposal without an event id.",
                    }
                elif not operation.get("character_links"):
                    operation = {
                        "type": "no_abstract_change",
                        "reason": operation.get("reason") or "Skipped memory proposal without character links.",
                    }
                else:
                    operation["proposed_id"] = cls._normalize_proposed_id(
                        "mem",
                        operation.get("proposed_id"),
                        operation.get("summary") or operation.get("reason") or "memory",
                        used_proposed_ids,
                    )

            elif operation_type == "create_intent":
                involved_characters = operation.pop("involved_characters", None)
                if not operation.get("character_id") and isinstance(involved_characters, list) and involved_characters:
                    first_character = involved_characters[0]
                    if isinstance(first_character, dict):
                        operation["character_id"] = first_character.get("character_id")

                if not operation.get("name"):
                    operation["name"] = cls._compact_title(
                        operation.get("summary") or operation.get("description") or operation.get("reason") or "Intent"
                    )
                operation.setdefault("description", operation.pop("summary", None) or operation["name"])
                operation.setdefault("intent_type", IntentType.QUEST)
                operation.setdefault("priority", 0.5)
                operation.setdefault("urgency", 0.5)
                operation.setdefault("status", IntentStatus.ACTIVE)
                operation.setdefault("horizon", IntentHorizon.SHORT)
                if not operation.get("created_by_event_id") and last_created_event_id:
                    operation["created_by_event_id"] = last_created_event_id
                if not operation.get("character_id"):
                    operation = {
                        "type": "no_abstract_change",
                        "reason": operation.get("reason") or "Skipped intent proposal without a character id.",
                    }
                else:
                    operation["proposed_id"] = cls._normalize_proposed_id(
                        "int",
                        operation.get("proposed_id"),
                        operation.get("summary") or operation.get("name") or operation.get("reason") or "intent",
                        used_proposed_ids,
                    )

            normalized_operations.append(operation)

        normalized_data = dict(data)
        normalized_data["operations"] = normalized_operations[:cls._MAX_OPERATIONS]
        return normalized_data

    @classmethod
    def _normalize_memory_creation(cls,
                                   operation: dict[str, Any],
                                   fallback_involvements: list[Any],
                                   ) -> dict[str, Any]:
        involved_characters = operation.pop("involved_characters", None)
        if not isinstance(involved_characters, list):
            involved_characters = fallback_involvements

        if not operation.get("character_links") and isinstance(involved_characters, list):
            operation["character_links"] = [
                character_link
                for character_link in (
                    cls._memory_link_from_event_involvement(involvement)
                    for involvement in involved_characters
                )
                if character_link is not None
            ]

        if not operation.get("support_type"):
            operation["support_type"] = cls._memory_support_type_from_links(
                operation.get("character_links", [])
            )

        return operation

    @staticmethod
    def _infer_operation_type(operation: dict[str, Any]) -> str | None:
        if "relationship_type" in operation:
            return None

        if (
            "summary" in operation
            and (
                "turn_ids" in operation
                or "involved_characters" in operation
                or "name" in operation
            )
        ):
            return "create_event"

        if "character_links" in operation or "support_type" in operation or "event_id" in operation:
            return "create_memory"

        if "character_id" in operation or "intent_type" in operation or "current_plan" in operation:
            return "create_intent"

        return None

    @staticmethod
    def _memory_link_from_event_involvement(involvement: Any) -> dict[str, Any] | None:
        if not isinstance(involvement, dict) or not involvement.get("character_id"):
            return None

        involvement_type = involvement.get("involvement")
        if involvement_type == EventInvolvement.INFER or involvement_type == "infer":
            stance = MemoryStance.INFER
            confidence = 0.65
        elif involvement_type == EventInvolvement.BELIEVE or involvement_type == "believe":
            stance = MemoryStance.BELIEVE
            confidence = 0.7
        elif involvement_type == EventInvolvement.SUSPECT or involvement_type == "suspect":
            stance = MemoryStance.BELIEVE
            confidence = 0.45
        else:
            stance = MemoryStance.REMEMBER
            confidence = 0.8

        return {
            "character_id": involvement["character_id"],
            "confidence": confidence,
            "salience": Salience.MEDIUM,
            "stance": stance,
        }

    @staticmethod
    def _memory_support_type_from_links(character_links: Any) -> MemorySupportType:
        if not isinstance(character_links, list):
            return MemorySupportType.DIRECT

        inferred_stances = {MemoryStance.INFER, MemoryStance.BELIEVE, MemoryStance.DOUBT, MemoryStance.MISTAKE}
        inferred_stance_values = {stance.value for stance in inferred_stances}
        for link in character_links:
            if isinstance(link, MemoryCharacterLinkProposal):
                stance = link.stance
            elif isinstance(link, dict):
                stance = link.get("stance")
            else:
                continue

            if stance in inferred_stances or str(stance) in inferred_stance_values:
                return MemorySupportType.INFERRED

        return MemorySupportType.DIRECT

    @staticmethod
    def _compact_title(value: str) -> str:
        title = " ".join(value.strip().split())
        if not title:
            return "Untitled"
        first_sentence = title.split(".", 1)[0].strip()
        title = first_sentence or title
        return title[:80].rstrip()

    @staticmethod
    def _default_proposed_id(prefix: str, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return f"{prefix}_{slug[:48].strip('_') or 'proposal'}"

    @classmethod
    def _normalize_proposed_id(cls,
                               prefix: str,
                               proposed_id: Any,
                               fallback: str,
                               used_proposed_ids: set[str],
                               ) -> str:
        if isinstance(proposed_id, str) and proposed_id.startswith(f"{prefix}_"):
            candidate = proposed_id
        else:
            candidate = cls._default_proposed_id(prefix, fallback)

        unique_candidate = candidate
        index = 2
        while unique_candidate in used_proposed_ids:
            unique_candidate = f"{candidate}_{index}"
            index += 1

        used_proposed_ids.add(unique_candidate)
        return unique_candidate

    @staticmethod
    def _extract_uuid(value: str) -> str | None:
        match = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            value,
        )
        return match.group(0) if match else None

    @staticmethod
    def _normalize_event_involvements(value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []

        involvements = []
        for involvement in value:
            if not isinstance(involvement, dict):
                involvements.append(involvement)
                continue

            normalized = dict(involvement)
            if normalized.get("involvement") == "participant":
                normalized["involvement"] = EventInvolvement.PARTICIPATE
            involvements.append(normalized)
        return involvements
