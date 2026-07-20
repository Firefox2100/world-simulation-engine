import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.narrator import Narrator
from world_simulation_engine.misc.enums import ActionType, SceneCoordinationStatus, SupportedLanguage
from world_simulation_engine.model import AcceptedSceneAction, Character, CurrentActivity, Location, NarrationBlock, \
    NarrationInsertionProposal, NarrationProposal, ProposedAction, SceneCoordinationResult, Simulation, SpeechBlock, \
    World


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
                action_index=0,
                action=ProposedAction(
                    type=ActionType.SPEAK,
                    label="greet_room",
                    target_ids=[],
                    utterance="Hello.",
                    intended_duration_seconds=2,
                    interruptible=True,
                ),
                start_offset_seconds=0,
                end_offset_seconds=2,
                summary='Alex says "Hello."',
            )
        ],
    )


async def test_narrate_turn_invokes_plain_text_llm_with_context():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    location = Location(
        id="location_1",
        name="Room",
        description="A small room",
    )
    coordination = make_coordination()

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=location)
    narrator = Narrator(database=database)
    narrator._prepare_llm_service = AsyncMock()
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=NarrationInsertionProposal(insertions=[]))
    narrator._prepare_llm_service.return_value = llm

    result = await narrator.narrate_turn(
        world_id=world.id,
        simulation_id=simulation.id,
        coordination_result=coordination,
        user_input="I greet everyone.",
    )

    assert result == NarrationProposal(
        blocks=[
            SpeechBlock(
                type="speech",
                character_id="character_1",
                character_name="Alex",
                text="Hello.",
            )
        ]
    )
    llm.invoke_structured_with_repair.assert_awaited_once()
    data = llm.invoke_structured_with_repair.await_args.kwargs["data"]
    assert data["coordination_result"]["accepted_actions"][0]["action"]["utterance"] == "Hello."
    assert data["actors"][0]["character"]["name"] == "Alex"
    assert data["speech_anchors"][0]["text"] == "Hello."


async def test_narrate_turn_inserts_narration_around_fixed_speech():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    coordination = make_coordination()

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=None)
    narrator = Narrator(database=database)
    narrator._prepare_llm_service = AsyncMock()
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(
        return_value=NarrationInsertionProposal(
            insertions=[
                {
                    "position": 0,
                    "text": "Alex turns toward the room.",
                },
                {
                    "position": 1,
                    "text": "The greeting hangs briefly in the air.",
                },
            ],
        )
    )
    narrator._prepare_llm_service.return_value = llm

    result = await narrator.narrate_turn(
        world_id=world.id,
        simulation_id=simulation.id,
        coordination_result=coordination,
        user_input="I greet everyone.",
    )

    assert result.blocks == [
        NarrationBlock(type="narration", text="Alex turns toward the room."),
        SpeechBlock(type="speech", character_id="character_1", character_name="Alex", text="Hello."),
        NarrationBlock(type="narration", text="The greeting hangs briefly in the air."),
    ]


async def test_narrate_turn_clamps_narration_insertions_after_final_speech():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    coordination = make_coordination()

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=None)
    narrator = Narrator(database=database)
    narrator._prepare_llm_service = AsyncMock()
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(
        return_value=NarrationInsertionProposal(
            insertions=[
                {
                    "position": 99,
                    "text": "The room settles again.",
                },
            ],
        )
    )
    narrator._prepare_llm_service.return_value = llm

    result = await narrator.narrate_turn(
        world_id=world.id,
        simulation_id=simulation.id,
        coordination_result=coordination,
        user_input="I greet everyone.",
    )

    assert result.blocks == [
        SpeechBlock(type="speech", character_id="character_1", character_name="Alex", text="Hello."),
        NarrationBlock(type="narration", text="The room settles again."),
    ]


async def test_narrate_turn_includes_accepted_speech_when_model_returns_only_narration():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    coordination = make_coordination()

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=character)
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=None)
    narrator = Narrator(database=database)
    narrator._prepare_llm_service = AsyncMock()
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=NarrationInsertionProposal(insertions=[]))
    narrator._prepare_llm_service.return_value = llm

    result = await narrator.narrate_turn(
        world_id=world.id,
        simulation_id=simulation.id,
        coordination_result=coordination,
        user_input="I greet everyone.",
    )

    assert result.blocks == [
        SpeechBlock(
            type="speech",
            character_id="character_1",
            character_name="Alex",
            text="Hello.",
        )
    ]


async def test_build_context_collects_sorted_unique_actor_ids_from_accepted_pending_and_problem():
    from world_simulation_engine.misc.enums import SceneCoordinationProblemType
    from world_simulation_engine.model import PendingSceneAction, SceneCoordinationProblem

    world = make_world()
    simulation = make_simulation()
    actor_1 = make_character()
    actor_2 = Character(
        id="character_2",
        name="Blake",
        age=31,
        gender="unknown",
        appearance="Plain",
        description="A second actor",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )
    actors = {
        actor_1.id: actor_1,
        actor_2.id: actor_2,
    }
    location = Location(id="location_1", name="Room", description="A small room")
    coordination = make_coordination()
    coordination.pending_actions = [
        PendingSceneAction(
            actor_id="character_2",
            action_index=0,
            action=ProposedAction(
                type=ActionType.WAIT,
                label="wait",
                intended_duration_seconds=2,
            ),
            reason="Waiting on a conflict.",
        )
    ]
    coordination.problem = SceneCoordinationProblem(
        type=SceneCoordinationProblemType.REACTION_TRIGGER,
        time_offset_seconds=1,
        involved_actor_ids=["character_2", "missing_character"],
        description="A reaction may be needed.",
        needs_user_decision=False,
    )

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
    database.character.get_user_character_by_simulation = AsyncMock(return_value=actor_1)
    database.character.get_character = AsyncMock(side_effect=lambda actor_id: actors.get(actor_id))
    database.location.get_location_by_character = AsyncMock(return_value=location)
    narrator = Narrator(database=database)

    context = await narrator._build_context(
        world_id=world.id,
        simulation_id=simulation.id,
        coordination_result=coordination,
        user_input="Continue.",
    )

    assert [actor.character.id for actor in context.actors] == ["character_1", "character_2"]
    assert all(actor.location == location for actor in context.actors)
