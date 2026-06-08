from enum import StrEnum
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


from world_simulation_engine.misc.enums import WorldEntryRecallType


class CommitPolicy(StrEnum):
    COMMIT_IF_DISCOVERED = "commit_if_discovered"
    COMMIT_IF_SUCCEEDED = "commit_if_succeeded"
    COMMIT_HIDDEN_IF_NEEDED = "commit_hidden_if_needed"
    RESOLVER_DECIDES = "resolver_decides"


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
    resolver_policy: Literal[
        "resolver_decides",
        "commit_if_user_action_succeeds",
        "commit_if_npc_action_succeeds",
        "commit_if_discovered",
        "discard_if_action_fails",
    ] = "resolver_decides"


class ActivationDecision(BaseModel):
    character_id: int
    character_name: str
    activate: bool
    priority: int = Field(ge=0, le=100)
    reason_for_system: str
    private_motive_used: bool = False


class DirectorOutput(BaseModel):
    scene_focus: str

    activations: list[ActivationDecision]
    active_character_ids: list[int]
    inactive_character_ids: list[int]

    pending_generated_proposals: list[PendingGeneratedProposal] = Field(default_factory=list)

    resolver_instructions: list[str] = Field(default_factory=list)
    narrator_constraints: list[str] = Field(default_factory=list)

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
