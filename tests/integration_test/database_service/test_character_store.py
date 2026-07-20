from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.model import (
    BackgroundCharacter,
    Character,
    CurrentActivity,
    Landmark,
    Location,
    Simulation,
)
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_world


async def test_missing_character_returns_none(clean_neo4j):
    store = CharacterStore(clean_neo4j)

    assert await store.get_character(str(uuid4())) is None


async def test_create_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Market", description="A market")
    landmark = Landmark(id=str(uuid4()), name="Counter", description="A shop counter")
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

    await location_store.create_location(location, source_id=world.id)
    await location_store.create_landmark(landmark, location.id)
    await store.create_character(
        character,
        world.id,
        location_id=location.id,
        position="near the counter",
        landmark_id=landmark.id,
    )

    assert await store.get_character(character.id) == character
    assert await store.list_characters(location_id=location.id) == [character]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $character_id})-[present:PRESENT_IN]->(:Location {id: $location_id})
        MATCH (:Character {id: $character_id})-[:ANCHORED_TO]->(:Landmark {id: $landmark_id})
        RETURN present.position AS position
        """,
        parameters_={
            "character_id": character.id,
            "location_id": location.id,
            "landmark_id": landmark.id,
        },
    )
    assert result.records[0]["position"] == "near the counter"


async def test_create_character_returns_none_when_source_is_missing(clean_neo4j):
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
        current_activity=CurrentActivity(name="observing"),
    )

    assert await store.create_character(character, str(uuid4())) is None
    assert await store.get_character(character.id) is None


async def test_create_character_returns_none_when_relationship_target_is_missing(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    missing_location_character = Character(
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
    missing_landmark_character = missing_location_character.model_copy(update={"id": str(uuid4())})

    assert await store.create_character(
        missing_location_character,
        source_id=world.id,
        location_id=str(uuid4()),
    ) is None
    assert await store.create_character(
        missing_landmark_character,
        source_id=world.id,
        landmark_id=str(uuid4()),
    ) is None
    assert await store.get_character(missing_location_character.id) is None
    assert await store.get_character(missing_landmark_character.id) is None


async def test_list_update_and_delete_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    first_character = Character(
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
    second_character = Character(
        id=str(uuid4()),
        name="Blair",
        age=35,
        gender="female",
        appearance="A dark jacket",
        description="Another test character",
        public_state="Reading",
        private_state="Listening",
        current_activity=CurrentActivity(name="reading"),
    )

    await store.create_character(first_character, world.id)
    await store.create_character(second_character, world.id)

    assert await store.list_characters() == [first_character, second_character]
    assert await store.list_characters(world_id=world.id) == [first_character, second_character]

    updated_character = await store.update_character(
        first_character.id,
        {
            "name": "Updated Alex",
            "age": 31,
            "current_activity": CurrentActivity(
                name="walking",
                started_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            ),
        },
    )

    assert updated_character == first_character.model_copy(
        update={
            "name": "Updated Alex",
            "age": 31,
            "current_activity": CurrentActivity(
                name="walking",
                started_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            ),
        }
    )
    assert await store.get_character(first_character.id) == updated_character
    assert await store.update_character(str(uuid4()), {"name": "Missing Character"}) is None

    assert await store.delete_character(first_character.id) is True
    assert await store.get_character(first_character.id) is None
    assert await store.delete_character(first_character.id) is False
    assert await store.list_characters(world_id=world.id) == [second_character]


async def test_copy_characters_creates_new_ids_and_links_to_target_simulation(clean_neo4j):
    world = await create_world(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    source_character = Character(
        id=str(uuid4()),
        user_controlled=True,
        name="Alex",
        age=30,
        gender="non-binary",
        appearance="Short hair and a practical coat",
        description="A test character",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="observing"),
    )
    simulation = await simulation_store.create_simulation(
        simulation=Simulation(
            id=str(uuid4()),
            name="Test Simulation",
            description="A test simulation",
            current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        world_id=world.id,
    )

    await character_store.create_character(source_character, world.id)
    copied_characters = await character_store.copy_characters(world.id, simulation.id)

    assert len(copied_characters) == 1
    copied_character = copied_characters[0]
    assert copied_character.id != source_character.id
    assert copied_character.model_copy(update={"id": source_character.id}) == source_character
    assert await character_store.list_characters(simulation_id=simulation.id) == [copied_character]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(:Character {id: $character_id})
        RETURN count(*) AS link_count
        """,
        parameters_={
            "simulation_id": simulation.id,
            "character_id": copied_character.id,
        },
    )

    assert result.records[0]["link_count"] == 1


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
    assert await store.create_background_character(
        background_character,
        source_id=world.id,
        location_id=location.id,
        position="behind the counter",
    ) == background_character

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


