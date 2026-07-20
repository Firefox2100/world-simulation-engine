import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.state_committer import StateCommitter
from world_simulation_engine.misc.enums import ActionType, SceneCoordinationStatus, SupportedLanguage
from world_simulation_engine.model import AcceptedSceneAction, Character, CurrentActivity, Location, ProposedAction, \
    SceneCoordinationResult, Simulation, StateCommitProposal, World


def make_world() -> World:
    return World(
        id="world_1",
        name="World",
        description="A test world",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )


def make_simulation() -> Simulation:
    return Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )


def make_character() -> Character:
    return Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="A character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )


def make_coordination() -> SceneCoordinationResult:
    return SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            AcceptedSceneAction(
                actor_id="character_1",
                proposal_index=0,
                action_index=0,
                action=ProposedAction(
                    type=ActionType.TAKE,
                    label="take_glass",
                    target_ids=["item_glass"],
                    intended_duration_seconds=2,
                    interruptible=True,
                    expected_effects=["Alex holds the glass."],
                ),
                start_offset_seconds=0,
                end_offset_seconds=2,
                summary="Alex takes the glass.",
            )
        ],
    )


def make_database():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    location = Location(
        id="location_1",
        name="Room",
        description="A small room",
    )

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=location)
    database.item.get_inventory = AsyncMock(return_value=[])
    database.equipment.get_equipment_inventory = AsyncMock(return_value=[])
    database.get_characters_in_location = AsyncMock(return_value=[])
    database.character.get_background_characters_by_location = AsyncMock(return_value=[])
    database.item.get_stacks_by_location = AsyncMock(return_value=[])
    database.equipment.get_equipment_by_location = AsyncMock(return_value=[])
    database.container.get_containers_by_location = AsyncMock(return_value=[])
    database.location.get_landmarks_by_location = AsyncMock(return_value=[])

    return database


async def test_build_context_fetches_physical_scene_context():
    database = make_database()
    committer = StateCommitter(database=database)
    coordination = make_coordination()

    context = await committer._build_context(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=coordination,
        source="character",
        user_input="Continue.",
    )

    assert context.world.id == "world_1"
    assert context.simulation.id == "simulation_1"
    assert context.user_character_id == "character_1"
    assert context.coordination_result == coordination
    assert context.actors[0].actor.id == "character_1"
    assert context.actors[0].location.id == "location_1"


async def test_commit_character_actions_invokes_structured_llm():
    database = make_database()
    committer = StateCommitter(database=database)
    committer._prepare_llm_service = AsyncMock()
    expected = StateCommitProposal(
        operations=[
            {
                "type": "relationship_change",
                "relationship_type": "held_by",
                "subject": {
                    "type": "item_stack",
                    "id": "item_glass",
                },
                "object": {
                    "type": "character",
                    "id": "character_1",
                },
                "source_action_refs": ["accepted:0"],
                "reason": "Alex took the glass.",
            }
        ],
    )
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=expected)
    committer._prepare_llm_service.return_value = llm

    result = await committer.commit_character_actions(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=make_coordination(),
        user_input="Continue.",
    )

    assert result == expected
    llm.invoke_structured_with_repair.assert_awaited_once()
    assert llm.invoke_structured_with_repair.await_args.kwargs["output_model"] is StateCommitProposal


async def test_build_context_skips_missing_actor_or_location_and_collects_problem_actor_ids():
    from world_simulation_engine.misc.enums import SceneCoordinationProblemType
    from world_simulation_engine.model import SceneCoordinationProblem

    database = make_database()
    character = make_character()
    database.character.get_character = AsyncMock(
        side_effect=lambda actor_id: character if actor_id == "character_1" else None
    )
    database.location.get_location_by_character = AsyncMock(
        side_effect=lambda actor_id: Location(
            id="location_1",
            name="Room",
            description="A small room",
        ) if actor_id == "character_1" else None
    )
    coordination = make_coordination()
    coordination.problem = SceneCoordinationProblem(
        type=SceneCoordinationProblemType.INTERRUPTION,
        time_offset_seconds=1,
        involved_actor_ids=["character_1", "missing_character"],
        description="A character interrupted the action.",
        needs_user_decision=False,
    )
    committer = StateCommitter(database=database)

    context = await committer._build_context(
        world_id="world_1",
        simulation_id="simulation_1",
        coordination_result=coordination,
        source="user",
    )

    assert [actor.actor.id for actor in context.actors] == ["character_1"]
    assert context.source == "user"
