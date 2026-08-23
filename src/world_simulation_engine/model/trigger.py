"""Trigger: connects a condition (location/variable/semantic, or a boolean combination of the
deterministic ones) to an effect that fires once the condition becomes true.

The defining design constraint (see CLAUDE.md and the trigger feature discussion) is that a
trigger's own existence and content must never leak into a character/narrator/memory prompt while
it is dormant - the only content ever allowed into an LLM prompt is (a) a SemanticCondition's own
`statement`, fed to the trigger_evaluator component, and (b) a *fired* EVENT effect's payload, via
TriggerActivation, injected only into the specific prompt that needs it and only until consumed.
Nothing else - `name`, `description`, a dormant trigger's `effects`, or a GATE's `gate_effect` -
may ever be passed into `_prepare_prompt`/`invoke_structured_with_repair` context data.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .inter_state.state_commit import StateCommitOperation
from ..misc.enums import ComparisonOperator, SemanticConditionMode, TriggerEffectKind, TriggerStatus


class TimeCondition(BaseModel):
    """True while the simulation's current time satisfies the comparison against `value` - time
    is a first-class constraint here (deadlines, scheduled world events, curfews) just like
    location/variable, evaluated the same way: in code, every turn, never touching a prompt."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["time"] = "time"
    operator: ComparisonOperator
    value: datetime


class LocationCondition(BaseModel):
    """True while `character_id` is currently present in `location_id` - or, if `landmark_id` is
    also set, anchored to that specific landmark within the location."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["location"] = "location"
    character_id: str
    location_id: str
    landmark_id: str | None = None


class VariableCondition(BaseModel):
    """True while `owner_id`'s tracked variable named `variable_name` satisfies the comparison."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["variable"] = "variable"
    owner_id: str
    variable_name: str
    operator: ComparisonOperator
    value: str | int | float | bool | list[str]


class SemanticCondition(BaseModel):
    """Free-text condition judged each candidate turn by the trigger_evaluator LLM component
    against recent narration and newly committed memories. Always the sole condition on a
    trigger (see the union types below) - never nested inside all_of/any_of/not, since batching an
    LLM re-check of a fuzzy statement on every turn a sibling deterministic condition merely
    *might* flip is expensive and unreliable on local models; keep semantic and deterministic
    triggers separate instead."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["semantic"] = "semantic"
    mode: SemanticConditionMode = Field(
        default=SemanticConditionMode.FACT,
        description="FACT: has this specific thing become objectively true right now - judged "
                    "against this turn's narration/memories alone. PACING: given the recent story "
                    "trend, would surfacing this feel natural right now - judged against a wider "
                    "recent-summary window, for long-running script threads with no hard moment "
                    "they become true, only better or worse moments to nudge them forward.",
    )
    statement: str = Field(
        min_length=1,
        description="A single, concrete, checkable statement for FACT mode (e.g. 'Alice has "
                    "realized Bob has been lying to her about the letter'), or a description of "
                    "the narrative opening being watched for in PACING mode (e.g. 'a natural "
                    "moment has appeared to hint that Bob was involved in the incident').",
    )
    relevant_character_ids: list[str] = Field(
        default_factory=list,
        description="Characters this condition concerns. Used to decide which turns this "
                    "condition is even a candidate for - it is not re-checked against every "
                    "unrelated turn - and is the only part of a SemanticCondition ever combined "
                    "with other trigger data outside the evaluator prompt itself.",
    )


class AllOfCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["all_of"] = "all_of"
    conditions: list["DeterministicCondition"] = Field(min_length=1)


class AnyOfCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["any_of"] = "any_of"
    conditions: list["DeterministicCondition"] = Field(min_length=1)


class NotCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["not"] = "not"
    condition: "DeterministicCondition"


DeterministicCondition = Annotated[
    TimeCondition | LocationCondition | VariableCondition | AllOfCondition | AnyOfCondition | NotCondition,
    Field(discriminator="type"),
]

TriggerCondition = Annotated[
    TimeCondition | LocationCondition | VariableCondition | AllOfCondition | AnyOfCondition | NotCondition
    | SemanticCondition,
    Field(discriminator="type"),
]


class NarrativeBeatEffect(BaseModel):
    """Queued as a must-include beat for the next narration that involves a relevant character."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["narrative_beat"] = "narrative_beat"
    directive: str = Field(min_length=1, description="What must be woven into the next narration.")
    relevant_character_ids: list[str] = Field(default_factory=list)


