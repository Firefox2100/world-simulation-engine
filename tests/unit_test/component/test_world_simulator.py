import asyncio
import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.world_simulator import CharacterActionProposalRecord, \
    CharacterActionProposalState, CharacterActionValidationRecord, WorldSimulator, WorldSimulatorState
from world_simulation_engine.misc.enums import ActionType, GraphStateSnapshotType, SceneCoordinationProblemType, \
    SceneCoordinationStatus, SimulationGenerationRequestType, SupportedLanguage, TurnType
from world_simulation_engine.model import AcceptedSceneAction, ActionProposal, ActionValidation, ActionValidationResult, \
    ActionCandidateSet, CurrentActivity, Character, CharacterActionPlan, GenerationJob, GraphStateSnapshot, InputInterpretation, \
    MemorySummaryProposal, OOCCommand, ProposedAction, ReactionHistoryEntry, SceneCoordinationResult, Simulation, \
    StateCommitProposal, Turn, World


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
        actions=[action],
        reasoning_summary="Look around.",
        next_review_hint_seconds=2,
    )


def make_database_mock() -> Mock:
    database = Mock()
    database.turn.list_turns = AsyncMock(return_value=[])
    database.graph_state_snapshot.save_snapshot = AsyncMock(
        side_effect=lambda snapshot: snapshot
    )
    database.graph_state_snapshot.get_snapshot = AsyncMock(return_value=None)
    database.graph_state_snapshot.get_latest_generation_base_snapshot = AsyncMock(return_value=None)
    database.graph_state_snapshot.get_generation_base_snapshot_by_turn_sequence = AsyncMock(return_value=None)
    database.generation_job.get_job_by_client_request_id = AsyncMock(return_value=None)
    database.generation_job.get_active_job = AsyncMock(return_value=None)
    database.generation_job.create_job = AsyncMock(side_effect=lambda job: job)
    database.generation_job.get_job = AsyncMock(return_value=None)
    database.generation_job.mark_running = AsyncMock()
    database.generation_job.update_job = AsyncMock()
    database.generation_job.mark_completed = AsyncMock()
    database.generation_job.mark_failed = AsyncMock()
    return database


class FakeStreamingGraph:
    def __init__(self, chunks, release_event: asyncio.Event | None = None):
        self.chunks = chunks
        self.release_event = release_event
        self.config = None
        self.stream_mode = None
        self.state = None
        self.started = asyncio.Event()

    async def astream(self, state, config=None, stream_mode=None):
        self.state = state
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
    database.location.get_location_by_character = AsyncMock(return_value=None)
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


async def test_validate_user_action_rejects_other_character_control_without_ooc():
    action = make_action("clara_answers")
    state = make_state(
        InputInterpretation(
            items=[
                {
                    "type": "action",
                    "action": action,
                    "source_text": "Clara answers Arthur.",
                }
            ],
        )
    )
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
    database.location.get_location_by_character = AsyncMock(return_value=Mock(id="location_1"))
    database.get_characters_in_location = AsyncMock(
        return_value=[
            (
                Character(
                    id="character_2",
                    name="Clara Whitlock",
                    age=42,
                    gender="female",
                    appearance="Plain",
                    description="The innkeeper",
                    public_state="Behind the bar",
                    private_state="Careful",
                    current_activity=CurrentActivity(name="serving"),
                ),
                None,
                None,
                None,
            )
        ]
    )
    simulator = WorldSimulator(database=database)
    simulator._action_validator.validate_actions = AsyncMock()

    with pytest.raises(RuntimeError, match="only describe actions attempted by the user character"):
        await simulator.validate_user_action(state)

    simulator._action_validator.validate_actions.assert_not_awaited()


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


