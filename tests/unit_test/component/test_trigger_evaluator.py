from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from world_simulation_engine.component.simulator.trigger_evaluator import (
    SemanticConditionCandidate,
    SemanticTriggerEvaluator,
    TriggerEngine,
    TriggerFireResult,
    _evaluate_deterministic,
    _DeterministicSnapshot,
)
from world_simulation_engine.misc.enums import ComparisonOperator, SemanticConditionMode, TriggerEffectKind, \
    TriggerStatus
from world_simulation_engine.model import (
    AllOfCondition,
    AnyOfCondition,
    EntityVariableSet,
    ForcedActionEffect,
    GateEffect,
    LocationCondition,
    MemoryAtom,
    NarrativeBeatEffect,
    NotCondition,
    PerceivedCueEffect,
    SemanticCondition,
    SemanticConditionEvaluationResult,
    SemanticConditionVerdict,
    Simulation,
    StateMutationEffect,
    TimeCondition,
    Trigger,
    TriggerActivation,
    VariableCondition,
    VariableDefinition,
    World,
)
from world_simulation_engine.misc.enums import SupportedLanguage


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_trigger(**overrides) -> Trigger:
    defaults = dict(
        id="trigger_1",
        source_id="simulation_1",
        name="Alice enters the bar",
        condition=LocationCondition(character_id="alice", location_id="bar"),
        effect_kind=TriggerEffectKind.EVENT,
        effects=[NarrativeBeatEffect(directive="Someone recognises Alice.", relevant_character_ids=["alice"])],
    )
    defaults.update(overrides)
    return Trigger(**defaults)


def make_database(triggers: list[Trigger], *, positions: dict | None = None) -> Mock:
    database = Mock()
    database.trigger.list_evaluation_candidates = AsyncMock(return_value=triggers)
    database.trigger.update_trigger_runtime_state = AsyncMock(side_effect=lambda **kwargs: None)
    database.trigger.record_activation = AsyncMock(side_effect=lambda activation: activation)
    database.trigger.list_unconsumed_activations = AsyncMock(return_value=[])
    database.trigger.mark_activations_consumed = AsyncMock()
    database.location.get_location_ids_by_characters = AsyncMock(return_value=positions or {})
    database.variable.get_variable_set = AsyncMock(return_value=None)
    database.turn.get_turn = AsyncMock(return_value=None)
    database.state_commit.apply_state_commit_proposal = AsyncMock()
    return database


# -- Deterministic condition evaluation --------------------------------------------------------

async def test_location_condition_true_when_character_is_in_the_location():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock(), positions={"alice": {"location_id": "bar", "landmark_id": None}})
    condition = LocationCondition(character_id="alice", location_id="bar")

    assert await _evaluate_deterministic(condition, snapshot) is True


async def test_location_condition_false_when_character_is_elsewhere():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock(), positions={"alice": {"location_id": "kitchen", "landmark_id": None}})
    condition = LocationCondition(character_id="alice", location_id="bar")

    assert await _evaluate_deterministic(condition, snapshot) is False


async def test_location_condition_checks_landmark_when_specified():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock(), positions={"alice": {"location_id": "bar", "landmark_id": "counter"}})

    assert await _evaluate_deterministic(
        LocationCondition(character_id="alice", location_id="bar", landmark_id="counter"), snapshot,
    ) is True
    assert await _evaluate_deterministic(
        LocationCondition(character_id="alice", location_id="bar", landmark_id="stage"), snapshot,
    ) is False


async def test_variable_condition_compares_current_value():
    database = Mock()
    database.variable.get_variable_set = AsyncMock(return_value=EntityVariableSet(
        id="varset_1", source_id="simulation_1", owner_type="character", owner_id="alice",
        variables=[VariableDefinition(
            name="mana", value_type="integer", value=80, default_value=0,
        )],
        last_updated_at=NOW,
    ))
    snapshot = _DeterministicSnapshot(current_time=NOW, db=database)
    condition = VariableCondition(owner_id="alice", variable_name="mana", operator=ComparisonOperator.GTE, value=70)

    assert await _evaluate_deterministic(condition, snapshot) is True
    # Same owner read twice within one snapshot only hits the DB once.
    database.variable.get_variable_set.assert_awaited_once()


