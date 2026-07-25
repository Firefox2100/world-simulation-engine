import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.action_suggester import ActionSuggester
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import ActionSuggestionResult, Character, CurrentActivity, Location, \
    Simulation, World


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
        description="The user character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
        user_controlled=True,
    )


def make_database():
    world = make_world()
    simulation = make_simulation()
    character = make_character()
    location = Location(
        id="location_1",
        name="Tavern",
        description="A dim tavern",
    )

    database = Mock()
    database.world.get_world = AsyncMock(return_value=world)
    database.simulation.get_simulation = AsyncMock(return_value=simulation)
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


async def test_build_context_fetches_actor_scoped_scene_and_recent_narration():
    database = make_database()
    suggester = ActionSuggester(database=database)

    context = await suggester._build_context(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        recent_narration="Clara leans across the bar and whispers about a stranger.",
    )

    assert context.world.id == "world_1"
    assert context.simulation.id == "simulation_1"
    assert context.actor.id == "character_1"
    assert context.location.id == "location_1"
    assert "stranger" in context.recent_narration


async def test_suggest_actions_invokes_structured_llm():
    database = make_database()
    suggester = ActionSuggester(database=database)
    suggester._prepare_llm_service = AsyncMock()
    expected = ActionSuggestionResult(
        suggestions=[
            "Ask Clara who the stranger is.",
            "Observe the stranger closely from across the room.",
            "Say nothing and keep listening.",
        ],
    )
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=expected)
    suggester._prepare_llm_service.return_value = llm

    result = await suggester.suggest_actions(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        recent_narration="Clara leans across the bar and whispers about a stranger.",
    )

    assert result == expected
    llm.invoke_structured_with_repair.assert_awaited_once()
    assert llm.invoke_structured_with_repair.await_args.kwargs["output_model"] is ActionSuggestionResult