async def test_route_after_user_action_validation_routes_valid_actions_to_commit():
    action = make_action()
    state = make_state(InputInterpretation(items=[]))
    state.user_action_validation = ActionValidationResult(
        validations=[
            ActionValidation(
                action_index=0,
                action=action,
                allowed=True,
                reason="The action is allowed.",
            )
        ],
    )
    simulator = WorldSimulator(database=Mock())

    assert await simulator.route_after_user_action_validation(state) == "commit_user_actions"


async def test_route_after_user_action_validation_routes_invalid_actions_to_narration():
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

    assert await simulator.route_after_user_action_validation(state) == "narrate_user_turn"


async def test_coordinate_rejected_user_actions_converts_validation_failure_to_coordination_problem():
    action = make_action()
    state = make_state(InputInterpretation(items=[]))
    state.user_action_validation = ActionValidationResult(
        validations=[
            ActionValidation(
                action_index=0,
                action=action,
                allowed=False,
                reason="The ladder is too far away.",
            )
        ],
    )
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
    simulator = WorldSimulator(database=database)

    result = await simulator.coordinate_rejected_user_actions(state)

    coordination = result["user_action_coordination"]
    assert coordination.status == SceneCoordinationStatus.PROBLEM
    assert coordination.problem.description == "The ladder is too far away."
    assert coordination.problem.involved_actor_ids == ["character_1"]
    assert coordination.pending_actions[0].action == action


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


async def test_route_after_character_coordination_routes_non_user_problem_to_reactions():
    state = make_state(InputInterpretation(items=[]))
    state.character_action_coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.PROBLEM,
        problem={
            "type": SceneCoordinationProblemType.EXCLUSIVE_RESOURCE,
            "time_offset_seconds": 1,
            "involved_actor_ids": ["character_1", "character_2"],
            "involved_actions": [
                {"actor_id": "character_1", "proposal_index": 0, "action_index": 0},
                {"actor_id": "character_2", "proposal_index": 0, "action_index": 0},
            ],
            "description": "Both actors reach for the same glass.",
            "needs_user_decision": False,
            "actors_to_react": ["character_2"],
        },
    )
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
    simulator = WorldSimulator(database=database)

    assert await simulator.route_after_character_coordination(state) == "propose_character_reactions"


async def test_route_after_character_coordination_routes_user_decision_to_narration():
    state = make_state(InputInterpretation(items=[]))
    state.character_action_coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.PROBLEM,
        problem={
            "type": SceneCoordinationProblemType.REACTION_TRIGGER,
            "time_offset_seconds": 1,
            "involved_actor_ids": ["character_1", "character_2"],
            "involved_actions": [
                {"actor_id": "character_2", "proposal_index": 0, "action_index": 0},
            ],
            "description": "Bob swings at Alex, requiring Alex's response.",
            "needs_user_decision": True,
            "actors_to_react": [],
        },
    )
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
    simulator = WorldSimulator(database=database)

    assert await simulator.route_after_character_coordination(state) == "narrate_turn"


async def test_route_after_character_coordination_routes_stopped_scene_to_narration():
    state = make_state(InputInterpretation(items=[]))
    state.character_action_coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.STOPPED,
        stopped_reason="The same reaction repeated three times.",
    )
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
    simulator = WorldSimulator(database=database)

    assert await simulator.route_after_character_coordination(state) == "narrate_turn"


async def test_route_after_user_coordination_routes_problem_to_user_narration():
    state = make_state(InputInterpretation(items=[]))
    state.user_action_coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.PROBLEM,
        problem={
            "type": SceneCoordinationProblemType.OTHER,
            "time_offset_seconds": 0,
            "involved_actor_ids": ["character_1"],
            "involved_actions": [
                {"actor_id": "character_1", "proposal_index": 0, "action_index": 0},
            ],
            "description": "Alex cannot reach the ladder.",
            "needs_user_decision": False,
            "actors_to_react": [],
        },
    )
    simulator = WorldSimulator(database=Mock())

    assert await simulator.route_after_user_coordination(state) == "narrate_user_turn"


