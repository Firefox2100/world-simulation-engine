from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.model import StateCommitEntityRef, StateCommitFieldChange, StateCommitProposal
from world_simulation_engine.service.database.state_commit_store import StateCommitStore


class FakeNode(dict):
    pass


async def test_apply_state_commit_proposal_writes_state_and_relationship_changes():
    driver = SimpleNamespace(execute_query=AsyncMock(return_value=SimpleNamespace(records=[])))
    store = StateCommitStore(driver)
    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "state_change",
                    "entity": {
                        "type": "character",
                        "id": "character_1",
                    },
                    "field_changes": [
                        {
                            "field_path": "public_state",
                            "new_value": "holding a glass",
                            "reason": "Alex picked up a glass.",
                        }
                    ],
                    "reason": "Visible state changed.",
                },
                {
                    "type": "relationship_change",
                    "relationship_type": "held_by",
                    "subject": {
                        "type": "item_stack",
                        "id": "stack_1",
                    },
                    "object": {
                        "type": "character",
                        "id": "character_1",
                    },
                    "reason": "The stack is now held.",
                },
            ],
        }
    )

    await store.apply_state_commit_proposal(
        proposal=proposal,
        source_id="simulation_1",
        turn_id="turn_1",
    )

    assert driver.execute_query.await_count == 2
    state_call = driver.execute_query.await_args_list[0]
    relationship_call = driver.execute_query.await_args_list[1]
    assert "Character" in state_call.args[0]
    assert state_call.kwargs["parameters_"]["properties"] == {
        "public_state": "holding a glass",
    }
    assert "HOLDS" in relationship_call.args[0]
    assert relationship_call.kwargs["parameters_"]["subject_id"] == "character_1"
    assert relationship_call.kwargs["parameters_"]["object_id"] == "stack_1"


async def test_create_entity_serializes_nested_properties():
    driver = SimpleNamespace(execute_query=AsyncMock(return_value=SimpleNamespace(records=[])))
    store = StateCommitStore(driver)

    ref = await store.create_entity(
        entity_type="location",
        properties={
            "id": "location_1",
            "name": "Back Room",
            "metadata": {
                "source": "accepted:0",
            },
        },
        source_id="simulation_1",
        turn_id="turn_1",
    )

    assert ref.id == "location_1"
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert parameters["properties"]["metadata"] == '{"source": "accepted:0"}'


def test_safe_properties_drops_none_and_serializes_lists_and_dicts_but_keeps_datetimes():
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    properties = StateCommitStore._safe_properties(
        {
            "name": "Back Room",
            "none_value": None,
            "tags": ["quiet", "dim"],
            "metadata": {"source": "accepted:0"},
            "created_at": now,
        }
    )

    assert properties == {
        "name": "Back Room",
        "tags": '["quiet", "dim"]',
        "metadata": '{"source": "accepted:0"}',
        "created_at": now,
    }


def test_relationship_endpoints_reverse_inventory_or_ownership_relationships():
    stack = StateCommitEntityRef(type="item_stack", id="stack_1")
    character = StateCommitEntityRef(type="character", id="character_1")
    container = StateCommitEntityRef(type="container", id="container_1")

    assert StateCommitStore._relationship_endpoints("held_by", stack, character) == (character, stack)
    assert StateCommitStore._relationship_endpoints("owned_by", stack, character) == (character, stack)
    assert StateCommitStore._relationship_endpoints("inside", stack, container) == (container, stack)
    assert StateCommitStore._relationship_endpoints("near", character, container) == (character, container)


async def test_change_entity_state_skips_missing_id_and_empty_field_changes():
    driver = SimpleNamespace(execute_query=AsyncMock())
    store = StateCommitStore(driver)

    await store.change_entity_state(
        entity=StateCommitEntityRef(type="character", id=None),
        field_changes=[],
        turn_id="turn_1",
    )
    await store.change_entity_state(
        entity=StateCommitEntityRef(type="character", id="character_1"),
        field_changes=[],
        turn_id="turn_1",
    )

    driver.execute_query.assert_not_called()


async def test_change_entity_state_updates_character_current_activity_json():
    driver = SimpleNamespace(
        execute_query=AsyncMock(
            side_effect=[
                SimpleNamespace(
                    records=[
                        {
                            "current_activity": (
                                '{"name":"waiting","started_at":null,"expected_end":null,'
                                '"interruptible":true,"constraints":[]}'
                            ),
                        }
                    ],
                ),
                SimpleNamespace(records=[]),
            ],
        )
    )
    store = StateCommitStore(driver)

    await store.change_entity_state(
        entity=StateCommitEntityRef(type="character", id="character_1"),
        field_changes=[
            StateCommitFieldChange(
                field_path="current_activity.name",
                old_value=None,
                new_value="asking about Room 7",
                reason="The character is now asking about Room 7.",
            ),
        ],
        turn_id="turn_1",
    )

    assert driver.execute_query.await_count == 2
    update_call = driver.execute_query.await_args_list[1]
    parameters = update_call.kwargs["parameters_"]
    assert parameters["entity_id"] == "character_1"
    assert parameters["turn_id"] == "turn_1"
    assert '"name":"asking about Room 7"' in parameters["current_activity"]
    assert "current_activity.name" not in parameters["current_activity"]


async def test_change_relationship_marks_existing_relationship_ended_without_creating_new_one():
    driver = SimpleNamespace(execute_query=AsyncMock(return_value=SimpleNamespace(records=[])))
    store = StateCommitStore(driver)

    await store.change_relationship(
        relationship_type="held_by",
        subject=StateCommitEntityRef(type="item_stack", id="stack_1"),
        object=StateCommitEntityRef(type="character", id="character_1"),
        old_object=None,
        properties={},
        ended=True,
        turn_id="turn_1",
    )

    assert driver.execute_query.await_count == 1
    query = driver.execute_query.await_args.args[0]
    parameters = driver.execute_query.await_args.kwargs["parameters_"]
    assert "SET relationship.active = false" in query
    assert parameters == {
        "subject_id": "character_1",
        "object_id": "stack_1",
        "turn_id": "turn_1",
    }
