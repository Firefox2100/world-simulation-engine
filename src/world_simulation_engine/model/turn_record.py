from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import WorldEntryRecallType, CommitPolicy, TurnType, SandboxObjectType


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


class ProposedEquipment(BaseModel):
    temp_id: str
    name: str
    description: str
    status: str
    quality: Optional[str] = None
    proposed_owner_id: Optional[int] = None
    proposed_location_id: Optional[int] = None
    reason: str
    commit_policy: CommitPolicy = CommitPolicy.RESOLVER_DECIDES


class ProposedLink(BaseModel):
    source_temp_id: str
    target_temp_id: str
    relationship: str
    reason: str


class ProposedGenerationPackage(BaseModel):
    temp_id: str
    title: str
    package_type: Literal[
        "linked_discovery",
        "location_with_contents",
        "entity_with_clues",
        "item_with_knowledge",
        "equipment_with_knowledge",
        "mixed",
    ]
    summary: str

    locations: list[ProposedLocation] = Field(default_factory=list)
    entities: list[ProposedEntity] = Field(default_factory=list)
    items: list[ProposedItem] = Field(default_factory=list)
    equipments: list[ProposedEquipment] = Field(default_factory=list)
    world_entries: list[ProposedWorldEntry] = Field(default_factory=list)
    links: list[ProposedLink] = Field(default_factory=list)

    reason: str
    commit_policy: CommitPolicy = CommitPolicy.RESOLVER_DECIDES


class PendingGeneratedProposal(BaseModel):
    tool_name: str
    trigger: str
    result: dict[str, Any]
    intended_use: str


class ActivationSources(BaseModel):
    public_state: bool = False
    private_state: bool = False
    public_task: bool = False
    private_task: bool = False
    scene_opportunity: bool = False
    user_input: bool = False


class ActivationDecision(BaseModel):
    character_id: int
    character_name: str
    activate: bool
    priority: int = Field(ge=0, le=100)
    reason: str
    private_motive_used: bool = False
    activation_sources: ActivationSources


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


class CharacterReactionContext(BaseModel):
    character_id: int
    character_name: str

    original_action: CharacterActionOutput
    failure_record: FailedCharacterRecord

    fixed_visible_events: list[str] = Field(default_factory=list)
    fixed_private_events_for_actor: list[str] = Field(default_factory=list)
    relevant_task_ids: list[int] = Field(default_factory=list)
    relevant_world_entry_ids: list[int] = Field(default_factory=list)

    changed_scene_context: str
    immediate_failure_context: str

    retry_number: int = 1
    max_retries_this_round: int = 1

    allowed_reaction_scope: Literal[
        "adjust_original_intent",
        "respond_to_failure",
        "abort_or_wait",
        "any_plausible_reaction",
    ] = "respond_to_failure"

    constraints: list[str] = Field(default_factory=list)


class NarratorResolvedEvent(BaseModel):
    actor_id: int
    actor_name: str
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
    failure_reason: str | None = None
    blocking_actor_id: int | None = None
    blocking_entity_id: int | None = None


class NarratorResolutionView(BaseModel):
    resolved_visible_events: list[NarratorResolvedEvent] = Field(default_factory=list)
    safe_narrator_context: list[str] = Field(default_factory=list)
    scene_result_summary: str = ""
    next_round_note: str = ""


class CommitterPlannedMutation(BaseModel):
    operation: Literal[
        "update_simulation_state",
        "update_character",
        "update_location",
        "update_entity",
        "create_location",
        "create_world_entry",
        "create_task",
        "update_task",
        "update_inventory",
        "create_object",
        "remove_object",
        "accept_generated_proposal",
        "reject_generated_proposal",
        "defer_generated_proposal",
        "noop",
    ]

    args: dict[str, Any] = Field(default_factory=dict)
    reason: str
    source_event: str | None = None


class CommitterMutationPlanOutput(BaseModel):
    plan_summary: str
    mutations: list[CommitterPlannedMutation] = Field(default_factory=list)
    no_changes_needed: bool = False
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    # @model_validator(mode="after")
    # def validate_non_empty_plan(self):
    #     if not self.no_changes_needed and not self.mutations:
    #         raise ValueError(
    #             "CommitterMutationPlanOutput must contain at least one mutation "
    #             "unless no_changes_needed=true."
    #         )
    #
    #     if self.no_changes_needed and self.mutations:
    #         raise ValueError(
    #             "CommitterMutationPlanOutput cannot set no_changes_needed=true "
    #             "while also returning mutations."
    #         )
    #
    #     return self


class SandboxObjectRef(BaseModel):
    object_type: SandboxObjectType
    object_id: int | str


class SandboxMutationRecord(BaseModel):
    mutation_id: str
    operation: Literal[
        "create",
        "update",
        "remove",
        "move",
        "accept_proposal",
        "reject_proposal",
        "defer_proposal",
    ]
    target: SandboxObjectRef | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    source_event: str | None = None


class CommitterValidationOutput(BaseModel):
    complete: bool
    needs_more_changes: bool
    missing_changes: list[str] = Field(default_factory=list)
    questionable_changes: list[str] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    next_instruction: str | None = None


class CommitterFinalOutput(BaseModel):
    simulation_id: int
    ready_to_commit: bool
    round_summary: str
    mutation_log: list[SandboxMutationRecord]
    warnings: list[str] = Field(default_factory=list)

    final_state: dict[str, Any]

    database_patch_preview: list[SandboxMutationRecord]


class SummaryOutput(BaseModel):
    scene_summary: str
    short_term_memory: str
    long_term_memory: str
    active_scene: str | None = None
    open_threads: list[str] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)


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
    proposals: Optional[list[PendingGeneratedProposal]] = Field(
        None,
        description="Generation proposals for this turn record."
    )
    briefing_output: Optional[BriefingOutput] = Field(
        None,
        description="Briefing output for this turn record."
    )

    narration: str = Field(
        ...,
        description="The narration for this turn. Can be the user input, or the final AI narration."
    )
