import pytest
from pydantic import ValidationError

from world_simulation_engine.model import OOCCharacterActionGuide, OOCEvaluationResult, OOCTriggerDirective, \
    OOCTriggerDraft, OOCWorldStateMutation


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


def _minimal_trigger_draft(**overrides) -> dict:
    draft = {
        "name": "Zombie outbreak begins",
        "description": "Long-term script thread.",
        "condition": {"type": "time", "operator": "gte", "value": "2027-01-01T00:00:00"},
        "effect_kind": "event",
        "effects": [
            {"type": "narrative_beat", "directive": "Reports of unrest spread.", "relevant_character_ids": []}
        ],
    }
    draft.update(overrides)
    return draft


def test_ooc_evaluation_infers_trigger_directive_category_when_missing():
    result = OOCEvaluationResult.model_validate(
        {
            "items": [
                {
                    "command_index": 0,
                    "command_text": "in 3 months a zombie outbreak begins",
                    "operation": "create",
                    "draft": _minimal_trigger_draft(),
                    "consistent": True,
                    "issues": [],
                    "reason": "Authored a long-term scripted trigger.",
                }
            ]
        }
    )

    assert isinstance(result.items[0], OOCTriggerDirective)
    assert result.items[0].category == "trigger_directive"


def test_ooc_trigger_directive_create_forbids_trigger_id():
    with pytest.raises(ValidationError):
        OOCTriggerDirective.model_validate(
            {
                "category": "trigger_directive",
                "command_index": 0,
                "command_text": "in 3 months a zombie outbreak begins",
                "operation": "create",
                "trigger_id": "trigger_1",
                "draft": _minimal_trigger_draft(),
                "consistent": True,
                "reason": "Authored a long-term scripted trigger.",
            }
        )


def test_ooc_trigger_directive_create_requires_draft():
    with pytest.raises(ValidationError):
        OOCTriggerDirective.model_validate(
            {
                "category": "trigger_directive",
                "command_index": 0,
                "command_text": "in 3 months a zombie outbreak begins",
                "operation": "create",
                "consistent": True,
                "reason": "Authored a long-term scripted trigger.",
            }
        )


def test_ooc_trigger_directive_update_requires_trigger_id_and_draft():
    with pytest.raises(ValidationError):
        OOCTriggerDirective.model_validate(
            {
                "category": "trigger_directive",
                "command_index": 0,
                "command_text": "push the outbreak back",
                "operation": "update",
                "consistent": True,
                "reason": "Redefines an existing trigger.",
            }
        )

    valid = OOCTriggerDirective.model_validate(
        {
            "category": "trigger_directive",
            "command_index": 0,
            "command_text": "push the outbreak back",
            "operation": "update",
            "trigger_id": "trigger_1",
            "draft": _minimal_trigger_draft(),
            "consistent": True,
            "reason": "Redefines an existing trigger.",
        }
    )
    assert valid.trigger_id == "trigger_1"


def test_ooc_trigger_directive_set_status_requires_trigger_id_and_status():
    with pytest.raises(ValidationError):
        OOCTriggerDirective.model_validate(
            {
                "category": "trigger_directive",
                "command_index": 0,
                "command_text": "disable the outbreak trigger",
                "operation": "set_status",
                "trigger_id": "trigger_1",
                "consistent": True,
                "reason": "Disables an existing trigger.",
            }
        )

    valid = OOCTriggerDirective.model_validate(
        {
            "category": "trigger_directive",
            "command_index": 0,
            "command_text": "disable the outbreak trigger",
            "operation": "set_status",
            "trigger_id": "trigger_1",
            "status": "disabled",
            "consistent": True,
            "reason": "Disables an existing trigger.",
        }
    )
    assert valid.status == "disabled"


def test_ooc_trigger_directive_delete_requires_trigger_id():
    with pytest.raises(ValidationError):
        OOCTriggerDirective.model_validate(
            {
                "category": "trigger_directive",
                "command_index": 0,
                "command_text": "remove the outbreak trigger",
                "operation": "delete",
                "consistent": True,
                "reason": "Removes an existing trigger.",
            }
        )


def test_ooc_trigger_draft_repairs_missing_discriminator_in_state_mutation_effect_operations():
    # A trigger's state_mutation effect carries a nested StateCommitOperation list with the same
    # discriminator-omission risk as OOCWorldStateMutation.operations (see
    # test_ooc_world_state_mutation_unwraps_relationship_only_promotion_container above) - this
    # confirms OOCTriggerDraft applies the identical repair pass to it.
    draft = OOCTriggerDraft.model_validate(
        _minimal_trigger_draft(
            effects=[
                {
                    "type": "state_mutation",
                    "operations": [
                        {
                            "source_action_refs": [],
                            "reason": "No physical change is needed.",
                        }
                    ],
                    "note": "",
                }
            ]
        )
    )

    assert draft.effects[0].operations[0].type == "no_physical_change"


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