async def test_variable_condition_false_when_owner_has_no_variable_set():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock(variable=Mock(get_variable_set=AsyncMock(return_value=None))))
    condition = VariableCondition(owner_id="alice", variable_name="mana", operator=ComparisonOperator.GTE, value=70)

    assert await _evaluate_deterministic(condition, snapshot) is False


async def test_time_condition_compares_against_the_simulation_clock():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock())

    assert await _evaluate_deterministic(
        TimeCondition(operator=ComparisonOperator.GTE, value=datetime(2026, 1, 1, 11, 0, tzinfo=UTC)), snapshot,
    ) is True
    assert await _evaluate_deterministic(
        TimeCondition(operator=ComparisonOperator.GTE, value=datetime(2026, 1, 1, 13, 0, tzinfo=UTC)), snapshot,
    ) is False


async def test_time_condition_tolerates_a_naive_authored_value():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock())

    assert await _evaluate_deterministic(
        TimeCondition(operator=ComparisonOperator.GTE, value=datetime(2026, 1, 1, 11, 0)), snapshot,
    ) is True


async def test_time_condition_has_no_entity_ids_so_it_is_always_a_candidate():
    trigger = make_trigger(condition=TimeCondition(operator=ComparisonOperator.GTE, value=NOW))
    database = make_database([trigger])
    engine = TriggerEngine(database=database)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids=set(),
    )

    assert len(results) == 1
    database.trigger.record_activation.assert_awaited_once()


async def test_composite_conditions_combine_correctly():
    snapshot = _DeterministicSnapshot(current_time=NOW, db=Mock(), positions={
        "alice": {"location_id": "bar", "landmark_id": None},
        "bob": {"location_id": "kitchen", "landmark_id": None},
    })
    alice_in_bar = LocationCondition(character_id="alice", location_id="bar")
    bob_in_bar = LocationCondition(character_id="bob", location_id="bar")

    assert await _evaluate_deterministic(AllOfCondition(conditions=[alice_in_bar, bob_in_bar]), snapshot) is False
    assert await _evaluate_deterministic(AnyOfCondition(conditions=[alice_in_bar, bob_in_bar]), snapshot) is True
    assert await _evaluate_deterministic(NotCondition(condition=bob_in_bar), snapshot) is True


# -- TriggerEngine: rising-edge firing, repeatability, gates ------------------------------------

async def test_event_trigger_fires_on_rising_edge_and_queues_a_narrative_beat_activation():
    trigger = make_trigger(last_condition_result=False)
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert len(results) == 1
    assert results[0].trigger_id == "trigger_1"
    recorded = database.trigger.record_activation.await_args.args[0]
    assert isinstance(recorded, TriggerActivation)
    assert recorded.effect.directive == "Someone recognises Alice."
    assert recorded.consumed is False
    runtime_update = database.trigger.update_trigger_runtime_state.await_args.kwargs
    assert runtime_update["status"] == TriggerStatus.CONSUMED  # not repeatable by default


async def test_event_trigger_does_not_refire_while_condition_stays_satisfied():
    trigger = make_trigger(last_condition_result=True)  # already true on the previous evaluation
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert results == []
    database.trigger.record_activation.assert_not_awaited()


async def test_repeatable_event_trigger_goes_back_to_dormant_instead_of_consumed():
    trigger = make_trigger(repeatable=True, last_condition_result=False)
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)

    await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    runtime_update = database.trigger.update_trigger_runtime_state.await_args.kwargs
    assert runtime_update["status"] == TriggerStatus.DORMANT


async def test_irrelevant_trigger_is_not_evaluated_or_touched():
    trigger = make_trigger()
    database = make_database([trigger])
    engine = TriggerEngine(database=database)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"someone_unrelated"},
    )

    assert results == []
    database.location.get_location_ids_by_characters.assert_not_awaited()
    database.trigger.update_trigger_runtime_state.assert_not_awaited()


async def test_probabilistic_trigger_only_fires_when_the_roll_succeeds(monkeypatch):
    trigger = make_trigger(chance=0.5, last_condition_result=False)
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)
    monkeypatch.setattr("world_simulation_engine.component.simulator.trigger_evaluator.random.random", lambda: 0.9)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert results == []
    database.trigger.record_activation.assert_not_awaited()


