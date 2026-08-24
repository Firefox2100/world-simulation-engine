"""End-to-end verification of turn-version archiving and revert against a real Neo4j - drives
WorldSimulator._archive_current_turn_slot/revert_to_turn_version directly (bypassing the
LLM-driven graph, per the no-real-LLM-calls rule) to exercise the actual Cypher for archiving a
regenerated-away turn and bringing it back, including its paired world-state checkpoint."""

from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import TurnType, WorldStateCheckpointType
from world_simulation_engine.model import Simulation, Turn
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.component.simulator.world_simulator import WorldSimulator
from integration_test.database_service.helpers import create_character, create_world


async def _create_simulation(db: DatabaseService, world_id: str) -> Simulation:
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await db.simulation.create_simulation(simulation, world_id)
    return simulation


async def test_archive_and_revert_brings_back_the_discarded_turn_and_its_world_state(clean_neo4j):
    db = DatabaseService(clean_neo4j)
    simulator = WorldSimulator(database=db)

    world = await create_world(clean_neo4j)
    simulation = await _create_simulation(db, world.id)
    character = await create_character(clean_neo4j, simulation.id, name="Alice")

    user_turn = await db.turn.create_next_turn(
        turn=Turn(
            id=str(uuid4()), sequence=0, type=TurnType.USER_INPUT, content="I wave at Alice.",
            start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        source_id=simulation.id,
    )

    # First generated version of the reply turn: Alice nods, and her public_state reflects it.
    await db.character.update_character(character.id, {"public_state": "Nodding"})
    original_reply = await db.turn.create_next_turn(
        turn=Turn(
            id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="Alice nods.",
            start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
        ),
        source_id=simulation.id,
    )
    original_checkpoint = await simulator._checkpoint_service.capture(
        simulation_id=simulation.id,
        type=WorldStateCheckpointType.AFTER_CHARACTER_ROUND,
        turn=original_reply,
    )

    # Regenerate: archive the original, then replace it with a different version.
    await simulator._archive_current_turn_slot(simulation_id=simulation.id, turn_sequence=1)
    await db.turn.delete_turns_after(simulation.id, 0)
    await db.character.update_character(character.id, {"public_state": "Frowning"})
    replacement_reply = await db.turn.create_next_turn(
        turn=Turn(
            id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="Alice frowns.",
            start_time=datetime(2026, 1, 1, 12, 2, tzinfo=UTC),
        ),
        source_id=simulation.id,
    )
    assert replacement_reply.id != original_reply.id

    versions = await db.turn_version.list_versions(simulation_id=simulation.id, turn_sequence=1)
    assert len(versions) == 1
    archived_version = versions[0]
    assert archived_version.turn["content"] == "Alice nods."
    assert archived_version.checkpoint_id == original_checkpoint.id

    reverted_turn = await simulator.revert_to_turn_version(
        simulation_id=simulation.id, version_id=archived_version.id,
    )

    assert reverted_turn is not None
    assert reverted_turn.id == original_reply.id
    assert reverted_turn.content == "Alice nods."

    live_turn = await db.turn.get_turn_by_sequence(simulation.id, 1)
    assert live_turn.id == original_reply.id
    assert live_turn.content == "Alice nods."

    restored_character = await db.character.get_character(character.id)
    assert restored_character.public_state == "Nodding"

    # The replacement version was archived on the way out, so it's not lost either.
    versions_after_revert = await db.turn_version.list_versions(simulation_id=simulation.id, turn_sequence=1)
    assert {version.turn["content"] for version in versions_after_revert} == {"Alice nods.", "Alice frowns."}

    # And user_turn is untouched throughout.
    assert await db.turn.get_turn(user_turn.id) is not None
