import os
from unittest.mock import AsyncMock, Mock
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.misc.enums import ActionType, SupportedLanguage
from world_simulation_engine.model import CurrentActivity, Character, InputInterpretation, OOCCommand, ProposedAction, \
    Simulation, World, Location


def test_split_ooc_markers_preserves_source_order():
    raw_input = 'I turn to Bob.\n[/OOC: Keep it short.]\n"Hello."'

    segments = InputInterpreter._split_ooc_markers(raw_input)

    assert [segment.type for segment in segments] == ["in_world", "ooc", "in_world"]
    assert segments[0].source_text == "I turn to Bob.\n"
    assert segments[1].source_text == "[/OOC: Keep it short.]"
    assert segments[1].command_text == "Keep it short."
    assert segments[2].source_text == '\n"Hello."'


def test_split_ooc_markers_requires_closed_exact_marker():
    raw_input = "I mention OOC briefly. [/ooc: not exact] [/OOC: missing close"

    segments = InputInterpreter._split_ooc_markers(raw_input)

    assert len(segments) == 1
    assert segments[0].type == "in_world"
    assert segments[0].source_text == raw_input


def test_input_interpretation_accepts_ooc_sequence_item():
    interpretation = InputInterpretation(
        items=[
            OOCCommand(
                command_text="Keep it short.",
                normalized_intent="Keep future narration concise.",
                source_text="[/OOC: Keep it short.]",
            )
        ],
    )

    assert interpretation.items[0].type == "ooc"


def test_ooc_sequence_item_requires_exact_marker_source_text():
    with pytest.raises(ValidationError):
        InputInterpretation.model_validate(
            {
                "items": [
                    {
                        "type": "ooc",
                        "command_text": "If Clara seems willing to speak privately",
                        "normalized_intent": "Treat the condition as OOC.",
                        "source_text": "If Clara seems willing to speak privately",
                    }
                ]
            }
        )


def test_ooc_sequence_item_command_text_must_match_marker():
    with pytest.raises(ValidationError):
        InputInterpretation.model_validate(
            {
                "items": [
                    {
                        "type": "ooc",
                        "command_text": "Keep it brief.",
                        "normalized_intent": "Keep future narration concise.",
                        "source_text": "[/OOC: Keep it short.]",
                    }
                ]
            }
        )


def test_input_interpretation_accepts_action_sequence_item():
    interpretation = InputInterpretation(
        items=[
            {
                "type": "action",
                "action": ProposedAction(
                    type=ActionType.LOOK,
                    label="look_around",
                    target_ids=[],
                    intended_duration_seconds=2,
                    interruptible=True,
                ),
                "source_text": "I look around.",
            }
        ],
    )

    assert interpretation.items[0].type == "action"
    assert interpretation.items[0].action.type == ActionType.LOOK


@pytest.mark.parametrize("wrapper_key", ["input_interpretation", "interpretation"])
def test_input_interpretation_accepts_known_llm_wrapper_keys(wrapper_key):
    interpretation = InputInterpretation.model_validate(
        {
            wrapper_key: [
                {
                    "type": "action",
                    "action": {
                        "type": "look",
                        "label": "look_around",
                        "target_ids": [],
                        "intended_duration_seconds": 2,
                        "interruptible": True,
                    },
                    "source_text": "I look around.",
                }
            ]
        }
    )

    assert interpretation.items[0].type == "action"
    assert interpretation.items[0].action.type == ActionType.LOOK


def test_input_interpretation_accepts_model_type_discriminator_wrapper():
    interpretation = InputInterpretation.model_validate(
        {
            "type": "InputInterpretation",
            "items": [
                {
                    "type": "ooc",
                    "command_text": "Keep it short.",
                    "normalized_intent": "Keep future narration concise.",
                    "source_text": "[/OOC: Keep it short.]",
                }
            ],
        }
    )

    assert interpretation.items[0].type == "ooc"


def test_input_interpretation_discards_blank_unparsed_text_from_llm():
    interpretation = InputInterpretation.model_validate(
        {
            "items": [],
            "unparsed_text": ["", "   ", "unclear fragment"],
            "parser_notes": [],
        }
    )

    assert interpretation.unparsed_text == ["unclear fragment"]


def test_input_interpretation_moves_misplaced_action_label_into_action():
    interpretation = InputInterpretation.model_validate(
        {
            "items": [
                {
                    "type": "action",
                    "source_text": "I study the Notice Board.",
                    "label": "study_notice_board",
                    "action": {
                        "type": "observe",
                        "target_ids": ["landmark_notice_board"],
                        "intended_duration_seconds": 10,
                        "interruptible": True,
                        "interruption_triggers": [],
                        "required_preconditions": [],
                        "expected_effects": [],
                    },
                }
            ],
            "unparsed_text": [],
            "parser_notes": [],
        }
    )

    assert interpretation.items[0].type == "action"
    assert interpretation.items[0].action.type == ActionType.OBSERVE
    assert interpretation.items[0].action.label == "study_notice_board"


def test_input_interpretation_wraps_flattened_action_payload():
    interpretation = InputInterpretation.model_validate(
        {
            "items": [
                {
                    "type": "action",
                    "source_text": "Arthur shows Clara the signature line.",
                    "label": "show_letter_and_ask_handwriting",
                    "target_ids": ["character_clara_whitlock"],
                    "utterance": None,
                    "intended_duration_seconds": 6,
                    "interruptible": True,
                    "interruption_triggers": [],
                    "required_preconditions": [],
                    "expected_effects": [
                        "clara_views_signature_line",
                        "clara_hears_question",
                    ],
                }
            ],
            "unparsed_text": [],
            "parser_notes": [],
        }
    )

    assert interpretation.items[0].type == "action"
    assert interpretation.items[0].action.type == ActionType.OTHER
    assert interpretation.items[0].action.label == "show_letter_and_ask_handwriting"
    assert interpretation.items[0].action.target_ids == ["character_clara_whitlock"]


def test_input_interpretation_still_rejects_unknown_extra_fields():
    with pytest.raises(ValidationError):
        InputInterpretation.model_validate(
            {
                "items": [],
                "unexpected": "not allowed",
            }
        )


async def test_build_context_fetches_typed_database_state():
    world = World(
        id="world_1",
        name="World",
        description="A world",
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
    interpreter = InputInterpreter(database=database)
    segments = InputInterpreter._split_ooc_markers("I look around.")

    context = await interpreter._build_context(
        world_id=world.id,
        simulation_id=simulation.id,
        character_id=character.id,
        user_input="I look around.",
        input_segments=segments,
    )

    assert context.world == world
    assert context.simulation == simulation
    assert context.actor == character
    assert context.location == location
    assert context.input_segments == segments
