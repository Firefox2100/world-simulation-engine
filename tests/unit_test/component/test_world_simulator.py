import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.world_simulator import CharacterActionProposalRecord, \
    CharacterActionProposalState, WorldSimulator, WorldSimulatorState
from world_simulation_engine.misc.enums import ActionType, SceneCoordinationStatus, SupportedLanguage, TurnType
from world_simulation_engine.model import AcceptedSceneAction, ActionProposal, ActionValidation, ActionValidationResult, \
    CurrentActivity, Character, InputInterpretation, MemorySummaryProposal, OOCCommand, ProposedAction, \
    SceneCoordinationResult, Simulation, StateCommitProposal, Turn, World


def make_state(input_interpretation: InputInterpretation) -> WorldSimulatorState:
    return WorldSimulatorState(
        world=World(
            id="world_1",
            name="World",
            description="A test world",
            starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            version=1,
            language=SupportedLanguage.ENGLISH,
        ),
        simulation=Simulation(
            id="simulation_1",
            name="Simulation",
            description="A simulation",
            current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        user_input="I look around.",
        input_interpretation=input_interpretation,
    )


def make_character() -> Character:
    return Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="The user character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )


def make_action(label: str = "look_around") -> ProposedAction:
    return ProposedAction(
        type=ActionType.LOOK,
        label=label,
        target_ids=[],
        intended_duration_seconds=2,
        interruptible=True,
    )


def make_action_proposal(action: ProposedAction) -> ActionProposal:
    return ActionProposal(
        chosen_action=action,
        reasoning_summary="Look around.",
        next_review_hint_seconds=2,
    )


class FakeStreamingGraph:
    def __init__(self, chunks, release_event: asyncio.Event | None = None):
        self.chunks = chunks
        self.release_event = release_event
        self.config = None
        self.stream_mode = None
        self.started = asyncio.Event()

    async def astream(self, state, config=None, stream_mode=None):
        self.config = config
        self.stream_mode = stream_mode
        self.started.set()
        for index, chunk in enumerate(self.chunks):
            if index > 0 and self.release_event is not None:
                await self.release_event.wait()
            yield chunk


async def collect_async(async_iterable):
    return [
        item
        async for item in async_iterable
    ]


async def test_validate_user_action_validates_interpreted_actions():
    action = make_action()
    state = make_state(
        InputInterpretation(
            items=[
                {
                    "type": "action",
                    "action": action,
                    "source_text": "I look around.",
                }
            ],
        )
    )
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
    simulator = WorldSimulator(database=database)
    expected = ActionValidationResult(validations=[])
    simulator._action_validator.validate_actions = AsyncMock(return_value=expected)

    result = await simulator.validate_user_action(state)

    assert result == {
        "user_action_validation": expected,
    }
    simulator._action_validator.validate_actions.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        actions=[action],
    )


async def test_route_after_input_interpretation_rejects_ooc_for_now():
    state = make_state(
        InputInterpretation(
            items=[
                OOCCommand(
                    command_text="summarize",
                    normalized_intent="Summarize the scene.",
                    source_text="[/OOC: summarize]",
                )
            ],
        )
    )
    simulator = WorldSimulator(database=Mock())

    with pytest.raises(NotImplementedError, match="OOC command route"):
        await simulator.route_after_input_interpretation(state)


async def test_route_after_user_action_validation_rejects_invalid_actions_for_now():
    action = make_action()
    state = make_state(InputInterpretation(items=[]))
    state.user_action_validation = ActionValidationResult(
        validations=[
            ActionValidation(
                action_index=0,
                action=action,
                allowed=False,
                reason="The action is not allowed.",
            )
        ],
    )
    simulator = WorldSimulator(database=Mock())

    with pytest.raises(NotImplementedError, match="Rejected user action route"):
        await simulator.route_after_user_action_validation(state)


