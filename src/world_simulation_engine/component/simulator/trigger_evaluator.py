"""Trigger condition evaluation and effect application.

Two evaluation paths, kept deliberately separate:

- Deterministic conditions (location/variable/all_of/any_of/not) are evaluated in plain code
  against already-committed state, with zero LLM calls - the strongest possible guarantee that a
  dormant trigger's condition never touches a prompt.
- A SemanticCondition (free text) is judged by SemanticTriggerEvaluator, a small bounded LLM
  component that only ever sees the condition's own `statement`, never the rest of the trigger.

TriggerEngine.process_turn is the single entry point `WorldSimulator` calls after a turn's state
commit and derived updates (variable/emotion/relationship/subjective) have all landed, so both
condition types see fully up-to-date state. It fires EVENT effects (immediately for
state_mutation, queued as a TriggerActivation otherwise) and tracks GATE open/closed status - see
model/trigger.py for why a GATE trigger's effect is never itself injected anywhere in this pass.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ComparisonOperator, ComponentType, SemanticConditionMode, \
    TriggerEffectKind, TriggerEffectType, TriggerStatus
from world_simulation_engine.model import (
    AllOfCondition,
    AnyOfCondition,
    ForcedActionEffect,
    LocationCondition,
    MemoryAtom,
    NarrativeBeatEffect,
    NotCondition,
    PerceivedCueEffect,
    SemanticCondition,
    SemanticConditionEvaluationResult,
    StateCommitProposal,
    StateMutationEffect,
    TimeCondition,
    Trigger,
    TriggerActivation,
    VariableCondition,
)
from world_simulation_engine.service import DatabaseService

from .simulator_component import SimulatorComponent
from ..prompt_loader import PromptLoader


class SemanticConditionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    statement: str


class SemanticEvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_time: datetime
    narration: str = ""
    memories: list[MemoryAtom] = Field(default_factory=list)
    candidates: list[SemanticConditionCandidate] = Field(default_factory=list)


class PacingEvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_time: datetime
    recent_summaries: list[str] = Field(default_factory=list)
    candidates: list[SemanticConditionCandidate] = Field(default_factory=list)


class SemanticTriggerEvaluator(SimulatorComponent):
    """Batch-judges a bounded set of SemanticCondition statements. Never receives a trigger's
    name, description, or effect - only each candidate's own `statement`.

    FACT and PACING mode are two different questions with two different prompts, not one prompt
    with a mode switch: FACT checks a specific narrow claim against this turn's own narration/
    memories ("has X become true"); PACING checks a long-running narrative opening against a
    wider recent-history window ("would surfacing something related to X feel earned right now").
    Mixing both framings in a single call risks a local model blending the two kinds of judgment.
    """

    COMPONENT_TYPE = ComponentType.TRIGGER_EVALUATOR
    _MAX_CANDIDATES = 6
    _MAX_MEMORIES = 6
    _MAX_RECENT_SUMMARIES = 10
    _RECENT_TURN_WINDOW = 8

    async def evaluate_fact(
            self,
            *,
            world_id: str,
            simulation_id: str,
            candidates: list[SemanticConditionCandidate],
            narration: str,
            memories: list[MemoryAtom],
    ) -> SemanticConditionEvaluationResult:
        if not candidates:
            return SemanticConditionEvaluationResult(verdicts=[])

        world, simulation = await self._require_world_and_simulation(world_id, simulation_id)

        context = SemanticEvaluationContext(
            simulation_time=simulation.current_time,
            narration=narration,
            memories=memories[:self._MAX_MEMORIES],
            candidates=candidates[:self._MAX_CANDIDATES],
        )
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=world.language,
            prompt_name="trigger_evaluator",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)
        return await llm.invoke_structured_with_repair(
            output_model=SemanticConditionEvaluationResult,
            messages=prompt,
            data=context.model_dump(mode="json"),
            repair_instruction=(
                "Return SemanticConditionEvaluationResult JSON only. Return exactly one verdict "
                "per supplied candidate, preserving candidate_index. Use satisfied=false whenever "
                "the supplied narration/memories don't clearly establish the statement as true - "
                "most candidates stay unsatisfied on most turns, and that is the expected outcome."
            ),
            run_name="trigger_evaluator.evaluate_fact",
        )

    async def evaluate_pacing(
            self,
            *,
            world_id: str,
            simulation_id: str,
            candidates: list[SemanticConditionCandidate],
            relevant_character_ids: list[str],
    ) -> SemanticConditionEvaluationResult:
        if not candidates:
            return SemanticConditionEvaluationResult(verdicts=[])

        world, simulation = await self._require_world_and_simulation(world_id, simulation_id)

        recent_summaries = await self._recent_summaries(
            simulation_id=simulation_id,
            character_ids=relevant_character_ids,
        )
        context = PacingEvaluationContext(
            simulation_time=simulation.current_time,
            recent_summaries=recent_summaries,
            candidates=candidates[:self._MAX_CANDIDATES],
        )
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=world.language,
            prompt_name="trigger_pacing_evaluator",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)
        return await llm.invoke_structured_with_repair(
            output_model=SemanticConditionEvaluationResult,
            messages=prompt,
            data=context.model_dump(mode="json"),
            repair_instruction=(
                "Return SemanticConditionEvaluationResult JSON only. Return exactly one verdict "
                "per supplied candidate, preserving candidate_index. Use satisfied=false whenever "
                "the recent story doesn't clearly support surfacing this right now - most "
                "candidates stay unsatisfied on most turns, and that is the expected outcome, not "
                "a failure to find an opening."
            ),
            run_name="trigger_evaluator.evaluate_pacing",
        )

    async def _require_world_and_simulation(self, world_id: str, simulation_id: str):
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")
        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")
        return world, simulation

    async def _recent_summaries(self, *, simulation_id: str, character_ids: list[str]) -> list[str]:
        """A bounded, deduplicated window of recent memory summaries across every character a
        pacing candidate concerns - the "recent story" a pacing judgment is made against, wider
        than any single turn's own narration/memories."""
        seen_memory_ids: set[str] = set()
        summaries: list[str] = []
        for character_id in character_ids:
            records = await self._db.memory.get_recent_turn_memory_candidates(
                character_id=character_id,
                source_id=simulation_id,
                turn_limit=self._RECENT_TURN_WINDOW,
            )
            for record in records:
                if record.memory.id in seen_memory_ids:
                    continue
                seen_memory_ids.add(record.memory.id)
                summaries.append(record.memory.summary)
                if len(summaries) >= self._MAX_RECENT_SUMMARIES:
                    return summaries
        return summaries


