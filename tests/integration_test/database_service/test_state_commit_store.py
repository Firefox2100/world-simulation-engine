from datetime import UTC, datetime
from uuid import uuid4

import pytest

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import StateCommitProposal, Turn
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.state_commit_store import StateCommitStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def _make_turn(clean_neo4j, world_id: str) -> Turn:
    turn = Turn(
        id=str(uuid4()),
        sequence=1,
        type=TurnType.SYSTEM_RESPONSE,
        content="A test turn.",
        start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    return await TurnStore(clean_neo4j).create_turn(turn, world_id)


async def test_apply_state_commit_proposal_writes_every_operation(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    turn = await _make_turn(clean_neo4j, world.id)
    store = StateCommitStore(clean_neo4j)

    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "state_change",
                    "entity": {"type": "character", "id": character.id},
                    "field_changes": [
                        {
                            "field_path": "public_state",
                            "new_value": "holding a lantern",
                            "reason": "The character picked up a lantern.",
                        }
                    ],
                    "reason": "Visible state changed.",
                },
                {
                    "type": "create",
                    "entity_type": "item",
                    "properties": {"name": "Lantern", "description": "A brass lantern", "unique": False},
                    "reason": "A new item was introduced.",
                },
            ],
        }
    )

    await store.apply_state_commit_proposal(proposal=proposal, source_id=world.id, turn_id=turn.id)

    reloaded_character = await CharacterStore(clean_neo4j).get_character(character.id)
    assert reloaded_character.public_state == "holding a lantern"

    result = await clean_neo4j.execute_query(
        "MATCH (:World {id: $world_id})-[:CONTAINS]->(i:Item) RETURN count(i) AS item_count",
        parameters_={"world_id": world.id},
    )
    assert result.records[0]["item_count"] == 1


async def test_apply_state_commit_proposal_rolls_back_all_operations_when_one_fails(clean_neo4j):
    # Regression test: apply_state_commit_proposal used to run each operation as its own
    # auto-committing query, so a failure partway through a multi-operation proposal left the
    # earlier operations permanently applied - a real, silent world-state inconsistency. This
    # proves the whole proposal now commits or rolls back as one unit against a real Neo4j
    # transaction, not just a mocked one.
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    turn = await _make_turn(clean_neo4j, world.id)
    store = StateCommitStore(clean_neo4j)
    original_public_state = character.public_state

    proposal = StateCommitProposal.model_validate(
        {
            "operations": [
                {
                    "type": "state_change",
                    "entity": {"type": "character", "id": character.id},
                    "field_changes": [
                        {
                            "field_path": "public_state",
                            "new_value": "should not persist",
                            "reason": "This write must be rolled back.",
                        }
                    ],
                    "reason": "First operation succeeds against the real transaction.",
                },
                {
                    "type": "state_change",
                    "entity": {"type": "character", "id": character.id},
                    "field_changes": [
                        {
                            "field_path": "private_state",
                            "new_value": "also should not persist",
                            "reason": "This write must also be rolled back.",
                        }
                    ],
                    "reason": "Second operation is forced to fail below.",
                },
            ],
        }
    )

    call_count = 0
    original_change_entity_state = store.change_entity_state

    async def failing_change_entity_state(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("simulated failure applying the second operation")
        return await original_change_entity_state(*args, **kwargs)

    store.change_entity_state = failing_change_entity_state

    with pytest.raises(RuntimeError, match="simulated failure"):
        await store.apply_state_commit_proposal(proposal=proposal, source_id=world.id, turn_id=turn.id)

    reloaded_character = await CharacterStore(clean_neo4j).get_character(character.id)
    assert reloaded_character.public_state == original_public_state
    assert reloaded_character.private_state == character.private_state