async def test_validate_character_actions_reworks_invalid_proposal_before_coordination():
    invalid_action = make_action("look_through_wall")
    valid_action = make_action("look_at_door")
    invalid_proposal = make_action_proposal(invalid_action)
    valid_proposal = make_action_proposal(valid_action)
    state = CharacterActionProposalState(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input="Look for the exit.",
        character_actions=[
            CharacterActionProposalRecord(
                character_id="character_1",
                proposal=invalid_proposal,
            )
        ],
    )
    database = Mock()
    simulator = WorldSimulator(database=database)
    simulator._action_validator.validate_actions = AsyncMock(
        side_effect=[
            ActionValidationResult(
                validations=[
                    ActionValidation(
                        action_index=0,
                        action=invalid_action,
                        allowed=False,
                        reason="The wall is opaque.",
                    )
                ],
            ),
            ActionValidationResult(
                validations=[
                    ActionValidation(
                        action_index=0,
                        action=valid_action,
                        allowed=True,
                        reason="The door is visible.",
                    )
                ],
            ),
        ]
    )
    simulator._character_simulator.propose_actions = AsyncMock(return_value=valid_proposal)
    simulator._scene_coordinator.coordinate_scene = AsyncMock(
        return_value=SceneCoordinationResult(status=SceneCoordinationStatus.COMPLETE)
    )

    result = await simulator.validate_character_actions(state)

    validation_record = result["character_action_validations"][0]
    assert validation_record.proposal == valid_proposal
    assert validation_record.validation.validations[0].allowed
    assert "The wall is opaque." in simulator._character_simulator.propose_actions.await_args.kwargs["user_input"]
    simulator._scene_coordinator.coordinate_scene.assert_not_called()


async def test_validate_character_actions_stops_after_three_invalid_reworks():
    invalid_action = make_action("phase_through_wall")
    invalid_proposal = make_action_proposal(invalid_action)
    state = CharacterActionProposalState(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input="Leave.",
        character_actions=[
            CharacterActionProposalRecord(
                character_id="character_1",
                proposal=invalid_proposal,
            )
        ],
    )
    database = Mock()
    simulator = WorldSimulator(database=database)
    simulator._action_validator.validate_actions = AsyncMock(
        return_value=ActionValidationResult(
            validations=[
                ActionValidation(
                    action_index=0,
                    action=invalid_action,
                    allowed=False,
                    reason="Phasing is not possible.",
                )
            ],
        )
    )
    simulator._character_simulator.propose_actions = AsyncMock(return_value=invalid_proposal)

    with pytest.raises(RuntimeError, match="3 rework attempts"):
        await simulator.validate_character_actions(state)

    assert simulator._character_simulator.propose_actions.await_count == 3


async def test_narrate_turn_uses_character_action_coordination():
    coordination = SceneCoordinationResult(status=SceneCoordinationStatus.COMPLETE)
    state = CharacterActionProposalState(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input="Continue.",
        character_action_coordination=coordination,
    )
    simulator = WorldSimulator(database=Mock())
    simulator._narrator.narrate_turn = AsyncMock(return_value="The scene continues.")

    result = await simulator.narrate_turn(state)

    assert result == {
        "narration": "The scene continues.",
    }
    simulator._narrator.narrate_turn.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=coordination,
        user_input="Continue.",
    )