async def test_probabilistic_trigger_fires_when_the_roll_succeeds(monkeypatch):
    trigger = make_trigger(chance=0.5, last_condition_result=False)
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)
    monkeypatch.setattr("world_simulation_engine.component.simulator.trigger_evaluator.random.random", lambda: 0.1)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert len(results) == 1


async def test_cooldown_blocks_refiring_until_enough_turns_have_elapsed():
    trigger = make_trigger(
        repeatable=True, cooldown_turns=3, last_condition_result=False, last_fired_turn_id="turn_prior",
    )
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    database.turn.get_turn = AsyncMock(return_value=SimpleNamespace(sequence=5))
    engine = TriggerEngine(database=database)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_new", turn_sequence=6, current_time=NOW,  # only 1 turn later
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert results == []
    database.trigger.record_activation.assert_not_awaited()


async def test_gate_trigger_opens_and_closes_without_ever_recording_an_activation():
    trigger = make_trigger(
        condition=VariableCondition(owner_id="alice", variable_name="mana", operator=ComparisonOperator.GTE, value=70),
        effect_kind=TriggerEffectKind.GATE,
        effects=[],
        gate_effect=GateEffect(description="Alice can now hear the voice."),
        reversible=True,
    )
    database = make_database([trigger])
    database.variable.get_variable_set = AsyncMock(return_value=EntityVariableSet(
        id="varset_1", source_id="simulation_1", owner_type="character", owner_id="alice",
        variables=[VariableDefinition(name="mana", value_type="integer", value=80, default_value=0)],
        last_updated_at=NOW,
    ))
    engine = TriggerEngine(database=database)

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert results == []  # gates never produce a TriggerFireResult in this pass
    database.trigger.record_activation.assert_not_awaited()
    runtime_update = database.trigger.update_trigger_runtime_state.await_args.kwargs
    assert runtime_update["status"] == TriggerStatus.ACTIVE


async def test_state_mutation_effect_is_applied_immediately_and_recorded_already_consumed():
    trigger = make_trigger(
        effects=[StateMutationEffect(operations=[{
            "type": "state_change",
            "entity": {"type": "character", "id": "alice", "name": "Alice"},
            "field_changes": [{"field_path": "public_state", "new_value": "smiling", "reason": "Trigger fired."}],
            "reason": "Trigger fired.",
        }])],
    )
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)

    await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    database.state_commit.apply_state_commit_proposal.assert_awaited_once()
    recorded = database.trigger.record_activation.await_args.args[0]
    assert recorded.consumed is True
    assert recorded.consumed_at_turn_id == "turn_1"


# -- SemanticTriggerEvaluator: the LLM must never see anything but the statement ----------------

async def test_semantic_evaluator_never_forwards_trigger_name_description_or_effect_to_the_llm():
    database = Mock()
    database.world.get_world = AsyncMock(return_value=World(
        id="world_1", name="World", description="World", starting_time=NOW, version=1,
        language=SupportedLanguage.ENGLISH,
    ))
    database.simulation.get_simulation = AsyncMock(return_value=Simulation(
        id="simulation_1", name="Simulation", current_time=NOW,
    ))
    evaluator = SemanticTriggerEvaluator(database=database)
    evaluator._prepare_prompt = AsyncMock(return_value=[])
    llm = SimpleNamespace(invoke_structured_with_repair=AsyncMock(
        return_value=SemanticConditionEvaluationResult(verdicts=[
            SemanticConditionVerdict(candidate_index=0, satisfied=True, reason="Shown directly."),
        ]),
    ))
    evaluator._prepare_llm_service = AsyncMock(return_value=llm)

    result = await evaluator.evaluate_fact(
        world_id="world_1", simulation_id="simulation_1",
        candidates=[SemanticConditionCandidate(index=0, statement="Alice found the letter.")],
        narration="Alice found a letter on the table.",
        memories=[MemoryAtom(id="memory_1", summary="Alice found a letter.", keywords=[], embedding=None)],
    )

    assert result.verdicts[0].satisfied is True
    call_data = llm.invoke_structured_with_repair.await_args.kwargs["data"]
    serialized = str(call_data)
    # The only trigger-authored content ever sent is the candidate's own `statement` - a
    # trigger's name/description/effect must never reach this prompt's data payload.
    assert "Someone recognises Alice" not in serialized
    assert "narrative_beat" not in serialized
    assert call_data["candidates"] == [{"index": 0, "statement": "Alice found the letter."}]


