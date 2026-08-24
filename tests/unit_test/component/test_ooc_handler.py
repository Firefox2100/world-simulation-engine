import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.ooc_handler import OOCHandler
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Character, CurrentActivity, Location, OOCCommand, OOCEvaluationResult, \
    OOCWorldStateMutation, Simulation, World


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
    )


def make_command(index: int = 0) -> OOCCommand:
    return OOCCommand(
        type="ooc",
        command_text="the chest under the bar contains a ledger",
        normalized_intent="Place a ledger inside the chest.",
        source_text="[/OOC: the chest under the bar contains a ledger]",
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
    database.trigger.list_triggers = AsyncMock(return_value=[])

    return database


async def test_build_context_fetches_actor_scoped_scene_and_commands():
    database = make_database()
    handler = OOCHandler(database=database)
    command = make_command()

    context = await handler._build_context(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        commands=[command],
    )

    assert context.world.id == "world_1"
    assert context.simulation.id == "simulation_1"
    assert context.actor.id == "character_1"
    assert context.location.id == "location_1"
    assert context.commands[0].command_index == 0
    assert context.commands[0].command == command


async def test_evaluate_commands_returns_empty_result_without_commands():
    database = make_database()
    handler = OOCHandler(database=database)

    result = await handler.evaluate_commands(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        commands=[],
    )

    assert result == OOCEvaluationResult(items=[], evaluator_notes=["No OOC commands were supplied."])


async def test_evaluate_commands_invokes_structured_llm_and_restores_command_text():
    database = make_database()
    handler = OOCHandler(database=database)
    handler._prepare_llm_service = AsyncMock()
    command = make_command()

    raw_result = OOCEvaluationResult(
        items=[
            OOCWorldStateMutation(
                category="world_state_mutation",
                command_index=0,
                command_text="a hallucinated different command text",
                operations=[],
                consistent=True,
                issues=[],
                reason="Placed the ledger in the chest.",
            )
        ],
    )
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(return_value=raw_result)
    handler._prepare_llm_service.return_value = llm

    result = await handler.evaluate_commands(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        commands=[command],
    )

    llm.invoke_structured_with_repair.assert_awaited_once()
    assert llm.invoke_structured_with_repair.await_args.kwargs["output_model"] is OOCEvaluationResult
    assert result.items[0].command_text == command.command_text