async def test_route_after_user_memory_summary_stops_after_user_problem():
    state = make_state(InputInterpretation(items=[]))
    state.user_action_coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.PROBLEM,
        problem={
            "type": SceneCoordinationProblemType.OTHER,
            "time_offset_seconds": 0,
            "involved_actor_ids": ["character_1"],
            "involved_actions": [],
            "description": "Alex cannot reach the ladder.",
            "needs_user_decision": False,
            "actors_to_react": [],
        },
    )
    simulator = WorldSimulator(database=Mock())

    assert await simulator.route_after_user_memory_summary(state) == "__end__"


async def test_propose_character_reactions_replaces_active_actions_and_preserves_problem_context():
    original_action = make_action("take_glass")
    reaction_action = make_action("pull_hand_back")
    reaction_proposal = make_action_proposal(reaction_action)
    coordination = SceneCoordinationResult(
        status=SceneCoordinationStatus.PROBLEM,
        problem={
            "type": SceneCoordinationProblemType.EXCLUSIVE_RESOURCE,
            "time_offset_seconds": 1,
            "involved_actor_ids": ["character_1", "character_2"],
            "involved_actions": [
                {"actor_id": "character_2", "proposal_index": 0, "action_index": 0},
            ],
            "description": "The glass is already taken.",
            "needs_user_decision": False,
            "actors_to_react": ["character_2"],
        },
    )
    state = make_state(InputInterpretation(items=[]))
    state.character_actions = [
        CharacterActionProposalRecord(
            character_id="character_2",
            proposal=make_action_proposal(original_action),
        )
    ]
    state.character_action_validations = [
        CharacterActionValidationRecord(
            character_id="character_2",
            proposal=make_action_proposal(original_action),
            validation=ActionValidationResult(
                validations=[
                    ActionValidation(
                        action_index=0,
                        action=original_action,
                        allowed=True,
                        reason="Allowed.",
                    )
                ],
            ),
        )
    ]
    state.character_action_coordination = coordination
    state.character_actions_are_reactions = True
    state.reaction_history = [
        ReactionHistoryEntry(
            actor_id="character_2",
            action_signature="old",
            count=1,
        )
    ]
    database = Mock()
    database.character.get_user_character_by_simulation = AsyncMock(return_value=Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="The user character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
        user_controlled=True,
    ))
    simulator = WorldSimulator(database=database)
    simulator._character_simulator.propose_reaction = AsyncMock(return_value=reaction_proposal)

    result = await simulator.propose_character_reactions(state)

    assert result["character_actions"] == [
        CharacterActionProposalRecord(
            character_id="character_2",
            proposal=reaction_proposal,
        )
    ]
    assert result["character_action_validations"] == []
    assert result["previous_character_action_coordination"] == coordination
    assert result["character_action_coordination"] is None
    assert result["character_actions_are_reactions"] is True
    assert any(entry.actor_id == "character_2" for entry in result["reaction_history"])
    simulator._character_simulator.propose_reaction.assert_awaited_once()
    assert simulator._character_simulator.propose_reaction.await_args.kwargs["coordination_result"] == coordination
    assert simulator._character_simulator.propose_reaction.await_args.kwargs["action_plans"] == [
        CharacterActionPlan(
            actor_id="character_2",
            actions=[original_action],
            action_proposals=[make_action_proposal(original_action)],
            candidate_sets=[
                ActionCandidateSet(
                    proposal_index=0,
                    actions=[original_action],
                )
            ],
            is_reaction=True,
        )
    ]


