import pytest
from pydantic import ValidationError

from world_simulation_engine.model import InputInterpretation, OOCCommand, UserActionSequenceItem


def test_input_interpretation_infers_action_type_when_missing():
    result = InputInterpretation.model_validate(
        {
            "items": [
                {
                    "action": {
                        "type": "move",
                        "label": "approach the bar",
                        "intended_duration_seconds": 3,
                    },
                    "source_text": "Arthur walks to the bar.",
                }
            ],
            "unparsed_text": [],
            "parser_notes": [],
        }
    )

    assert isinstance(result.items[0], UserActionSequenceItem)
    assert result.items[0].type == "action"
    assert result.items[0].action.label == "approach the bar"


def test_input_interpretation_infers_ooc_type_when_missing():
    result = InputInterpretation.model_validate(
        {
            "items": [
                {
                    "command_text": "skip time",
                    "normalized_intent": "The user wants to skip ahead in time.",
                    "source_text": "[/OOC: skip time]",
                }
            ],
            "unparsed_text": [],
            "parser_notes": [],
        }
    )

    assert isinstance(result.items[0], OOCCommand)
    assert result.items[0].type == "ooc"


def test_input_interpretation_repairs_missing_type_alongside_misplaced_action_fields():
    # Local models sometimes both drop the "type" tag and misplace action-specific fields
    # directly on the item instead of nesting them under "action" - the two repairs must compose
    # (discriminator inference first, then UserActionSequenceItem's own field-flattening).
    result = InputInterpretation.model_validate(
        {
            "items": [
                {
                    "action": {"type": "move"},
                    "label": "approach the bar",
                    "intended_duration_seconds": 3,
                    "source_text": "Arthur walks to the bar.",
                }
            ],
            "unparsed_text": [],
            "parser_notes": [],
        }
    )

    item = result.items[0]
    assert item.type == "action"
    assert item.action.label == "approach the bar"
    assert item.action.intended_duration_seconds == 3


def test_input_interpretation_rejects_ambiguous_item_without_type():
    with pytest.raises(ValidationError):
        InputInterpretation.model_validate(
            {
                "items": [
                    {
                        "source_text": "Some source text with no distinguishing fields.",
                    }
                ],
                "unparsed_text": [],
                "parser_notes": [],
            }
        )
