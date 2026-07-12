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
