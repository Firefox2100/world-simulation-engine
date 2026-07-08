from uuid import uuid4

from world_simulation_engine.model import Location, Landmark
from world_simulation_engine.service.database.location_store import LocationStore
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