async def test_create_background_character_returns_none_when_relationship_target_is_missing(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    missing_location_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Porter",
        description="A porter",
    )
    missing_landmark_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Guide",
        description="A guide",
    )

    assert await store.create_background_character(
        missing_location_character,
        source_id=world.id,
        location_id=str(uuid4()),
    ) is None
    assert await store.create_background_character(
        missing_landmark_character,
        source_id=world.id,
        landmark_id=str(uuid4()),
    ) is None
    assert await store.get_background_character(missing_location_character.id) is None
    assert await store.get_background_character(missing_landmark_character.id) is None


async def test_list_update_delete_and_move_background_character(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = CharacterStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    first_location = Location(id=str(uuid4()), name="Market", description="A market")
    second_location = Location(id=str(uuid4()), name="Docks", description="Busy docks")
    landmark = Landmark(id=str(uuid4()), name="Counter", description="A shop counter")
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )

    await location_store.create_location(first_location, source_id=world.id)
    await location_store.create_location(second_location, source_id=world.id)
    await location_store.create_landmark(landmark, second_location.id)
    await store.create_background_character(background_character, source_id=world.id)

    assert await store.list_background_characters() == [background_character]
    assert await store.list_background_characters(world_id=world.id) == [background_character]

    updated_character = await store.update_background_character(
        background_character.id,
        {
            "name": "Updated Shopkeeper",
            "description": "An updated shopkeeper",
        },
    )

    assert updated_character == BackgroundCharacter(
        id=background_character.id,
        name="Updated Shopkeeper",
        description="An updated shopkeeper",
    )
    assert await store.move_background_character_to_location(
        background_character.id,
        first_location.id,
        "beside the stall",
    ) == updated_character
    assert await store.list_background_characters(location_id=first_location.id) == [updated_character]
    assert await store.move_background_character_to_location(
        background_character.id,
        second_location.id,
    ) == updated_character
    assert await store.list_background_characters(location_id=first_location.id) == []
    assert await store.anchor_background_character_to_landmark(
        background_character.id,
        landmark.id,
    ) == updated_character
    assert await store.get_background_characters_by_location(second_location.id) == [
        (updated_character, second_location, None, landmark)
    ]
    assert await store.delete_background_character(background_character.id) is True
    assert await store.get_background_character(background_character.id) is None
    assert await store.delete_background_character(background_character.id) is False


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


async def test_copy_background_characters_preserves_location_and_landmark_relationships(clean_neo4j):
    world = await create_world(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Market", description="A market")
    landmark = Landmark(id=str(uuid4()), name="Counter", description="A shop counter")
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )
    simulation = await simulation_store.create_simulation(
        simulation=Simulation(
            id=str(uuid4()),
            name="Test Simulation",
            description="A test simulation",
            current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        world_id=world.id,
    )

    await location_store.create_location(location, source_id=world.id)
    await location_store.create_landmark(landmark, location.id)
    _, location_pairs, landmark_pairs = await location_store.copy_locations(world.id, simulation.id)
    await character_store.create_background_character(
        background_character,
        source_id=world.id,
        location_id=location.id,
        position="behind the counter",
        landmark_id=landmark.id,
    )
    copied_characters, character_pairs = await character_store.copy_background_characters(
        world.id,
        simulation.id,
        location_pairs=location_pairs,
        landmark_pairs=landmark_pairs,
    )

    assert len(copied_characters) == 1
    copied_character = copied_characters[0]
    assert copied_character.id != background_character.id
    assert copied_character.model_copy(update={"id": background_character.id}) == background_character
    assert character_pairs == [
        {
            "source_id": background_character.id,
            "copy_id": copied_character.id,
        }
    ]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(copy:BackgroundCharacter {id: $copy_id})
        MATCH (copy)-[present:PRESENT_IN]->(copy_location:Location)
        MATCH (copy)-[:ANCHORED_TO]->(copy_landmark:Landmark)<-[:CONTAINS]-(copy_location)
        RETURN present.position AS position, copy_location.id AS location_id, copy_landmark.id AS landmark_id
        """,
        parameters_={
            "simulation_id": simulation.id,
            "copy_id": copied_character.id,
        },
    )

    record = result.records[0]
    assert record["position"] == "behind the counter"
    assert record["location_id"] == location_pairs[0]["copy_id"]
    assert record["landmark_id"] == landmark_pairs[0]["copy_id"]
