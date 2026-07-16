from uuid import uuid4

from world_simulation_engine.model import Character, CurrentActivity, Location, Landmark, Simulation
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_world


async def test_missing_location_returns_none(clean_neo4j):
    store = LocationStore(clean_neo4j)

    assert await store.get_location(str(uuid4())) is None


async def test_create_location(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="City", description="A city")

    await store.create_location(location, source_id=world.id)

    assert await store.get_location(location.id) == location

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:Location {id: $location_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "location_id": location.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_create_location_returns_none_when_source_is_missing(clean_neo4j):
    store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="City", description="A city")

    assert await store.create_location(location, source_id=str(uuid4())) is None
    assert await store.get_location(location.id) is None


async def test_list_update_and_delete_location(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    first_location = Location(id=str(uuid4()), name="A City", description="A city")
    second_location = Location(id=str(uuid4()), name="B Market", description="A market")

    await store.create_location(first_location, source_id=world.id)
    await store.create_location(second_location, source_id=world.id)

    assert await store.list_locations() == [first_location, second_location]
    assert await store.list_locations(world_id=world.id) == [first_location, second_location]

    updated_location = await store.update_location(
        first_location.id,
        {
            "name": "Updated City",
            "description": "An updated city",
        },
    )

    assert updated_location == first_location.model_copy(
        update={
            "name": "Updated City",
            "description": "An updated city",
        }
    )
    assert await store.get_location(first_location.id) == updated_location
    assert await store.update_location(str(uuid4()), {"name": "Missing Location"}) is None

    assert await store.delete_location(first_location.id) is True
    assert await store.get_location(first_location.id) is None
    assert await store.delete_location(first_location.id) is False
    assert await store.list_locations(world_id=world.id) == [second_location]


async def test_create_location_with_parent_containment(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    parent = Location(id=str(uuid4()), name="City", description="A city")
    child = Location(id=str(uuid4()), name="Market", description="A market")

    await store.create_location(parent, source_id=world.id)
    await store.create_location(child, source_id=world.id, contained_in=parent.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Location {id: $parent_id})-[:CONTAINS]->(:Location {id: $child_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"parent_id": parent.id, "child_id": child.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_create_sub_location_uses_parent_source(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    parent = Location(id=str(uuid4()), name="City", description="A city")
    child = Location(id=str(uuid4()), name="Market", description="A market")

    await store.create_location(parent, source_id=world.id)
    assert await store.create_sub_location(child, parent.id) == child
    assert await store.list_locations(region_id=parent.id) == [child]
    assert await store.create_sub_location(child.model_copy(update={"id": str(uuid4())}), str(uuid4())) is None


async def test_get_location_by_character_present_in_location(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Library", description="Quiet shelves")
    await store.create_location(location, source_id=world.id)

    await clean_neo4j.execute_query(
        """
        CREATE (c:Character {id: $character_id})
        WITH c
        MATCH (loc:Location {id: $location_id})
        MERGE (c)-[:PRESENT_IN]->(loc)
        """,
        parameters_={"character_id": str(uuid4()), "location_id": location.id},
    )

    character_id = (
        await clean_neo4j.execute_query("MATCH (c:Character) RETURN c.id AS id LIMIT 1")
    ).records[0]["id"]

    assert await store.get_location_by_character(character_id) == location


async def test_create_landmark_and_get_location_by_character_anchor(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Library", description="Quiet shelves")
    landmark = Landmark(id=str(uuid4()), name="Front Desk", description="A reception desk")
    character_id = str(uuid4())

    await store.create_location(location, source_id=world.id)
    await store.create_landmark(landmark, location.id)
    await clean_neo4j.execute_query(
        """
        CREATE (c:Character {id: $character_id})
        WITH c
        MATCH (landmark:Landmark {id: $landmark_id})
        MERGE (c)-[:ANCHORED_TO]->(landmark)
        """,
        parameters_={"character_id": character_id, "landmark_id": landmark.id},
    )

    assert store.landmark_from_node(
        (await clean_neo4j.execute_query(
            "MATCH (landmark:Landmark {id: $id}) RETURN landmark",
            parameters_={"id": landmark.id},
        )).records[0]["landmark"]
    ) == landmark
    assert await store.get_location_by_character(character_id) == location


async def test_get_landmarks_by_location(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Lobby", description="A lobby")
    first = Landmark(id=str(uuid4()), name="Desk", description="A front desk")
    second = Landmark(id=str(uuid4()), name="Statue", description="A marble statue")

    await store.create_location(location, source_id=world.id)
    await store.create_landmark(second, location.id)
    await store.create_landmark(first, location.id)

    assert await store.get_landmarks_by_location(location.id) == [first, second]


async def test_copy_locations_preserves_nesting_landmarks_and_character_location(clean_neo4j):
    world = await create_world(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    city = Location(id=str(uuid4()), name="City", description="A city")
    market = Location(id=str(uuid4()), name="Market", description="A market")
    landmark = Landmark(id=str(uuid4()), name="Fountain", description="A fountain")
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
    simulation = await simulation_store.create_simulation(
        Simulation(
            id=str(uuid4()),
            name="Test Simulation",
            description="A test simulation",
            current_time=world.starting_time,
        ),
        world.id,
    )

    await location_store.create_location(city, source_id=world.id)
    await location_store.create_location(market, source_id=world.id, contained_in=city.id)
    await location_store.create_landmark(landmark, market.id)
    await character_store.create_character(character, world.id)
    await character_store.move_to_location(character.id, market.id, position="near the stalls")
    await character_store.anchor_to_landmark(character.id, landmark.id)

    copied_locations, location_pairs, landmark_pairs = await location_store.copy_locations(world.id, simulation.id)
    copied_characters = await character_store.copy_characters(
        world.id,
        simulation.id,
        location_pairs=location_pairs,
        landmark_pairs=landmark_pairs,
    )

    assert {
        location.name
        for location in copied_locations
    } == {"City", "Market"}
    assert all(location.id not in {city.id, market.id} for location in copied_locations)
    assert len(location_pairs) == 2
    assert len(landmark_pairs) == 1
    assert len(copied_characters) == 1

    copied_market_id = next(pair["copy_id"] for pair in location_pairs if pair["source_id"] == market.id)
    copied_city_id = next(pair["copy_id"] for pair in location_pairs if pair["source_id"] == city.id)
    copied_landmark_id = landmark_pairs[0]["copy_id"]
    copied_character = copied_characters[0]

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(:Location {id: $copied_market_id})
        MATCH (:Location {id: $copied_city_id})-[:CONTAINS]->(:Location {id: $copied_market_id})
        MATCH (:Location {id: $copied_market_id})-[:CONTAINS]->(:Landmark {id: $copied_landmark_id})
        MATCH (:Character {id: $copied_character_id})-[present:PRESENT_IN]->(:Location {id: $copied_market_id})
        MATCH (:Character {id: $copied_character_id})-[:ANCHORED_TO]->(:Landmark {id: $copied_landmark_id})
        RETURN present.position AS position
        """,
        parameters_={
            "simulation_id": simulation.id,
            "copied_city_id": copied_city_id,
            "copied_market_id": copied_market_id,
            "copied_landmark_id": copied_landmark_id,
            "copied_character_id": copied_character.id,
        },
    )

    assert result.records[0]["position"] == "near the stalls"
