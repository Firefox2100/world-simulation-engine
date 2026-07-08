from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.model import BackgroundCharacter, Character, CurrentActivity, Location, Landmark
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
    await location_store.create_location(first_location, source_id=world.id)
    await location_store.create_location(second_location, source_id=world.id)
    await character_store.move_to_location(character.id, first_location.id, position="near the fountain")
    await character_store.move_to_location(character.id, second_location.id, position="by the window")

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $character_id})-[r:PRESENT_IN]->(location:Location)
        RETURN collect(location.id) AS location_ids, collect(r.position) AS positions
        """,
        parameters_={"character_id": character.id},
    )
    assert result.records[0]["location_ids"] == [second_location.id]
    assert result.records[0]["positions"] == ["by the window"]


async def test_anchor_to_landmark_replaces_previous_landmark(clean_neo4j):
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
    location = Location(id=str(uuid4()), name="Library", description="Quiet shelves")
    first_landmark_id = str(uuid4())
    second_landmark_id = str(uuid4())

    await character_store.create_character(character, world.id)
    await location_store.create_location(location, source_id=world.id)
    await clean_neo4j.execute_query(
        """
        MATCH (loc:Location {id: $location_id})
        CREATE (loc)-[:CONTAINS]->(:Landmark {id: $first_id, name: 'Desk', description: 'A desk'})
        CREATE (loc)-[:CONTAINS]->(:Landmark {id: $second_id, name: 'Door', description: 'A door'})
        """,
        parameters_={
            "location_id": location.id,
            "first_id": first_landmark_id,
            "second_id": second_landmark_id,
        },
    )

    await character_store.anchor_to_landmark(character.id, first_landmark_id)
    await character_store.anchor_to_landmark(character.id, second_landmark_id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $character_id})-[:ANCHORED_TO]->(landmark:Landmark)
        RETURN collect(landmark.id) AS landmark_ids
        """,
        parameters_={"character_id": character.id},
    )
    assert result.records[0]["landmark_ids"] == [second_landmark_id]


async def test_create_background_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Market", description="A market")
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )

    await location_store.create_location(location, source_id=world.id)
    await store.create_background_character(
        background_character,
        source_id=world.id,
        location_id=location.id,
        position="behind the counter",
    )

    assert await store.get_background_character(background_character.id) == background_character
    assert await store.get_background_characters_by_location(location.id) == [
        (background_character, location, "behind the counter", None)
    ]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:BackgroundCharacter {id: $character_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "character_id": background_character.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_create_background_character_with_optional_landmark(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Market", description="A market")
    landmark = Landmark(id=str(uuid4()), name="Counter", description="A shop counter")
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )

    await location_store.create_location(location, source_id=world.id)
    await location_store.create_landmark(landmark, location.id)
    await store.create_background_character(
        background_character,
        source_id=world.id,
        location_id=location.id,
        position="behind the counter",
        landmark_id=landmark.id,
    )

    assert await store.get_background_characters_by_location(location.id) == [
        (background_character, location, "behind the counter", landmark)
    ]