def _compare(operator: ComparisonOperator, current, target) -> bool:
    if operator == ComparisonOperator.EQ:
        return current == target
    if operator == ComparisonOperator.NE:
        return current != target
    if operator == ComparisonOperator.IN:
        return isinstance(target, list) and current in target
    if operator == ComparisonOperator.NOT_IN:
        return isinstance(target, list) and current not in target
    if current is None or target is None:
        return False
    if operator == ComparisonOperator.GT:
        return current > target
    if operator == ComparisonOperator.GTE:
        return current >= target
    if operator == ComparisonOperator.LT:
        return current < target
    if operator == ComparisonOperator.LTE:
        return current <= target
    return False


def _comparable_datetimes(left: datetime, right: datetime) -> tuple[datetime, datetime]:
    """Align tzinfo before comparing so an authored value that omitted its offset doesn't crash
    against the simulation clock's aware datetime (or vice versa)."""
    if left.tzinfo is None and right.tzinfo is not None:
        left = left.replace(tzinfo=right.tzinfo)
    elif left.tzinfo is not None and right.tzinfo is None:
        right = right.replace(tzinfo=left.tzinfo)
    return left, right


@dataclass
class _DeterministicSnapshot:
    """Memoizes DB reads within one evaluation pass so a condition tree referencing the same
    entity from several leaves (e.g. an all_of over two variables on the same owner) only reads
    it once."""

    db: DatabaseService
    current_time: datetime
    positions: dict[str, dict] = field(default_factory=dict)
    _variable_cache: dict = field(default_factory=dict)

    def location_ids(self, character_id: str) -> tuple[str | None, str | None]:
        entry = self.positions.get(character_id)
        if not entry:
            return None, None
        return entry.get("location_id"), entry.get("landmark_id")

    async def variable_value(self, owner_id: str, variable_name: str):
        if owner_id not in self._variable_cache:
            self._variable_cache[owner_id] = await self.db.variable.get_variable_set(owner_id)
        variable_set = self._variable_cache[owner_id]
        if not variable_set:
            return None
        for definition in variable_set.variables:
            if definition.name == variable_name:
                return definition.value
        return None