async def test_semantic_evaluator_returns_empty_result_without_calling_the_llm_when_no_candidates():
    database = Mock()
    evaluator = SemanticTriggerEvaluator(database=database)
    evaluator._prepare_llm_service = AsyncMock()

    result = await evaluator.evaluate_fact(
        world_id="world_1", simulation_id="simulation_1", candidates=[], narration="", memories=[],
    )

    assert result.verdicts == []
    evaluator._prepare_llm_service.assert_not_awaited()


async def test_semantic_condition_trigger_fires_based_on_llm_verdict():
    trigger = make_trigger(
        condition=SemanticCondition(statement="Alice found the letter.", relevant_character_ids=["alice"]),
    )
    database = make_database([trigger])
    engine = TriggerEngine(database=database)
    engine._semantic_evaluator.evaluate_fact = AsyncMock(return_value=SemanticConditionEvaluationResult(verdicts=[
        SemanticConditionVerdict(candidate_index=0, satisfied=True, reason="Directly shown."),
    ]))

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="Alice found a letter.", memories=[], candidate_entity_ids={"alice"},
    )

    assert len(results) == 1


async def test_pacing_mode_semantic_trigger_uses_evaluate_pacing_not_evaluate_fact():
    trigger = make_trigger(
        condition=SemanticCondition(
            statement="a natural opening has appeared", mode=SemanticConditionMode.PACING,
            relevant_character_ids=["alice"],
        ),
    )
    database = make_database([trigger])
    engine = TriggerEngine(database=database)
    engine._semantic_evaluator.evaluate_fact = AsyncMock()
    engine._semantic_evaluator.evaluate_pacing = AsyncMock(return_value=SemanticConditionEvaluationResult(verdicts=[
        SemanticConditionVerdict(candidate_index=0, satisfied=True, reason="Recent story supports it."),
    ]))

    results = await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    assert len(results) == 1
    engine._semantic_evaluator.evaluate_fact.assert_not_awaited()
    engine._semantic_evaluator.evaluate_pacing.assert_awaited_once()
    assert engine._semantic_evaluator.evaluate_pacing.await_args.kwargs["relevant_character_ids"] == ["alice"]


async def test_evaluate_pacing_builds_recent_summaries_from_relevant_characters_only():
    database = Mock()
    database.world.get_world = AsyncMock(return_value=World(
        id="world_1", name="World", description="World", starting_time=NOW, version=1,
        language=SupportedLanguage.ENGLISH,
    ))
    database.simulation.get_simulation = AsyncMock(return_value=Simulation(
        id="simulation_1", name="Simulation", current_time=NOW,
    ))
    database.memory.get_recent_turn_memory_candidates = AsyncMock(return_value=[
        SimpleNamespace(memory=SimpleNamespace(id="memory_1", summary="Alice asked about the incident.")),
        SimpleNamespace(memory=SimpleNamespace(id="memory_2", summary="Alice seemed distracted.")),
    ])
    evaluator = SemanticTriggerEvaluator(database=database)
    evaluator._prepare_prompt = AsyncMock(return_value=[])
    llm = SimpleNamespace(invoke_structured_with_repair=AsyncMock(
        return_value=SemanticConditionEvaluationResult(verdicts=[]),
    ))
    evaluator._prepare_llm_service = AsyncMock(return_value=llm)

    await evaluator.evaluate_pacing(
        world_id="world_1", simulation_id="simulation_1",
        candidates=[SemanticConditionCandidate(index=0, statement="a natural opening has appeared")],
        relevant_character_ids=["alice"],
    )

    call_data = llm.invoke_structured_with_repair.await_args.kwargs["data"]
    assert call_data["recent_summaries"] == ["Alice asked about the incident.", "Alice seemed distracted."]
    # The pacing prompt never receives raw narration/memories - only pre-summarized text.
    assert "narration" not in call_data


async def test_forced_action_effect_activation_carries_only_directive_and_character_id():
    trigger = make_trigger(effects=[ForcedActionEffect(character_id="bob", directive="Approach Alice.")])
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)

    await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    recorded = database.trigger.record_activation.await_args.args[0]
    assert recorded.effect.character_id == "bob"
    assert recorded.effect.directive == "Approach Alice."
    assert recorded.consumed is False


