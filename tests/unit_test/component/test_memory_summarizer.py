import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.memory_summarizer import MemorySummarizer
from world_simulation_engine.misc.enums import ActionType, SceneCoordinationStatus, SupportedLanguage, TurnType
from world_simulation_engine.model import AcceptedSceneAction, Character, CurrentActivity, Location, MemorySummaryProposal, \
    ProposedAction, SceneCoordinationResult, Simulation, StateCommitProposal, Turn, World


def make_world() -> World:
    return World(
        id="world_1",
        name="World",
        description="A test world",
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


def make_turn() -> Turn:
    return Turn(
        id="turn_1",
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="Alex takes the glass.",
        start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
    )


def make_coordination() -> SceneCoordinationResult:
    return SceneCoordinationResult(
        status=SceneCoordinationStatus.COMPLETE,
        accepted_actions=[
            AcceptedSceneAction(
                actor_id="character_1",
                action_index=0,
                action=ProposedAction(
                    type=ActionType.TAKE,
                    label="take_glass",
                    target_ids=["item_glass"],
                    intended_duration_seconds=2,
                    interruptible=True,
                ),
                start_offset_seconds=0,
                end_offset_seconds=2,
                summary="Alex takes the glass.",
            )
        ],
    )


async def test_summarize_character_actions_invokes_structured_llm_with_context():
    database = Mock()
    database.world.get_world = AsyncMock(return_value=make_world())
    database.simulation.get_simulation = AsyncMock(return_value=make_simulation())
    database.character.get_character = AsyncMock(return_value=make_character())
    database.memory.get_recent_turn_memory_candidates = AsyncMock(return_value=[])
    database.intent.get_active_intent_candidates = AsyncMock(return_value=[])
    summarizer = MemorySummarizer(database=database)
    summarizer._prepare_llm_service = AsyncMock()
    expected = MemorySummaryProposal(
        operations=[
            {
                "type": "no_abstract_change",
                "reason": "No durable abstract state changed.",
            }
        ],
    )
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=expected)
    summarizer._prepare_llm_service.return_value = llm

    result = await summarizer.summarize_character_actions(
        world_id="world_1",
        simulation_id="simulation_1",
        turn=make_turn(),
        coordination_result=make_coordination(),
        state_commit=StateCommitProposal(),
        user_input="Continue.",
        narration="Alex takes the glass.",
    )

    assert result == expected
    llm.invoke_structured_with_repair.assert_awaited_once()
    data = llm.invoke_structured_with_repair.await_args.kwargs["data"]
    assert data["turn"]["id"] == "turn_1"
    assert data["coordination_result"]["accepted_actions"][0]["summary"] == "Alex takes the glass."


async def test_build_context_collects_sorted_unique_actors_and_skips_missing_characters():
    from world_simulation_engine.misc.enums import SceneCoordinationProblemType
    from world_simulation_engine.model import SceneCoordinationProblem

    character_1 = make_character()
    character_2 = Character(
        id="character_2",
        name="Blake",
        age=31,
        gender="unknown",
        appearance="Plain",
        description="A second character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )
    characters = {
        character_1.id: character_1,
        character_2.id: character_2,
    }
    coordination = make_coordination()
    coordination.problem = SceneCoordinationProblem(
        type=SceneCoordinationProblemType.CONTESTED_ACTION,
        time_offset_seconds=2,
        involved_actor_ids=["character_2", "missing_character", "character_1"],
        description="The action is contested.",
        needs_user_decision=True,
    )
    database = Mock()
    database.world.get_world = AsyncMock(return_value=make_world())
    database.simulation.get_simulation = AsyncMock(return_value=make_simulation())
    database.character.get_character = AsyncMock(side_effect=lambda actor_id: characters.get(actor_id))
    database.memory.get_recent_turn_memory_candidates = AsyncMock(return_value=[])
    database.intent.get_active_intent_candidates = AsyncMock(return_value=[])
    summarizer = MemorySummarizer(database=database)

    context = await summarizer._build_context(
        world_id="world_1",
        simulation_id="simulation_1",
        turn=make_turn(),
        coordination_result=coordination,
        state_commit=StateCommitProposal(),
        source="character",
    )

    assert [actor.actor.id for actor in context.actors] == ["character_1", "character_2"]
    assert database.memory.get_recent_turn_memory_candidates.await_count == 2
    assert database.intent.get_active_intent_candidates.await_count == 2