async def _evaluate_deterministic(condition, snapshot: _DeterministicSnapshot) -> bool:
    if isinstance(condition, TimeCondition):
        current_time, value = _comparable_datetimes(snapshot.current_time, condition.value)
        return _compare(condition.operator, current_time, value)
    if isinstance(condition, LocationCondition):
        location_id, landmark_id = snapshot.location_ids(condition.character_id)
        if location_id != condition.location_id:
            return False
        if condition.landmark_id is not None and landmark_id != condition.landmark_id:
            return False
        return True
    if isinstance(condition, VariableCondition):
        current = await snapshot.variable_value(condition.owner_id, condition.variable_name)
        return _compare(condition.operator, current, condition.value)
    if isinstance(condition, AllOfCondition):
        for sub_condition in condition.conditions:
            if not await _evaluate_deterministic(sub_condition, snapshot):
                return False
        return True
    if isinstance(condition, AnyOfCondition):
        for sub_condition in condition.conditions:
            if await _evaluate_deterministic(sub_condition, snapshot):
                return True
        return False
    if isinstance(condition, NotCondition):
        return not await _evaluate_deterministic(condition.condition, snapshot)
    raise TypeError(f"Not a deterministic condition: {condition!r}")


def _condition_entity_ids(condition) -> set[str]:
    """Every entity id a condition (sub)tree references, used to decide whether a trigger is even
    a candidate for evaluation on a turn that touched a given set of entities. TimeCondition
    references no entity - it always falls through to the empty set below, which _is_relevant
    treats as "always a candidate", since simulation time can advance on any committed turn."""
    if isinstance(condition, LocationCondition):
        return {condition.character_id}
    if isinstance(condition, VariableCondition):
        return {condition.owner_id}
    if isinstance(condition, SemanticCondition):
        return set(condition.relevant_character_ids)
    if isinstance(condition, (AllOfCondition, AnyOfCondition)):
        return {
            entity_id
            for sub_condition in condition.conditions
            for entity_id in _condition_entity_ids(sub_condition)
        }
    if isinstance(condition, NotCondition):
        return _condition_entity_ids(condition.condition)
    return set()


def _activation_character_ids(activation: TriggerActivation) -> set[str]:
    effect = activation.effect
    if isinstance(effect, ForcedActionEffect):
        return {effect.character_id}
    if isinstance(effect, NarrativeBeatEffect):
        return set(effect.relevant_character_ids)
    if isinstance(effect, PerceivedCueEffect):
        return set(effect.character_ids)
    return set()


@dataclass
class TriggerFireResult:
    trigger_id: str
    activations: list[TriggerActivation] = field(default_factory=list)

    def continuation_eligible(self, user_character_id: str | None) -> bool:
        """Whether this firing may warrant one extra foreground round before waiting for the
        user again - false whenever any of its effects name the user's own character, since the
        engine can never propose actions on the user's behalf (see
        _ensure_user_input_only_controls_user_character)."""
        if not user_character_id:
            return True
        return not any(
            user_character_id in _activation_character_ids(activation)
            for activation in self.activations
        )


