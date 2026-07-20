from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from world_simulation_engine.misc.enums import SceneCoordinationProblemType, SceneCoordinationStatus

from .action_proposal import ActionProposal, ProposedAction


class SceneActionReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_reference_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        normalized.pop("label", None)
        return normalized

    actor_id: str
    proposal_index: int = Field(
        default=0,
        ge=0,
        description="Selected proposal sequence index: 0 is primary, 1+ are backup proposals.",
    )
    action_index: int = Field(ge=0)


class ActionCandidateSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        normalized.setdefault("proposal_index", 0)
        normalized.setdefault("action_index", 0)
        return normalized

    proposal_index: int = Field(
        default=0,
        ge=0,
        description="Candidate proposal sequence index: 0 is primary, 1+ are backup proposals.",
    )

    action_index: int = Field(
        default=0,
        ge=0,
        description="Legacy field retained for compatibility; sequence candidates start at action_index 0.",
    )
    actions: list[ProposedAction] = Field(
        default_factory=list,
        description=(
            "A complete validator-approved proposal sequence. These actions must be accepted/rejected as an "
            "ordered sequence; they are not individual alternatives to splice into another proposal."
        ),
    )


class CharacterActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    actions: list[ProposedAction] = Field(default_factory=list)
    action_proposals: list[ActionProposal] = Field(
        default_factory=list,
        description=(
            "Original action proposals, preserving primary actions and backup proposals. "
            "This is context only; the coordinator should use candidate_sets for validator-approved sequences."
        ),
    )
    candidate_sets: list[ActionCandidateSet] = Field(
        default_factory=list,
        description=(
            "Allowed alternatives for each action index. Try these before declaring that a character must rework."
        ),
    )
    is_reaction: bool = Field(
        False,
        description="Whether these actions were proposed as a reaction to a previous coordination problem.",
    )
    replaces_from_index: int | None = Field(
        default=None,
        ge=0,
        description=(
            "For reactions, the original action index this reaction replaces from. "
            "The reaction must not be longer than the replaced suffix."
        ),
    )


class ReactionHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    action_signature: str = Field(
        description="Stable signature or compact summary of a previously proposed reaction.",
    )
    count: int = Field(
        ge=1,
        description="How many times this actor has proposed the same reaction in this scene.",
    )


class AcceptedSceneAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_action_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        action_keys = {
            "type",
            "label",
            "target_ids",
            "utterance",
            "intended_duration_seconds",
            "interruptible",
            "interruption_triggers",
            "required_preconditions",
            "expected_effects",
        }

        if "action" not in normalized:
            if isinstance(normalized.get("candidate_data"), dict):
                normalized["action"] = normalized.pop("candidate_data")
            else:
                flat_action = {
                    key: normalized.pop(key)
                    for key in list(action_keys)
                    if key in normalized
                }
                if flat_action:
                    normalized["action"] = flat_action
        else:
            normalized.pop("candidate_data", None)

        if "description" in normalized and "summary" not in normalized:
            normalized["summary"] = normalized.pop("description")
        else:
            normalized.pop("description", None)

        for field_name in ("start_offset_seconds", "end_offset_seconds"):
            value = normalized.get(field_name)
            if isinstance(value, float):
                normalized[field_name] = int(round(value))

        if "action" in normalized and isinstance(normalized["action"], dict):
            action = dict(normalized["action"])
            duration = normalized.get("end_offset_seconds", 0) - normalized.get("start_offset_seconds", 0)
            if "label" not in action and isinstance(normalized.get("summary"), str):
                action["label"] = (
                    normalized["summary"]
                    .lower()
                    .replace("'", "")
                    .replace('"', "")
                    .replace(".", "")
                    .replace(",", "")
                    .replace(" ", "_")
                )[:80] or "accepted_action"
            if "intended_duration_seconds" not in action and duration > 0:
                action["intended_duration_seconds"] = duration
            normalized["action"] = action

        return normalized

    actor_id: str
    proposal_index: int = Field(
        default=0,
        ge=0,
        description="Accepted proposal sequence index: 0 is primary, 1+ are backup proposals.",
    )
    action_index: int = Field(ge=0)
    action: ProposedAction
    start_offset_seconds: int = Field(ge=0)
    end_offset_seconds: int = Field(ge=0)
    summary: str = Field(
        description="Brief statement of what is accepted as having happened.",
    )


class PendingSceneAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_action_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        action_keys = {
            "type",
            "label",
            "target_ids",
            "utterance",
            "intended_duration_seconds",
            "interruptible",
            "interruption_triggers",
            "required_preconditions",
            "expected_effects",
        }

        if "action" not in normalized:
            if isinstance(normalized.get("candidate_data"), dict):
                normalized["action"] = normalized.pop("candidate_data")
            else:
                flat_action = {
                    key: normalized.pop(key)
                    for key in list(action_keys)
                    if key in normalized
                }
                if flat_action:
                    normalized["action"] = flat_action
        else:
            normalized.pop("candidate_data", None)

        return normalized

    actor_id: str
    proposal_index: int = Field(
        default=0,
        ge=0,
        description="Pending proposal sequence index: 0 is primary, 1+ are backup proposals.",
    )
    action_index: int = Field(ge=0)
    action: ProposedAction
    reason: str = Field(
        description="Why this action is pending rather than accepted.",
    )


class SceneCoordinationProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_time_offset(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        problem_type = normalized.get("type")
        if problem_type == "simultaneous_interruption_contention":
            normalized["type"] = SceneCoordinationProblemType.INTERRUPTION

        time_offset = normalized.get("time_offset_seconds")
        if isinstance(time_offset, float):
            normalized["time_offset_seconds"] = int(round(time_offset))
        return normalized

    type: SceneCoordinationProblemType
    time_offset_seconds: int = Field(
        ge=0,
        description="First point in scene time where the problem occurs.",
    )
    involved_actor_ids: list[str] = Field(default_factory=list)
    involved_actions: list[SceneActionReference] = Field(default_factory=list)
    description: str
    needs_user_decision: bool
    actors_to_react: list[str] = Field(
        default_factory=list,
        description="Non-user actors that should be asked to rework/react before coordination continues.",
    )
    resolver_required: bool = Field(
        False,
        description="Whether a later specialized resolver is needed for the contested action.",
    )


class SceneCoordinationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_wrapper_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        for wrapper_key in ("scene_coordination", "scene_coordination_result", "coordination_result", "result"):
            if wrapper_key in normalized and isinstance(normalized[wrapper_key], dict):
                normalized = dict(normalized[wrapper_key])
                break

        if normalized.get("type") == "SceneCoordinationResult":
            normalized.pop("type")

        coordinator_notes = normalized.get("coordinator_notes")
        if isinstance(coordinator_notes, str):
            normalized["coordinator_notes"] = [coordinator_notes]
        elif coordinator_notes is None and "coordinator_notes" in normalized:
            normalized["coordinator_notes"] = []

        if "summary" in normalized:
            summary = normalized.pop("summary")
            notes = list(normalized.get("coordinator_notes") or [])
            if isinstance(summary, str) and summary:
                notes.append(summary)
            normalized["coordinator_notes"] = notes

        return normalized

    status: SceneCoordinationStatus
    accepted_actions: list[AcceptedSceneAction] = Field(default_factory=list)
    problem: SceneCoordinationProblem | None = None
    pending_actions: list[PendingSceneAction] = Field(default_factory=list)
    stopped_reason: str | None = None
    coordinator_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )
