from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import SceneCoordinationProblemType, SceneCoordinationStatus

from .action_proposal import ActionProposal, ProposedAction


class SceneActionReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    action_index: int = Field(ge=0)


class ActionCandidateSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_index: int = Field(
        ge=0,
        description="The action index these candidates may satisfy.",
    )
    actions: list[ProposedAction] = Field(
        default_factory=list,
        description=(
            "Allowed candidate actions for this action index, in preference order. "
            "The first item is the initially chosen action when it passed validation; later items are backups."
        ),
    )


class CharacterActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    actions: list[ProposedAction] = Field(default_factory=list)
    action_proposals: list[ActionProposal] = Field(
        default_factory=list,
        description=(
            "Original action proposals, preserving chosen_action and alternatives_considered. "
            "This is context only; the coordinator should use candidate_sets for allowed options."
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

    actor_id: str
    action_index: int = Field(ge=0)
    action: ProposedAction
    start_offset_seconds: int = Field(ge=0)
    end_offset_seconds: int = Field(ge=0)
    summary: str = Field(
        description="Brief statement of what is accepted as having happened.",
    )


class PendingSceneAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    action_index: int = Field(ge=0)
    action: ProposedAction
    reason: str = Field(
        description="Why this action is pending rather than accepted.",
    )


class SceneCoordinationProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    status: SceneCoordinationStatus
    accepted_actions: list[AcceptedSceneAction] = Field(default_factory=list)
    problem: SceneCoordinationProblem | None = None
    pending_actions: list[PendingSceneAction] = Field(default_factory=list)
    stopped_reason: str | None = None
    coordinator_notes: list[str] = Field(
        default_factory=list,
        description="Brief diagnostic notes. Do not include hidden chain-of-thought.",
    )