async def test_commit_character_actions_returns_turn_and_commit_proposal():
    action = make_action()
    coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            AcceptedSceneAction(
                actor_id="character_1",
                action_index=0,
                action=action,
                start_offset_seconds=0,
                end_offset_seconds=2,
                summary="Alex looks around.",
            )
        ],
    )
    simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    updated_simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, 2, tzinfo=UTC),
    )
    state = CharacterActionProposalState(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input="Continue.",
        character_action_coordination=coordination,
        narration="The scene continues.",
    )
    simulator = WorldSimulator(database=Mock())
    proposal = StateCommitProposal()
    simulator._state_committer.commit_character_actions = AsyncMock(return_value=proposal)
    turn = Turn(
        id="turn_1",
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="The scene continues.",
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    simulator._db.turn.create_next_turn = AsyncMock(return_value=turn)
    simulator._db.state_commit.apply_state_commit_proposal = AsyncMock()
    simulator._db.simulation.get_simulation = AsyncMock(return_value=simulation)
    simulator._db.simulation.update_current_time = AsyncMock(return_value=updated_simulation)

    result = await simulator.commit_character_actions(state)

    assert result == {
        "committed_turn": turn,
        "state_commit_proposal": proposal,
        "simulation": updated_simulation,
    }
    simulator._state_committer.commit_character_actions.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=coordination,
        user_input="Continue.",
    )
    simulator._db.turn.create_next_turn.assert_awaited_once()
    created_turn = simulator._db.turn.create_next_turn.await_args.kwargs["turn"]
    assert created_turn.type == TurnType.SYSTEM_RESPONSE
    assert created_turn.content == "The scene continues."
    assert created_turn.start_time == simulation.current_time
    simulator._db.state_commit.apply_state_commit_proposal.assert_awaited_once_with(
        proposal=proposal,
        source_id="simulation_1",
        turn_id="turn_1",
    )
    simulator._db.simulation.update_current_time.assert_awaited_once_with(
        simulation_id="simulation_1",
        current_time=updated_simulation.current_time,
    )


async def test_commit_user_actions_uses_raw_user_input_for_turn_content():
    action = make_action()
    coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            AcceptedSceneAction(
                actor_id="character_1",
                action_index=0,
                action=action,
                start_offset_seconds=0,
                end_offset_seconds=2,
                summary="Alex looks around.",
            )
        ],
    )
    state = make_state(InputInterpretation(items=[]))
    state.user_action_coordination = coordination
    simulator = WorldSimulator(database=Mock())
    proposal = StateCommitProposal()
    updated_simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, 2, tzinfo=UTC),
    )
    simulator._state_committer.commit_user_actions = AsyncMock(return_value=proposal)
    turn = Turn(
        id="turn_1",
        sequence=1,
        type=TurnType.USER_INPUT,
        content=state.user_input,
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    simulator._db.turn.create_next_turn = AsyncMock(return_value=turn)
    simulator._db.state_commit.apply_state_commit_proposal = AsyncMock()
    simulator._db.simulation.update_current_time = AsyncMock(return_value=updated_simulation)

    result = await simulator.commit_user_actions(state)

    assert result == {
        "committed_turn": turn,
        "state_commit_proposal": proposal,
        "simulation": updated_simulation,
    }
    simulator._state_committer.commit_user_actions.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=coordination,
        user_input="I look around.",
    )
    created_turn = simulator._db.turn.create_next_turn.await_args.kwargs["turn"]
    assert created_turn.type == TurnType.USER_INPUT
    assert created_turn.content == "I look around."
    assert created_turn.start_time == state.simulation.current_time
    simulator._db.state_commit.apply_state_commit_proposal.assert_awaited_once_with(
        proposal=proposal,
        source_id="simulation_1",
        turn_id="turn_1",
    )
    simulator._db.simulation.update_current_time.assert_awaited_once_with(
        simulation_id="simulation_1",
        current_time=updated_simulation.current_time,
    )


async def test_summarize_character_memory_applies_summary_proposal():
    coordination = SceneCoordinationResult(status=SceneCoordinationStatus.COMPLETE)
    state_commit = StateCommitProposal()
    turn = Turn(
        id="turn_1",
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="The scene continues.",
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    state = CharacterActionProposalState(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        user_input="Continue.",
        character_action_coordination=coordination,
        narration="The scene continues.",
        committed_turn=turn,
        state_commit_proposal=state_commit,
    )
    simulator = WorldSimulator(database=Mock())
    proposal = MemorySummaryProposal()
    simulator._memory_summarizer.summarize_character_actions = AsyncMock(return_value=proposal)
    simulator._db.memory_summary.apply_memory_summary_proposal = AsyncMock()

    result = await simulator.summarize_character_memory(state)

    assert result == {
        "memory_summary_proposal": proposal,
    }
    simulator._memory_summarizer.summarize_character_actions.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        turn=turn,
        coordination_result=coordination,
        state_commit=state_commit,
        user_input="Continue.",
        narration="The scene continues.",
    )
    simulator._db.memory_summary.apply_memory_summary_proposal.assert_awaited_once_with(
        proposal=proposal,
        turn_id="turn_1",
    )


