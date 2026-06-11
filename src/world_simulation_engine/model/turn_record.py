from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import WorldEntryRecallType, CommitPolicy, TurnType


class ProposedWorldEntry(BaseModel):
    temp_id: str
    scope: list[int]
    content: str
    visibility: str
    confidence: float = Field(ge=0.0, le=1.0)
    narration_permission: str
    recall_type: WorldEntryRecallType
    keywords: Optional[list[dict]] = None
    chained_ids: Optional[list[int]] = None
    semantic_instruction: Optional[str] = None
    reason: str
    commit_policy: CommitPolicy = CommitPolicy.RESOLVER_DECIDES


class ProposedEntity(BaseModel):
    temp_id: str
    name: str
    type: str
    description: str
    status: str
    interactions: list[str]
    reason: str
    commit_policy: CommitPolicy = CommitPolicy.RESOLVER_DECIDES


class ProposedLocation(BaseModel):
    temp_id: str
    primary_location: str
    detailed_location: str
    scene: str
    description: str
    attributes: dict[str, list[str]] = Field(default_factory=dict)
    stats: dict[str, float] = Field(default_factory=dict)
    entities: list[ProposedEntity] = Field(default_factory=list)
    reason: str
    commit_policy: CommitPolicy = CommitPolicy.RESOLVER_DECIDES


class ProposedItem(BaseModel):
    temp_id: str
    name: str
    description: str
    quality: Optional[str] = None
    quantity: int = 1
    unique: bool = True
    proposed_owner_id: Optional[int] = None
    proposed_location_id: Optional[int] = None
    reason: str
    commit_policy: CommitPolicy = CommitPolicy.RESOLVER_DECIDES


class PendingGeneratedProposal(BaseModel):
    tool_name: str
    trigger: str
    result: dict[str, Any]
    intended_use: str


class ActivationDecision(BaseModel):
    character_id: int
    character_name: str
    activate: bool
    priority: int = Field(ge=0, le=100)
    reason: str
    private_motive_used: bool = False


class DirectorOutput(BaseModel):
    scene_focus: str

    activations: list[ActivationDecision]

    wait_for_user: bool = False
    reason_to_wait: str | None = None

    director_notes: str = ""


class CharacterBriefing(BaseModel):
    character_id: int
    character_name: str

    scene_context: str
    recent_context: str
    known_relevant_facts: str
    immediate_situation: str

    instruction: str
    available_interactions: list[str] = Field(default_factory=list)

    relevant_task_ids: list[int] = Field(default_factory=list)
    relevant_world_entry_ids: list[int] = Field(default_factory=list)

    constraints: list[str] = Field(default_factory=list)


class BriefingOutput(BaseModel):
    briefings: list[CharacterBriefing]
    notes: str = ""


class CharacterActionOutput(BaseModel):
    character_id: int
    character_name: str

    intent: str
    action_type: Literal[
        "speak",
        "move",
        "inspect",
        "manipulate_entity",
        "use_item",
        "give_item",
        "take_item",
        "observe",
        "wait",
        "leave_scene",
        "custom",
    ]

    target_character_ids: list[int] = Field(default_factory=list)
    target_entity_ids: list[int] = Field(default_factory=list)
    target_location_id: int | None = None
    target_item_ids: list[int] = Field(default_factory=list)

    method: str
    visible_behavior: str

    spoken_intent: str | None = None

    urgency: int = Field(ge=0, le=100)
    persistence: int = Field(ge=0, le=100)

    expected_outcome: str
    fallback_if_blocked: str | None = None

    uses_private_knowledge: bool = False
    private_reason_for_system: str | None = None

    constraints_for_resolver: list[str] = Field(default_factory=list)
    notes: str = ""


class ResolvedAction(BaseModel):
    actor_id: int
    actor_name: str

    original_intent: str
    final_status: Literal[
        "succeeded",
        "partially_succeeded",
        "failed",
        "blocked",
        "delayed",
        "invalid",
        "cancelled",
    ]

    resolved_order: int | None = None

    visible_result: str
    private_result_for_actor: str | None = None

    failure_reason: str | None = None
    blocking_actor_id: int | None = None
    blocking_entity_id: int | None = None

    state_change_hints: list[str] = Field(default_factory=list)
    world_entry_hints: list[str] = Field(default_factory=list)

    requires_actor_retry: bool = False
    retry_instruction: str | None = None


class ConflictRecord(BaseModel):
    conflict_type: Literal[
        "same_target",
        "mutually_exclusive",
        "interruption",
        "timing",
        "knowledge_invalid",
        "location_invalid",
        "item_unavailable",
        "entity_unavailable",
        "social_conflict",
        "other",
    ]

    involved_character_ids: list[int]
    description: str
    resolution: str
    winner_character_id: int | None = None
    loser_character_ids: list[int] = Field(default_factory=list)


class FailedCharacterRecord(BaseModel):
    character_id: int
    character_name: str
    failed_action_summary: str
    reason: str
    retry_allowed: bool = True
    retry_context: str | None = None


class ResolverOutput(BaseModel):
    mode: Literal["normal_action_resolution", "user_input_validation"]

    accepted: bool
    rejection_reason: str | None = None

    resolved_actions: list[ResolvedAction]
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    failed_characters: list[FailedCharacterRecord] = Field(default_factory=list)

    scene_result_summary: str
    next_round_note: str

    narrator_context: list[str] = Field(default_factory=list)
    state_update_suggestions: list[str] = Field(default_factory=list)
    pending_world_entry_suggestions: list[str] = Field(default_factory=list)

    requires_director_rerun: bool = False
    director_rerun_reason: str | None = None

    notes: str = ""


class TurnRecord(BaseModel):
    id: int = Field(
        ...,
        description="Unique ID for this turn record, generated by the database",
    )
    simulation_id: int = Field(
        ...,
        description="The simulation that this record belongs to."
    )
    turn_number: int = Field(
        ...,
        description="The turn number, starting from 0 (the opening)."
    )
    type: TurnType = Field(
        ...,
        description="The type of this turn."
    )

    director_output: Optional[DirectorOutput] = Field(
        None,
        description="Director output for this turn record."
    )
    briefing_output: Optional[BriefingOutput] = Field(
        None,
        description="Briefing output for this turn record."
    )

    narration: str = Field(
        ...,
        description="The narration for this turn. Can be the user input, or the final AI narration."
    )
