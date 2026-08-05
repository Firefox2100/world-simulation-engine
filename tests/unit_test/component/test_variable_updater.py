from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.component.simulator.variable_updater import VariableUpdater
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import (
    EntityVariableSet,
    MemoryAtom,
    ProposedVariableChange,
    RelationshipEntityRef,
    Simulation,
    VariableDefinition,
    VariableUpdateProposal,
    VariableValueType,
    World,
)


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_variable_set(**overrides):
    defaults = dict(
        id="varset_1",
        source_id="simulation_1",
        owner_type="character",
        owner_id="character_1",
        variables=[
            VariableDefinition(
                name="affection", value_type=VariableValueType.INTEGER, value=50,
                default_value=50, description="Rises when the character receives a kindness.",
                minimum=0, maximum=100,
            ),
        ],
        last_updated_at=NOW,
        version=1,
    )
    defaults.update(overrides)
    return EntityVariableSet(**defaults)


def make_memory(memory_id="memory_1", summary="A kindness was received."):
    return MemoryAtom(id=memory_id, summary=summary, keywords=[], embedding=None)


async def test_update_from_memories_is_a_noop_without_touching_db_when_no_memory_ids():
    database = Mock()
    database.variable.get_variable_set = AsyncMock()
    updater = VariableUpdater(database=database)

    result = await updater.update_from_memories(
        simulation_id="simulation_1", owner_id="character_1", turn_id="turn_1", memory_ids=[],
    )

    assert result.variable_set_id is None
    database.variable.get_variable_set.assert_not_awaited()


async def test_update_from_memories_is_a_noop_when_owner_has_no_variable_set():
    database = Mock()
    database.variable.get_variable_set = AsyncMock(return_value=None)
    updater = VariableUpdater(database=database)
    updater._prepare_llm_service = AsyncMock()

    result = await updater.update_from_memories(
        simulation_id="simulation_1", owner_id="character_1", turn_id="turn_1", memory_ids=["memory_1"],
    )

    assert result.variable_set_id is None
    updater._prepare_llm_service.assert_not_awaited()


async def test_update_from_memories_is_a_noop_when_variable_set_tracks_nothing():
    database = Mock()
    database.variable.get_variable_set = AsyncMock(return_value=make_variable_set(variables=[]))
    updater = VariableUpdater(database=database)
    updater._prepare_llm_service = AsyncMock()

    result = await updater.update_from_memories(
        simulation_id="simulation_1", owner_id="character_1", turn_id="turn_1", memory_ids=["memory_1"],
    )

    assert result.variable_set_id is None
    updater._prepare_llm_service.assert_not_awaited()


async def test_update_from_memories_forwards_full_variable_definitions_to_the_llm_and_handles_a_noop_proposal():
    variable_set = make_variable_set()
    database = Mock()
    database.variable.get_variable_set = AsyncMock(return_value=variable_set)
    database.simulation.get_simulation = AsyncMock(return_value=Simulation(
        id="simulation_1", name="Simulation", current_time=NOW,
    ))
    database.world.get_world_by_simulation = AsyncMock(return_value=World(
        id="world_1", name="World", description="World", starting_time=NOW, version=1,
        language=SupportedLanguage.ENGLISH,
    ))
    database.memory.get_memory = AsyncMock(return_value=make_memory())
    database.entity_relationship.resolve_entity_refs = AsyncMock(return_value=[
        RelationshipEntityRef(type="character", id="character_1", name="Alex"),
    ])
    updater = VariableUpdater(database=database)
    updater._prepare_prompt = AsyncMock(return_value=[])
    llm = SimpleNamespace(invoke_structured_with_repair=AsyncMock(
        return_value=VariableUpdateProposal(changes=[]),
    ))
    updater._prepare_llm_service = AsyncMock(return_value=llm)

    result = await updater.update_from_memories(
        simulation_id="simulation_1", owner_id="character_1", turn_id="turn_1", memory_ids=["memory_1"],
    )

    assert result.variable_set_id == "varset_1"
    assert result.applied_variable_names == []
    call = llm.invoke_structured_with_repair.await_args.kwargs
    assert call["output_model"] is VariableUpdateProposal
    forwarded_variables = call["data"]["variables"]
    assert len(forwarded_variables) == 1
    assert forwarded_variables[0]["description"] == "Rises when the character receives a kindness."
    assert forwarded_variables[0]["minimum"] == 0
    assert forwarded_variables[0]["maximum"] == 100


async def test_apply_proposal_is_a_noop_when_changes_is_empty_returns_no_writes():
    variable_set = make_variable_set()
    database = Mock()
    database.variable.update_variable_set = AsyncMock()
    updater = VariableUpdater(database=database)

    result = await updater._apply_proposal(
        proposal=VariableUpdateProposal(changes=[]),
        existing=variable_set,
        memories=[make_memory()],
        simulation_time=NOW,
        turn_id="turn_1",
    )

    assert result.variable_set_id == "varset_1"
    assert result.applied_variable_names == []
    database.variable.update_variable_set.assert_not_awaited()


