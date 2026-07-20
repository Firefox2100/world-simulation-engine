import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.action_validator import ActionValidator
from world_simulation_engine.misc.enums import ActionType, SupportedLanguage
from world_simulation_engine.model import ActionValidationResult, Character, CurrentActivity, Location, ProposedAction, \
    Simulation, World


async def test_validate_actions_returns_empty_result_without_llm_for_no_actions():
    validator = ActionValidator(database=Mock())
    validator._prepare_llm_service = AsyncMock()

    result = await validator.validate_actions(
        world_id="world_1",
        simulation_id="simulation_1",
        character_id="character_1",
        actions=[],
    )

    assert result.validations == []
    assert result.validator_notes == ["No actions were supplied for validation."]
    validator._prepare_llm_service.assert_not_called()


async def test_build_context_fetches_typed_database_state():
    world = World(
        id="world_1",
        name="World",
        description="A grounded modern world",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    character = Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="The actor",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )
    location = Location(
        id="location_1",
        name="Room",
        description="A small room",
    )
    action = ProposedAction(
        type=ActionType.LOOK,
        label="look_around",
        target_ids=[],
        intended_duration_seconds=2,
        interruptible=True,
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
    database.memory.get_recent_turn_memory_candidates = AsyncMock(return_value=[])
    database.intent.get_active_intent_candidates = AsyncMock(return_value=[])
    validator = ActionValidator(database=database)

    context = await validator._build_context(
        world_id=world.id,
        simulation_id=simulation.id,
        character_id=character.id,
        actions=[action],
    )

    assert context.world == world
    assert context.simulation == simulation
    assert context.actor == character
    assert context.location == location
    assert context.actions == [action]
    assert context.active_intents == []
    assert context.recent_memories == []


async def test_validate_actions_preserves_original_action_payload_from_llm_echo_drift():
    world = World(
        id="world_1",
        name="World",
        description="A grounded modern world",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id="simulation_1",
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    character = Character(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="The actor",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )
    location = Location(
        id="location_1",
        name="Room",
        description="A small room",
    )
    action = ProposedAction(
        type=ActionType.SPEAK,
        label="answer_question",
        target_ids=["character_2"],
        utterance="Yes, the room was occupied.",
        intended_duration_seconds=4,
        interruptible=True,
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
    database.memory.get_recent_turn_memory_candidates = AsyncMock(return_value=[])
    database.intent.get_active_intent_candidates = AsyncMock(return_value=[])
    validator = ActionValidator(database=database)
    validator._prepare_llm_service = AsyncMock()
    llm = Mock()
    llm.invoke_structured_with_repair = AsyncMock(
        return_value=ActionValidationResult(
            validations=[
                {
                    "action_index": 0,
                    "action": {
                        "type": "speak",
                        "label": "answer_question",
                        "target_ids": [],
                        "utterance": None,
                        "intended_duration_seconds": 4,
                        "interruptible": True,
                    },
                    "allowed": True,
                    "reason": "Allowed.",
                }
            ],
        )
    )
    validator._prepare_llm_service.return_value = llm

    result = await validator.validate_actions(
        world_id=world.id,
        simulation_id=simulation.id,
        character_id=character.id,
        actions=[action],
    )

    assert result.validations[0].action == action
