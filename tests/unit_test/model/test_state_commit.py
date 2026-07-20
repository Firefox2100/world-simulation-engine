import pytest
from pydantic import ValidationError

from world_simulation_engine.model import StateCommitProposal


def test_state_commit_proposal_accepts_physical_operation_mix():
    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "create",
                    "entity_type": "location",
                    "properties": {
                        "name": "Back Room",
                        "description": "A newly noticed room behind the bar.",
                    },
                    "reason": "The accepted movement revealed a new area.",
                },
                {
                    "type": "state_change",
                    "entity": {
                        "type": "character",
                        "id": "character_1",
                        "name": "Alex",
                    },
                    "field_changes": [
                        {
                            "field_path": "public_state",
                            "old_value": "standing",
                            "new_value": "holding a glass",
                            "reason": "Alex picked up the glass.",
                        }
                    ],
                    "reason": "A visible character state changed.",
                },
                {
                    "type": "promote",
                    "source_entity": {
                        "type": "item",
                        "id": "item_basket",
                        "name": "Basket",
                    },
                    "target_entity_type": "equipment",
                    "target_properties": {
                        "name": "Basket",
                        "equipped_position": "head",
                    },
                    "source_state_changes": [
                        {
                            "field_path": "description",
                            "new_value": "A basket currently worn as headgear.",
                            "reason": "The item is now functioning as equipment.",
                        }
                    ],
                    "reason": "The basket is now being worn.",
                },
                {
                    "type": "relationship_change",
                    "relationship_type": "equipped_by",
                    "subject": {
                        "type": "equipment",
                        "id": "equipment_basket",
                    },
                    "object": {
                        "type": "character",
                        "id": "character_1",
                    },
                    "properties": {
                        "equipped_position": "head",
                    },
                    "reason": "Alex put the basket on their head.",
                },
                {
                    "type": "no_physical_change",
                    "source_action_refs": ["accepted:2"],
                    "reason": "The action was speech only.",
                },
            ],
        }
    )

    assert [operation.type for operation in proposal.operations] == [
        "create",
        "state_change",
        "promote",
        "relationship_change",
        "no_physical_change",
    ]


def test_state_commit_proposal_rejects_operations_without_discriminator():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "operations": [
                    {
                        "entity": {
                            "type": "character",
                            "id": "character_1",
                        },
                        "reason": "Alex focuses their questioning on Room 7.",
                        "field_changes": [
                            {
                                "field_path": "current_activity.name",
                                "new_value": "asking about Room 7",
                                "old_value": None,
                                "reason": "The accepted action is a focused inquiry.",
                            }
                        ],
                        "source_action_refs": ["accepted:0"],
                    }
                ],
                "unchanged_action_refs": [],
                "committer_notes": [],
            }
        )


def test_state_commit_proposal_rejects_legacy_relationship_change_container():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "operations": [
                    {
                        "source_entity": {
                            "type": "character",
                            "id": "character_1",
                        },
                        "target_entity_type": "character",
                        "reason": "Clara speaks directly to Arthur regarding Room 7's occupancy status.",
                        "relationship_changes": [
                            {
                                "relationship_type": "interacting_with",
                                "subject": {
                                    "type": "character",
                                    "id": "character_1",
                                },
                                "reason": "Clara speaks directly to Arthur regarding Room 7's occupancy status.",
                                "object": {
                                    "type": "character",
                                    "id": "character_2",
                                },
                                "old_object": None,
                                "properties": {},
                                "ended": False,
                                "source_action_refs": ["accepted:0"],
                            }
                        ],
                        "source_action_refs": ["accepted:1", "accepted:0"],
                    },
                ],
                "unchanged_action_refs": [],
                "committer_notes": [],
            }
        )


def test_state_commit_proposal_accepts_explicit_state_and_relationship_changes():
    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "state_change",
                    "entity": {
                        "type": "character",
                        "id": "character_1",
                    },
                    "reason": "Arthur shifts focus and addresses Clara.",
                    "field_changes": [
                        {
                            "field_path": "current_activity.name",
                            "new_value": "questioning Clara about Room 7",
                            "reason": "accepted:0 shows Arthur asking a specific question.",
                        },
                    ],
                    "source_action_refs": ["accepted:0"],
                },
                {
                    "type": "relationship_change",
                    "relationship_type": "interacting_with",
                    "subject": {
                        "type": "character",
                        "id": "character_1",
                    },
                    "object": {
                        "type": "character",
                        "id": "character_2",
                    },
                    "old_object": None,
                    "properties": {},
                    "ended": False,
                    "source_action_refs": ["accepted:0"],
                    "reason": "accepted:0 shows Arthur speaking directly to Clara.",
                },
            ],
            "unchanged_action_refs": [],
            "committer_notes": [],
        }
    )

    assert [operation.type for operation in proposal.operations] == [
        "state_change",
        "relationship_change",
    ]
    assert proposal.operations[0].field_changes[0].field_path == "current_activity.name"
    assert proposal.operations[1].relationship_type == "interacting_with"
    assert proposal.operations[1].subject.id == "character_1"
    assert proposal.operations[1].object.id == "character_2"


def test_state_commit_proposal_rejects_incomplete_operation_fragments():
    with pytest.raises(ValidationError):
        StateCommitProposal.model_validate(
            {
                "operations": [
                    {
                        "type": "state_change",
                        "entity": {
                            "type": "character",
                            "id": "partial_character_id",
                        },
                    },
                ],
                "unchanged_action_refs": [],
                "committer_notes": [],
            }
        )
