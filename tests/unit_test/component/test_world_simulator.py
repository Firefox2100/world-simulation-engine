import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.world_simulator import WorldSimulator, WorldSimulatorState
from world_simulation_engine.misc.enums import ActionType, SupportedLanguage
from world_simulation_engine.model import ActionValidationResult, CurrentActivity, Character, InputInterpretation, \
    OOCCommand, ProposedAction, Simulation, World


def make_state(input_interpretation: InputInterpretation) -> WorldSimulatorState:
    return WorldSimulatorState(
        world=World(
            id="world_1",
            name="World",
            description="A test world",
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


async def test_validate_user_action_validates_interpreted_actions():
    action = ProposedAction(
        type=ActionType.LOOK,
        label="look_around",
        target_ids=[],
        intended_duration_seconds=2,
        interruptible=True,
    )
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
