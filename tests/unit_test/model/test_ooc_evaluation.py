import pytest
from pydantic import ValidationError

from world_simulation_engine.model import OOCCharacterActionGuide, OOCEvaluationResult, OOCWorldStateMutation


def test_ooc_evaluation_infers_world_state_mutation_category_when_missing():
    result = OOCEvaluationResult.model_validate(
        {
            "items": [
                {
                    "command_index": 0,
                    "command_text": "give Arthur the key",
                    "consistent": True,
                    "operations": [
                        {
                            "type": "no_physical_change",
                            "source_action_refs": [],
                            "reason": "Placeholder operation for the test.",
                        }
                    ],
                    "reason": "The command grants an item.",
                }
            ]
        }
    )

    assert isinstance(result.items[0], OOCWorldStateMutation)
    assert result.items[0].category == "world_state_mutation"


def test_ooc_evaluation_infers_character_action_guide_category_when_missing():
    result = OOCEvaluationResult.model_validate(
        {
            "items": [
                {
                    "command_index": 0,
                    "command_text": "make Clara suspicious",
                    "character_id": "character_clara",
                    "actions": [
                        {
                            "type": "other",
                            "label": "narrow her eyes",
                            "intended_duration_seconds": 2,
                        }
                    ],
                    "reason": "Directs Clara's next action.",
                }
            ]
        }
    )

    assert isinstance(result.items[0], OOCCharacterActionGuide)
    assert result.items[0].category == "character_action_guide"
    assert result.items[0].actions[0].label == "narrow her eyes"


def test_ooc_evaluation_rejects_ambiguous_item_without_category():
    with pytest.raises(ValidationError):
        OOCEvaluationResult.model_validate(
            {
                "items": [
                    {
                        "command_index": 0,
                        "command_text": "do something",
                        "reason": "Neither shape's distinguishing fields are present.",
                    }
                ]
            }
        )


def test_ooc_world_state_mutation_unwraps_relationship_only_promotion_container():
    # Same failure observed for StateCommitProposal: a plain relationship_change wrapped in a
    # source_entity/target_entity_type container with no other promote-specific field populated.
    # OOCWorldStateMutation.operations reaches apply_state_commit_proposal exactly like
    # StateCommitProposal.operations, so it must get the same protection against a wrong
    # "promote" guess creating a spurious duplicate entity.
    mutation = OOCWorldStateMutation.model_validate(
        {
            "category": "world_state_mutation",
            "command_index": 0,
            "command_text": "force Arthur to confront Clara",
            "consistent": True,
            "operations": [
                {
                    "source_entity": {"type": "character", "id": "character_arthur"},
                    "target_entity_type": "character",
                    "reason": "Arthur is forced to confront Clara.",
                    "relationship_changes": [
                        {
                            "relationship_type": "interacting_with",
                            "subject": {"type": "character", "id": "character_arthur"},
                            "object": {"type": "character", "id": "character_clara"},
                            "old_object": None,
                            "reason": "OOC-forced confrontation.",
                        }
                    ],
                }
            ],
            "reason": "The OOC command forces a direct confrontation.",
        }
    )

    assert [operation.type for operation in mutation.operations] == ["relationship_change"]
    assert mutation.operations[0].relationship_type == "interacting_with"


def test_ooc_world_state_mutation_still_rejects_ambiguous_promotion_without_relationship_changes():
    with pytest.raises(ValidationError):
        OOCWorldStateMutation.model_validate(
            {
                "command_index": 0,
                "command_text": "turn the basket into a hat",
                "consistent": True,
                "operations": [
                    {
                        "source_entity": {"type": "item", "id": "item_basket"},
                        "target_entity_type": "equipment",
                        "reason": "The basket is now worn as a hat.",
                    }
                ],
                "reason": "The command promotes an item to equipment.",
            }
        )