async def test_apply_proposal_applies_a_bounded_change_and_writes_audit():
    variable_set = make_variable_set()
    updated = variable_set.model_copy(update={"variables": [
        variable_set.variables[0].model_copy(update={"value": 65}),
    ], "version": 2})
    database = Mock()
    database.variable.update_variable_set = AsyncMock(return_value=updated)
    database.variable.create_change_audit = AsyncMock(side_effect=lambda value: value)
    updater = VariableUpdater(database=database)
    proposal = VariableUpdateProposal(changes=[ProposedVariableChange(
        name="affection", new_value=65, evidence_memory_ids=["memory_1"],
        reason="Received a kindness.",
    )])

    result = await updater._apply_proposal(
        proposal=proposal, existing=variable_set, memories=[make_memory()],
        simulation_time=NOW, turn_id="turn_1",
    )

    assert result.applied_variable_names == ["affection"]
    assert result.skipped_changes == 0
    stored = database.variable.update_variable_set.await_args.args[0]
    assert stored.variables[0].value == 65
    audit = database.variable.create_change_audit.await_args.args[0]
    assert audit.evidence_memory_ids == ["memory_1"]
    assert audit.change_type == "update"
    assert audit.turn_id == "turn_1"


async def test_apply_proposal_skips_change_referencing_an_unknown_variable_name():
    variable_set = make_variable_set()
    database = Mock()
    database.variable.update_variable_set = AsyncMock()
    updater = VariableUpdater(database=database)
    proposal = VariableUpdateProposal(changes=[ProposedVariableChange(
        name="not_a_real_variable", new_value=1, evidence_memory_ids=["memory_1"], reason="Made up.",
    )])

    result = await updater._apply_proposal(
        proposal=proposal, existing=variable_set, memories=[make_memory()],
        simulation_time=NOW, turn_id="turn_1",
    )

    assert result.applied_variable_names == []
    assert result.skipped_changes == 1
    database.variable.update_variable_set.assert_not_awaited()


async def test_apply_proposal_skips_change_with_evidence_not_in_supplied_memories():
    variable_set = make_variable_set()
    database = Mock()
    database.variable.update_variable_set = AsyncMock()
    updater = VariableUpdater(database=database)
    proposal = VariableUpdateProposal(changes=[ProposedVariableChange(
        name="affection", new_value=65, evidence_memory_ids=["memory_unrelated"],
        reason="Cites a memory that wasn't supplied this call.",
    )])

    result = await updater._apply_proposal(
        proposal=proposal, existing=variable_set, memories=[make_memory(memory_id="memory_1")],
        simulation_time=NOW, turn_id="turn_1",
    )

    assert result.applied_variable_names == []
    assert result.skipped_changes == 1
    database.variable.update_variable_set.assert_not_awaited()


async def test_apply_proposal_clamps_numeric_value_to_the_variable_bounds():
    variable_set = make_variable_set()
    updated = variable_set.model_copy(update={"variables": [
        variable_set.variables[0].model_copy(update={"value": 100}),
    ], "version": 2})
    database = Mock()
    database.variable.update_variable_set = AsyncMock(return_value=updated)
    database.variable.create_change_audit = AsyncMock(side_effect=lambda value: value)
    updater = VariableUpdater(database=database)
    proposal = VariableUpdateProposal(changes=[ProposedVariableChange(
        name="affection", new_value=250, evidence_memory_ids=["memory_1"],
        reason="A very large kindness.",
    )])

    await updater._apply_proposal(
        proposal=proposal, existing=variable_set, memories=[make_memory()],
        simulation_time=NOW, turn_id="turn_1",
    )

    stored = database.variable.update_variable_set.await_args.args[0]
    assert stored.variables[0].value == 100  # clamped to maximum, not left at the out-of-range 250


async def test_apply_proposal_skips_change_with_a_value_of_the_wrong_type():
    variable_set = make_variable_set()
    database = Mock()
    database.variable.update_variable_set = AsyncMock()
    updater = VariableUpdater(database=database)
    proposal = VariableUpdateProposal(changes=[ProposedVariableChange(
        name="affection", new_value="a lot", evidence_memory_ids=["memory_1"],
        reason="affection is an integer variable, not a string.",
    )])

    result = await updater._apply_proposal(
        proposal=proposal, existing=variable_set, memories=[make_memory()],
        simulation_time=NOW, turn_id="turn_1",
    )

    assert result.applied_variable_names == []
    assert result.skipped_changes == 1
    database.variable.update_variable_set.assert_not_awaited()