class TriggerEngine:
    """Evaluates every DORMANT/ACTIVE trigger relevant to one committed turn and applies whatever
    fires. See module docstring for the deterministic/semantic split."""

    _MAX_SEMANTIC_CANDIDATES_PER_TURN = 6

    def __init__(self, database: DatabaseService, prompt_loader: PromptLoader | None = None):
        self._db = database
        self._semantic_evaluator = SemanticTriggerEvaluator(database=database, prompt_loader=prompt_loader)

    async def process_turn(
            self,
            *,
            world_id: str,
            simulation_id: str,
            turn_id: str,
            turn_sequence: int,
            current_time: datetime,
            narration: str,
            memories: list[MemoryAtom],
            candidate_entity_ids: set[str],
    ) -> list[TriggerFireResult]:
        triggers = await self._db.trigger.list_evaluation_candidates(simulation_id)
        if not triggers:
            return []

        relevant_triggers = [
            trigger for trigger in triggers
            if self._is_relevant(trigger, candidate_entity_ids)
        ]
        if not relevant_triggers:
            return []

        referenced_character_ids = sorted({
            entity_id
            for trigger in relevant_triggers
            for entity_id in _condition_entity_ids(trigger.condition)
        })
        positions = await self._db.location.get_location_ids_by_characters(referenced_character_ids)
        snapshot = _DeterministicSnapshot(db=self._db, current_time=current_time, positions=positions)

        deterministic_triggers = [
            trigger for trigger in relevant_triggers
            if not isinstance(trigger.condition, SemanticCondition)
        ]
        semantic_triggers = [
            trigger for trigger in relevant_triggers
            if isinstance(trigger.condition, SemanticCondition)
        ]
        fact_triggers = [
            trigger for trigger in semantic_triggers
            if trigger.condition.mode == SemanticConditionMode.FACT
        ][:self._MAX_SEMANTIC_CANDIDATES_PER_TURN]
        pacing_triggers = [
            trigger for trigger in semantic_triggers
            if trigger.condition.mode == SemanticConditionMode.PACING
        ][:self._MAX_SEMANTIC_CANDIDATES_PER_TURN]

        results = []
        for trigger in deterministic_triggers:
            satisfied = await _evaluate_deterministic(trigger.condition, snapshot)
            result = await self._apply_condition_result(
                trigger=trigger,
                satisfied=satisfied,
                simulation_id=simulation_id,
                turn_id=turn_id,
                turn_sequence=turn_sequence,
            )
            if result:
                results.append(result)

        if fact_triggers:
            evaluation = await self._semantic_evaluator.evaluate_fact(
                world_id=world_id,
                simulation_id=simulation_id,
                candidates=[
                    SemanticConditionCandidate(index=index, statement=trigger.condition.statement)
                    for index, trigger in enumerate(fact_triggers)
                ],
                narration=narration,
                memories=memories,
            )
            results.extend(await self._apply_semantic_verdicts(
                triggers=fact_triggers, evaluation=evaluation, simulation_id=simulation_id,
                turn_id=turn_id, turn_sequence=turn_sequence,
            ))

        if pacing_triggers:
            evaluation = await self._semantic_evaluator.evaluate_pacing(
                world_id=world_id,
                simulation_id=simulation_id,
                candidates=[
                    SemanticConditionCandidate(index=index, statement=trigger.condition.statement)
                    for index, trigger in enumerate(pacing_triggers)
                ],
                relevant_character_ids=sorted({
                    character_id
                    for trigger in pacing_triggers
                    for character_id in trigger.condition.relevant_character_ids
                }),
            )
            results.extend(await self._apply_semantic_verdicts(
                triggers=pacing_triggers, evaluation=evaluation, simulation_id=simulation_id,
                turn_id=turn_id, turn_sequence=turn_sequence,
            ))

        await self._expire_stale_perceived_cues(simulation_id=simulation_id, current_turn_sequence=turn_sequence)

        return results

    async def _apply_semantic_verdicts(
            self,
            *,
            triggers: list[Trigger],
            evaluation: SemanticConditionEvaluationResult,
            simulation_id: str,
            turn_id: str,
            turn_sequence: int,
    ) -> list["TriggerFireResult"]:
        verdict_by_index = {verdict.candidate_index: verdict.satisfied for verdict in evaluation.verdicts}
        results = []
        for index, trigger in enumerate(triggers):
            result = await self._apply_condition_result(
                trigger=trigger,
                satisfied=verdict_by_index.get(index, False),
                simulation_id=simulation_id,
                turn_id=turn_id,
                turn_sequence=turn_sequence,
            )
            if result:
                results.append(result)
        return results

    async def _expire_stale_perceived_cues(self, *, simulation_id: str, current_turn_sequence: int) -> None:
        """Retire PerceivedCueEffect activations nobody has perceived within their own lifetime,
        so an ambient cue nothing ever surfaces (the target character never becomes relevant, or
        PerspectiveResolver never judges it salient) doesn't sit pending forever."""
        pending = await self._db.trigger.list_unconsumed_activations(
            simulation_id=simulation_id,
            effect_type=TriggerEffectType.PERCEIVED_CUE,
        )
        expired_ids = []
        for activation in pending:
            if not isinstance(activation.effect, PerceivedCueEffect):
                continue
            fired_turn = await self._db.turn.get_turn(activation.fired_at_turn_id)
            if not fired_turn:
                continue
            if (current_turn_sequence - fired_turn.sequence) >= activation.effect.expires_after_turns:
                expired_ids.append(activation.id)
        await self._db.trigger.mark_activations_consumed(expired_ids)

    @staticmethod
    def _is_relevant(trigger: Trigger, candidate_entity_ids: set[str]) -> bool:
        referenced = _condition_entity_ids(trigger.condition)
        # A trigger whose condition references no identifiable entity (rare) is always
        # considered relevant rather than silently never evaluated.
        return not referenced or bool(referenced & candidate_entity_ids)

    async def _apply_condition_result(
            self,
            *,
            trigger: Trigger,
            satisfied: bool,
            simulation_id: str,
            turn_id: str,
            turn_sequence: int,
    ) -> TriggerFireResult | None:
        if trigger.effect_kind == TriggerEffectKind.GATE:
            if satisfied:
                new_status = TriggerStatus.ACTIVE
            elif trigger.reversible:
                new_status = TriggerStatus.DORMANT
            else:
                # Non-reversible gate: once open, stays open even if the condition later lapses.
                new_status = TriggerStatus.ACTIVE if trigger.status == TriggerStatus.ACTIVE else TriggerStatus.DORMANT
            await self._db.trigger.update_trigger_runtime_state(
                trigger_id=trigger.id,
                status=new_status,
                last_condition_result=satisfied,
                last_evaluated_turn_id=turn_id,
            )
            return None

        rising_edge = satisfied and not trigger.last_condition_result
        if not rising_edge or not await self._cooldown_elapsed(trigger, turn_sequence):
            await self._db.trigger.update_trigger_runtime_state(
                trigger_id=trigger.id,
                status=trigger.status,
                last_condition_result=satisfied,
                last_evaluated_turn_id=turn_id,
            )
            return None

        if trigger.chance is not None and not self._roll(trigger.chance):
            await self._db.trigger.update_trigger_runtime_state(
                trigger_id=trigger.id,
                status=trigger.status,
                last_condition_result=satisfied,
                last_evaluated_turn_id=turn_id,
            )
            return None

        return await self._fire(trigger=trigger, satisfied=satisfied, simulation_id=simulation_id, turn_id=turn_id)

    async def _cooldown_elapsed(self, trigger: Trigger, turn_sequence: int) -> bool:
        if not trigger.cooldown_turns or not trigger.last_fired_turn_id:
            return True
        last_fired_turn = await self._db.turn.get_turn(trigger.last_fired_turn_id)
        if not last_fired_turn:
            return True
        return (turn_sequence - last_fired_turn.sequence) >= trigger.cooldown_turns

    @staticmethod
    def _roll(chance: float) -> bool:
        return random.random() < chance

    async def _fire(
            self,
            *,
            trigger: Trigger,
            satisfied: bool,
            simulation_id: str,
            turn_id: str,
    ) -> TriggerFireResult:
        stored_activations = []
        for effect in trigger.effects:
            if isinstance(effect, StateMutationEffect):
                await self._apply_state_mutation(effect=effect, simulation_id=simulation_id, turn_id=turn_id)
                activation = TriggerActivation(
                    trigger_id=trigger.id,
                    simulation_id=simulation_id,
                    fired_at_turn_id=turn_id,
                    effect=effect,
                    consumed=True,
                    consumed_at_turn_id=turn_id,
                )
            else:
                activation = TriggerActivation(
                    trigger_id=trigger.id,
                    simulation_id=simulation_id,
                    fired_at_turn_id=turn_id,
                    effect=effect,
                )
            stored = await self._db.trigger.record_activation(activation)
            if stored:
                stored_activations.append(stored)

        new_status = TriggerStatus.DORMANT if trigger.repeatable else TriggerStatus.CONSUMED
        await self._db.trigger.update_trigger_runtime_state(
            trigger_id=trigger.id,
            status=new_status,
            last_condition_result=satisfied,
            last_evaluated_turn_id=turn_id,
            last_fired_turn_id=turn_id,
        )
        return TriggerFireResult(trigger_id=trigger.id, activations=stored_activations)

    async def _apply_state_mutation(self, *, effect: StateMutationEffect, simulation_id: str, turn_id: str) -> None:
        proposal = StateCommitProposal(
            operations=effect.operations,
            committer_notes=[f"Applied by trigger effect: {effect.note}" if effect.note else "Applied by trigger."],
        )
        await self._db.state_commit.apply_state_commit_proposal(
            proposal=proposal,
            source_id=simulation_id,
            turn_id=turn_id,
        )