def test_character_action_plans_use_valid_backup_proposal_as_sequence_candidate():
    primary_action = make_action("inspect_locked_door")
    backup_first = make_action("step_back")
    backup_second = make_action("wait_for_opening")
    proposal = ActionProposal(
        actions=[primary_action],
        backup_proposals=[[backup_first, backup_second]],
        reasoning_summary="Try the door, otherwise wait.",
        next_review_hint_seconds=2,
    )
    record = CharacterActionValidationRecord(
        character_id="character_1",
        proposal=proposal,
        validation=ActionValidationResult(
            validations=[
                ActionValidation(
                    action_index=0,
                    action=primary_action,
                    allowed=False,
                    reason="The door is locked.",
                )
            ]
        ),
        proposal_validations=[
            ActionValidationResult(
                validations=[
                    ActionValidation(
                        action_index=0,
                        action=primary_action,
                        allowed=False,
                        reason="The door is locked.",
                    )
                ]
            ),
            ActionValidationResult(
                validations=[
                    ActionValidation(
                        action_index=0,
                        action=backup_first,
                        allowed=True,
                        reason="Can step back.",
                    ),
                    ActionValidation(
                        action_index=1,
                        action=backup_second,
                        allowed=True,
                        reason="Can wait.",
                    ),
                ]
            ),
        ],
    )
    simulator = WorldSimulator(database=Mock())

    plans = simulator._character_action_plans_from_validations([record])

    assert plans == [
        CharacterActionPlan(
            actor_id="character_1",
            actions=[backup_first, backup_second],
            action_proposals=[proposal],
            candidate_sets=[
                ActionCandidateSet(
                    proposal_index=1,
                    actions=[backup_first, backup_second],
                )
            ],
        )
    ]


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
                proposal_index=0,
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
                proposal_index=0,
                action_index=0,
                action=action,
                start_offset_seconds=0,
                end_offset_seconds=2,
                summary="Alex looks around.",
            )
        ],
    )
    state = make_state(InputInterpretation(items=[]))
    state.user_action_validation = ActionValidationResult(
        validations=[
            ActionValidation(
                action_index=0,
                action=action,
                allowed=True,
                reason="Allowed.",
            )
        ],
    )
    simulator = WorldSimulator(database=Mock())
    proposal = StateCommitProposal()
    updated_simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, 2, tzinfo=UTC),
    )
    simulator._state_committer.commit_user_actions = AsyncMock(return_value=proposal)
    simulator._db.character.get_user_character_by_simulation = AsyncMock(return_value=make_character())
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

    assert result["committed_turn"] == turn
    assert result["state_commit_proposal"] == proposal
    assert result["simulation"] == updated_simulation
    assert result["user_action_coordination"].status == SceneCoordinationStatus.COMPLETE
    assert result["user_action_coordination"].accepted_actions[0].action == action
    simulator._state_committer.commit_user_actions.assert_awaited_once_with(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=result["user_action_coordination"],
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


async def test_summarize_character_memory_saves_character_round_base_for_world_state():
    coordination = SceneCoordinationResult(status=SceneCoordinationStatus.COMPLETE)
    state_commit = StateCommitProposal()
    turn = Turn(
        id="turn_2",
        sequence=2,
        type=TurnType.SYSTEM_RESPONSE,
        content="The scene continues.",
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )
    state = make_state(InputInterpretation(items=[]))
    state.user_input = None
    state.request_type = SimulationGenerationRequestType.CONTINUE_GENERATION
    state.character_action_coordination = coordination
    state.narration = "The scene continues."
    state.committed_turn = turn
    state.state_commit_proposal = state_commit
    database = make_database_mock()
    simulator = WorldSimulator(database=database)
    proposal = MemorySummaryProposal()
    simulator._memory_summarizer.summarize_character_actions = AsyncMock(return_value=proposal)
    simulator._db.memory_summary.apply_memory_summary_proposal = AsyncMock()

    await simulator.summarize_character_memory(state)

    saved_snapshot = database.graph_state_snapshot.save_snapshot.await_args.args[0]
    assert saved_snapshot.type == GraphStateSnapshotType.AFTER_CHARACTER_ROUND
    assert saved_snapshot.turn_id == "turn_2"
    assert saved_snapshot.turn_sequence == 2
    assert saved_snapshot.state["memory_summary_proposal"] == proposal.model_dump(mode="json")


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
    database = make_database_mock()
    simulator = WorldSimulator(database=database)
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
    saved_snapshot = database.graph_state_snapshot.save_snapshot.await_args.args[0]
    assert saved_snapshot.type == GraphStateSnapshotType.AFTER_USER_INPUT
    assert saved_snapshot.turn_id == "turn_1"
    assert saved_snapshot.turn_sequence == 1
    assert saved_snapshot.state["memory_summary_proposal"] == proposal.model_dump(mode="json")


async def test_start_generation_streams_graph_values_and_stores_final_state():
    release_event = asyncio.Event()
    graph = FakeStreamingGraph(
        chunks=[
            {"narration": "The scene begins."},
            {"narration": "The scene settles.", "committed_turn": {"id": "turn_1"}},
        ],
        release_event=release_event,
    )
    database = make_database_mock()
    previous_turn = Turn(
        id="turn_40",
        sequence=40,
        type=TurnType.SYSTEM_RESPONSE,
        content="Generated something.",
        start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    database.turn.list_turns = AsyncMock(return_value=[previous_turn])
    simulator = WorldSimulator(database=database)
    simulator._user_input_graph = graph
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
    saved_snapshot = database.graph_state_snapshot.save_snapshot.await_args.args[0]
    assert saved_snapshot.type == GraphStateSnapshotType.BEFORE_USER_INPUT
    assert saved_snapshot.turn_id == "turn_40"
    assert saved_snapshot.turn_sequence == 40
    created_job = database.generation_job.create_job.await_args.args[0]
    assert created_job.id == thread_id
    assert created_job.simulation_id == "simulation_1"
    database.generation_job.mark_running.assert_awaited_once_with(thread_id, stage="starting")
    database.generation_job.mark_completed.assert_awaited_once_with(
        thread_id,
        final_turn_id="turn_1",
    )


async def test_start_generation_returns_existing_job_for_same_idempotency_key():
    database = make_database_mock()
    state = make_state(InputInterpretation(items=[]))
    fingerprint = WorldSimulator._generation_request_fingerprint(
        state=state,
        request_type=SimulationGenerationRequestType.USER_INPUT_GENERATION,
        regenerate_turn_sequence=None,
    )
    existing = GenerationJob(
        id="existing_job",
        simulation_id=state.simulation.id,
        client_request_id="request_1",
        request_fingerprint=fingerprint,
        request_type=SimulationGenerationRequestType.USER_INPUT_GENERATION,
    )
    database.generation_job.get_job_by_client_request_id = AsyncMock(return_value=existing)
    simulator = WorldSimulator(database=database)

    result = await simulator.start_generation(
        state,
        client_request_id="request_1",
    )

    assert result == existing.id
    database.generation_job.create_job.assert_not_awaited()


async def test_start_generation_rejects_reused_idempotency_key_for_different_request():
    database = make_database_mock()
    state = make_state(InputInterpretation(items=[]))
    existing = GenerationJob(
        id="existing_job",
        simulation_id=state.simulation.id,
        client_request_id="request_1",
        request_fingerprint="different",
        request_type=SimulationGenerationRequestType.USER_INPUT_GENERATION,
    )
    database.generation_job.get_job_by_client_request_id = AsyncMock(return_value=existing)
    simulator = WorldSimulator(database=database)

    with pytest.raises(ValueError, match="already used for a different"):
        await simulator.start_generation(
            state,
            client_request_id="request_1",
        )


async def test_stream_generation_returns_final_state_after_active_run_is_cleaned_up():
    graph = FakeStreamingGraph(
        chunks=[
            {"narration": "Already finished."},
        ],
    )
    simulator = WorldSimulator(database=make_database_mock())
    simulator._user_input_graph = graph
    state = make_state(InputInterpretation(items=[]))

    thread_id = await simulator.start_generation(state)
    final_state = await simulator.get_generation_final_state(thread_id)

    assert final_state == {"narration": "Already finished."}
    assert await collect_async(simulator.stream_generation(thread_id)) == [final_state]


async def test_continue_generation_uses_latest_character_round_base():
    snapshot_state = make_state(InputInterpretation(items=[]))
    snapshot_state.user_input = "Original user input."
    snapshot = GraphStateSnapshot(
        simulation_id="simulation_1",
        type=GraphStateSnapshotType.AFTER_CHARACTER_ROUND,
        turn_id="turn_42",
        turn_sequence=42,
        state=snapshot_state.model_dump(mode="json"),
    )
    graph = FakeStreamingGraph(chunks=[{"narration": "Continued."}])
    database = make_database_mock()
    database.graph_state_snapshot.get_latest_generation_base_snapshot = AsyncMock(return_value=snapshot)
    simulator = WorldSimulator(database=database)
    simulator._character_round_graph = graph
    state = make_state(InputInterpretation(items=[]))
    state.user_input = None

    thread_id = await simulator.start_generation(
        state,
        request_type=SimulationGenerationRequestType.CONTINUE_GENERATION,
    )
    await simulator.get_generation_final_state(thread_id)

    assert graph.state.request_type == SimulationGenerationRequestType.CONTINUE_GENERATION
    assert graph.state.user_input is None
    assert graph.state.character_actions == []
    database.graph_state_snapshot.get_latest_generation_base_snapshot.assert_awaited_once_with(
        simulation_id="simulation_1",
    )
    database.graph_state_snapshot.save_snapshot.assert_not_awaited()


async def test_regeneration_uses_base_before_requested_turn():
    snapshot_state = make_state(InputInterpretation(items=[]))
    snapshot = GraphStateSnapshot(
        simulation_id="simulation_1",
        type=GraphStateSnapshotType.AFTER_USER_INPUT,
        turn_id="turn_41",
        turn_sequence=41,
        state=snapshot_state.model_dump(mode="json"),
    )
    graph = FakeStreamingGraph(chunks=[{"narration": "Regenerated."}])
    database = make_database_mock()
    database.graph_state_snapshot.get_generation_base_snapshot_by_turn_sequence = AsyncMock(return_value=snapshot)
    simulator = WorldSimulator(database=database)
    simulator._character_round_graph = graph
    state = make_state(InputInterpretation(items=[]))
    state.user_input = None

    thread_id = await simulator.start_generation(
        state,
        request_type=SimulationGenerationRequestType.REGENERATION,
        regenerate_turn_sequence=42,
    )
    await simulator.get_generation_final_state(thread_id)

    assert graph.state.request_type == SimulationGenerationRequestType.REGENERATION
    assert graph.state.user_input is None
    database.graph_state_snapshot.get_generation_base_snapshot_by_turn_sequence.assert_awaited_once_with(
        simulation_id="simulation_1",
        turn_sequence=41,
    )


async def test_start_generation_allows_one_active_run_per_simulation():
    release_event = asyncio.Event()
    graph = FakeStreamingGraph(
        chunks=[
            {"narration": "First."},
            {"narration": "Second."},
        ],
        release_event=release_event,
    )
    simulator = WorldSimulator(database=make_database_mock())
    simulator._user_input_graph = graph
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


async def test_get_graph_state_snapshot_state_rehydrates_saved_world_state():
    state = make_state(InputInterpretation(items=[]))
    snapshot = GraphStateSnapshot(
        simulation_id="simulation_1",
        type=GraphStateSnapshotType.BEFORE_USER_INPUT,
        state=state.model_dump(mode="json"),
    )
    database = make_database_mock()
    database.graph_state_snapshot.get_snapshot = AsyncMock(return_value=snapshot)
    simulator = WorldSimulator(database=database)

    result = await simulator.get_graph_state_snapshot_state(
        simulation_id="simulation_1",
        type=GraphStateSnapshotType.BEFORE_USER_INPUT,
    )

    assert result == state