class ForcedActionEffect(BaseModel):
    """Queued as a forced next action for one specific non-user character, reusing the same
    forced-action pathway as an out-of-character character_action_guide command."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["forced_action"] = "forced_action"
    character_id: str
    directive: str = Field(min_length=1, description="What the character is forced to do next.")


class StateMutationEffect(BaseModel):
    """Applied immediately as StateCommitOperations, the same apply path used for an
    out-of-character world_state_mutation command - no LLM call, no waiting for the next
    narration."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["state_mutation"] = "state_mutation"
    operations: list[StateCommitOperation] = Field(min_length=1, max_length=6)
    note: str = Field(default="", description="Author-facing note, never shown to any LLM.")


class PerceivedCueEffect(BaseModel):
    """Queued as ambient, non-forcing information for one or more characters to possibly notice.

    Never narrated directly and never a command - delivery goes through PerspectiveResolver
    exactly like any other perceivable entity (an item, a person), which decides per-observer,
    per-turn whether it's salient enough to actually surface this pass. Until then it stays
    pending (see TriggerActivation) rather than being consumed on the first attempt, and expires
    on its own after `expires_after_turns` committed turns rather than lingering forever unread."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["perceived_cue"] = "perceived_cue"
    character_ids: list[str] = Field(min_length=1)
    description: str = Field(
        min_length=1,
        description="The ambient detail a recipient might notice - phrased as something "
                    "observable (a remark, a slip, an object out of place), not as narration or "
                    "a conclusion the character is being told to reach.",
    )
    expires_after_turns: int = Field(
        default=20,
        ge=1,
        description="How many committed turns this stays a pending candidate for PerspectiveResolver "
                    "before it's given up on and retired unconsumed.",
    )


TriggerEffectPayload = Annotated[
    NarrativeBeatEffect | ForcedActionEffect | StateMutationEffect | PerceivedCueEffect,
    Field(discriminator="type"),
]


class GateEffect(BaseModel):
    """What becomes possible once a GATE-kind trigger opens. Deliberately not wired into any
    prompt, validator, or perception mechanism yet - stored only for a future planning/guidance
    feature to consume."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)


class Trigger(BaseModel):
    """A hidden condition -> effect rule. Authored on a World, copied into each Simulation
    created from it (like Character/Intent), and evaluated independently per simulation copy."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str = Field(description="The World or Simulation this trigger belongs to.")
    name: str = Field(min_length=1, description="Author-facing label, never shown to any LLM.")
    description: str = Field(default="", description="Author-facing notes, never shown to any LLM.")

    condition: TriggerCondition
    effect_kind: TriggerEffectKind
    effects: list[TriggerEffectPayload] = Field(
        default_factory=list,
        max_length=3,
        description="Used when effect_kind is EVENT. Empty for GATE.",
    )
    gate_effect: GateEffect | None = Field(
        default=None,
        description="Used when effect_kind is GATE. Null for EVENT.",
    )

    chance: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="EVENT only. When set, a fresh code-rolled check must also succeed on the "
                    "condition's rising edge for the trigger to actually fire ('may happen'). "
                    "Null means unconditional firing on the rising edge ('will happen').",
    )
    repeatable: bool = Field(
        default=False,
        description="EVENT only: whether the trigger can fire again after firing once.",
    )
    cooldown_turns: int | None = Field(
        default=None,
        ge=1,
        description="EVENT + repeatable only: minimum committed turns between firings.",
    )
    reversible: bool = Field(
        default=True,
        description="GATE only: whether the gate can close again if the condition later becomes false.",
    )

    status: TriggerStatus = Field(default=TriggerStatus.DORMANT)
    last_condition_result: bool = Field(
        default=False,
        description="The condition tree's own last evaluated result, used to detect a rising "
                    "edge on the next evaluation. Distinct from `status`.",
    )
    last_fired_turn_id: str | None = None
    last_evaluated_turn_id: str | None = None

    @model_validator(mode="after")
    def _validate_effect_shape(self) -> "Trigger":
        if self.effect_kind == TriggerEffectKind.EVENT:
            if not self.effects:
                raise ValueError("An EVENT trigger needs at least one effect.")
            if self.gate_effect is not None:
                raise ValueError("gate_effect must be null for an EVENT trigger.")
        else:
            if self.effects:
                raise ValueError("effects must be empty for a GATE trigger.")
            if self.gate_effect is None:
                raise ValueError("A GATE trigger needs gate_effect set.")
            if self.chance is not None:
                raise ValueError("chance only applies to EVENT triggers.")
        return self


class TriggerActivation(BaseModel):
    """One firing of an EVENT-kind trigger's single effect, queued for delivery into the next
    relevant narrator/character-simulator call and then consumed - the only place a fired
    trigger's effect content is allowed to reach an LLM prompt. A StateMutationEffect activation
    is recorded already-consumed, since it is applied directly with no prompt injection."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    trigger_id: str
    simulation_id: str
    fired_at_turn_id: str
    effect: TriggerEffectPayload
    consumed: bool = False
    consumed_at_turn_id: str | None = None