async def test_perceived_cue_effect_activation_persists_unconsumed_with_multiple_recipients():
    trigger = make_trigger(effects=[PerceivedCueEffect(
        character_ids=["alice", "charlie"], description="A ring left on the table.",
    )])
    database = make_database([trigger], positions={"alice": {"location_id": "bar", "landmark_id": None}})
    engine = TriggerEngine(database=database)

    await engine.process_turn(
        world_id="world_1", simulation_id="simulation_1", turn_id="turn_1", turn_sequence=5, current_time=NOW,
        narration="", memories=[], candidate_entity_ids={"alice"},
    )

    recorded = database.trigger.record_activation.await_args.args[0]
    assert recorded.effect.character_ids == ["alice", "charlie"]
    assert recorded.consumed is False


async def test_expire_stale_perceived_cues_retires_activations_past_their_lifetime():
    activation = TriggerActivation(
        id="activation_1", trigger_id="trigger_1", simulation_id="simulation_1", fired_at_turn_id="turn_old",
        effect=PerceivedCueEffect(character_ids=["alice"], description="A ring.", expires_after_turns=3),
    )
    database = make_database([])
    database.trigger.list_unconsumed_activations = AsyncMock(return_value=[activation])
    database.turn.get_turn = AsyncMock(return_value=SimpleNamespace(sequence=1))
    engine = TriggerEngine(database=database)

    await engine._expire_stale_perceived_cues(simulation_id="simulation_1", current_turn_sequence=5)

    database.trigger.mark_activations_consumed.assert_awaited_once_with(["activation_1"])


async def test_expire_stale_perceived_cues_leaves_fresh_activations_pending():
    activation = TriggerActivation(
        id="activation_1", trigger_id="trigger_1", simulation_id="simulation_1", fired_at_turn_id="turn_recent",
        effect=PerceivedCueEffect(character_ids=["alice"], description="A ring.", expires_after_turns=10),
    )
    database = make_database([])
    database.trigger.list_unconsumed_activations = AsyncMock(return_value=[activation])
    database.turn.get_turn = AsyncMock(return_value=SimpleNamespace(sequence=4))
    engine = TriggerEngine(database=database)

    await engine._expire_stale_perceived_cues(simulation_id="simulation_1", current_turn_sequence=5)

    database.trigger.mark_activations_consumed.assert_awaited_once_with([])


# -- TriggerFireResult.continuation_eligible -----------------------------------------------------

def test_continuation_eligible_true_when_no_effect_names_the_user_character():
    result = TriggerFireResult(trigger_id="trigger_1", activations=[
        TriggerActivation(
            trigger_id="trigger_1", simulation_id="simulation_1", fired_at_turn_id="turn_1",
            effect=ForcedActionEffect(character_id="bob", directive="Approach Alice."),
        ),
    ])

    assert result.continuation_eligible("alice") is True


def test_continuation_eligible_false_when_forced_action_targets_the_user_character():
    result = TriggerFireResult(trigger_id="trigger_1", activations=[
        TriggerActivation(
            trigger_id="trigger_1", simulation_id="simulation_1", fired_at_turn_id="turn_1",
            effect=ForcedActionEffect(character_id="alice", directive="Confront Bob."),
        ),
    ])

    assert result.continuation_eligible("alice") is False


def test_continuation_eligible_false_when_perceived_cue_includes_the_user_character():
    result = TriggerFireResult(trigger_id="trigger_1", activations=[
        TriggerActivation(
            trigger_id="trigger_1", simulation_id="simulation_1", fired_at_turn_id="turn_1",
            effect=PerceivedCueEffect(character_ids=["alice", "charlie"], description="A ring."),
        ),
    ])

    assert result.continuation_eligible("alice") is False


def test_continuation_eligible_true_when_there_is_no_user_character():
    result = TriggerFireResult(trigger_id="trigger_1", activations=[
        TriggerActivation(
            trigger_id="trigger_1", simulation_id="simulation_1", fired_at_turn_id="turn_1",
            effect=ForcedActionEffect(character_id="alice", directive="Confront Bob."),
        ),
    ])

    assert result.continuation_eligible(None) is True
