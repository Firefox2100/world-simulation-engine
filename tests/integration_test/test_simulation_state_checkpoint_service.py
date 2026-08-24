"""End-to-end verification of SimulationStateCheckpointService against a real Neo4j - the unit
tests mock the driver and can't catch a wrong Cypher query, so this exercises the actual
capture -> mutate -> restore round-trip for the representative reconcile cases: overwrite an
existing entity back to its captured value, delete something created after the checkpoint, and
tail-delete turns."""

from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import TurnType, WorldStateCheckpointType
from world_simulation_engine.model import Simulation, Turn
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.simulation_state_checkpoint_service import SimulationStateCheckpointService
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


async def test_capture_and_restore_reverts_drift_since_the_checkpoint(clean_neo4j):
    db = DatabaseService(clean_neo4j)
    service = SimulationStateCheckpointService(db)

    world = await create_world(clean_neo4j)
    simulation = await _create_simulation(db, world.id)
    character = await create_character(clean_neo4j, simulation.id, name="Alex")

    turn_1 = await db.turn.create_next_turn(
        turn=Turn(
            id=str(uuid4()), sequence=0, type=TurnType.USER_INPUT, content="Alex looks around.",
            start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        source_id=simulation.id,
    )

    checkpoint = await service.capture(
        simulation_id=simulation.id,
        type=WorldStateCheckpointType.AFTER_USER_INPUT,
        turn=turn_1,
    )

    assert checkpoint.turn_sequence == 0
    assert len(checkpoint.characters) == 1
    assert checkpoint.characters[0]["entity"]["public_state"] == "Standing"

    # Drift since the checkpoint: mutate the existing character, commit a further turn, and
    # introduce a brand new character - none of this should survive the rollback.
    await db.character.update_character(character.id, {"public_state": "Startled"})
    turn_2 = await db.turn.create_next_turn(
        turn=Turn(
            id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="A crash startles Alex.",
            start_time=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
        ),
        source_id=simulation.id,
    )
    extra_character = await create_character(clean_neo4j, simulation.id, name="Bystander")

    await service.restore(simulation_id=simulation.id, checkpoint=checkpoint)

    restored_character = await db.character.get_character(character.id)
    assert restored_character is not None
    assert restored_character.public_state == "Standing"

    assert await db.character.get_character(extra_character.id) is None
    assert await db.turn.get_turn(turn_2.id) is None
    assert await db.turn.get_turn(turn_1.id) is not None