async def test_summarize_user_memory_applies_summary_proposal():
    coordination = SceneCoordinationResult(status=SceneCoordinationStatus.COMPLETE)
    state_commit = StateCommitProposal()
    turn = Turn(
        id="turn_1",
        sequence=1,
        type=TurnType.USER_INPUT,
        content="I look around.",
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    state = make_state(InputInterpretation(items=[]))
    state.user_action_coordination = coordination
    state.committed_turn = turn
    state.state_commit_proposal = state_commit
    simulator = WorldSimulator(database=Mock())
    proposal = MemorySummaryProposal()
    simulator._memory_summarizer.summarize_user_actions = AsyncMock(return_value=proposal)
    simulator._db.memory_summary.apply_memory_summary_proposal = AsyncMock()

    result = await simulator.summarize_user_memory(state)

    assert result == {
        "memory_summary_proposal": proposal,
    }
    simulator._memory_summarizer.summarize_user_actions.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        turn=turn,
        coordination_result=coordination,
        state_commit=state_commit,
        user_input="I look around.",
    )


async def test_start_generation_streams_graph_values_and_stores_final_state():
    release_event = asyncio.Event()
    graph = FakeStreamingGraph(
        chunks=[
            {"narration": "The scene begins."},
            {"narration": "The scene settles.", "committed_turn": {"id": "turn_1"}},
        ],
        release_event=release_event,
    )
    simulator = WorldSimulator(database=Mock())
    simulator._simulator_graph = graph
    state = make_state(InputInterpretation(items=[]))

    thread_id = await simulator.start_generation(state)
    await graph.started.wait()

    stream = simulator.stream_generation(thread_id)
    first_chunk = await anext(stream)
    release_event.set()
    remaining_chunks = [item async for item in stream]

    assert first_chunk == {"narration": "The scene begins."}
    assert remaining_chunks == [
        {"narration": "The scene settles.", "committed_turn": {"id": "turn_1"}},
    ]
    assert graph.stream_mode == "values"
    assert graph.config["configurable"]["thread_id"] == thread_id
    assert await simulator.get_generation_final_state(thread_id) == remaining_chunks[-1]


async def test_stream_generation_returns_final_state_after_active_run_is_cleaned_up():
    graph = FakeStreamingGraph(
        chunks=[
            {"narration": "Already finished."},
        ],
    )
    simulator = WorldSimulator(database=Mock())
    simulator._simulator_graph = graph
    state = make_state(InputInterpretation(items=[]))

    thread_id = await simulator.start_generation(state)
    final_state = await simulator.get_generation_final_state(thread_id)

    assert final_state == {"narration": "Already finished."}
    assert await collect_async(simulator.stream_generation(thread_id)) == [final_state]


async def test_start_generation_allows_one_active_run_per_simulation():
    release_event = asyncio.Event()
    graph = FakeStreamingGraph(
        chunks=[
            {"narration": "First."},
            {"narration": "Second."},
        ],
        release_event=release_event,
    )
    simulator = WorldSimulator(database=Mock())
    simulator._simulator_graph = graph
    state = make_state(InputInterpretation(items=[]))

    first_thread_id = await simulator.start_generation(state)
    await graph.started.wait()

    with pytest.raises(RuntimeError, match="already has an active generation"):
        await simulator.start_generation(state)

    release_event.set()
    await simulator.get_generation_final_state(first_thread_id)

    second_thread_id = await simulator.start_generation(state)

    assert second_thread_id != first_thread_id
    assert await simulator.get_generation_final_state(second_thread_id) == {"narration": "Second."}
