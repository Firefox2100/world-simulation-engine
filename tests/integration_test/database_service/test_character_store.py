from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.model import Character, CurrentActivity, Location
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.location_store import LocationStore
from tests.integration_test.database_service.helpers import create_world


async def test_missing_character_returns_none(clean_neo4j):
    store = CharacterStore(clean_neo4j)

    assert await store.get_character(str(uuid4())) is None


async def test_create_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    character = Character(
        id=str(uuid4()),
        name="Alex",
        age=30,
        gender="non-binary",
        appearance="Short hair and a practical coat",
        description="A test character",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(
            name="observing",
            started_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            expected_end=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            interruptible=True,
            constraints=["quiet"],
        ),
    )

    await store.create_character(character, world.id)

    assert await store.get_character(character.id) == character


async def test_move_to_location_replaces_previous_location(clean_neo4j):
    world = await create_world(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    character = Character(
        id=str(uuid4()),
        name="Alex",
        age=30,
        gender="non-binary",
        appearance="Short hair and a practical coat",
        description="A test character",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="observing"),
    )
    first_location = Location(id=str(uuid4()), name="Town Square", description="Open plaza")
    second_location = Location(id=str(uuid4()), name="Library", description="Quiet shelves")

    await character_store.create_character(character, world.id)
    await location_store.create_location(first_location)
    await location_store.create_location(second_location)
    await character_store.move_to_location(character.id, first_location.id)
    await character_store.move_to_location(character.id, second_location.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $character_id})-[:PRESENT_IN]->(location:Location)
        RETURN collect(location.id) AS location_ids
        """,
        parameters_={"character_id": character.id},
    )
    assert result.records[0]["location_ids"] == [second_location.id]
