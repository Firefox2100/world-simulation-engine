from uuid import uuid4

from world_simulation_engine.model import Location
from world_simulation_engine.service.database.location_store import LocationStore


async def test_missing_location_returns_none(clean_neo4j):
    store = LocationStore(clean_neo4j)

    assert await store.get_location(str(uuid4())) is None


async def test_create_location(clean_neo4j):
    store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="City", description="A city")

    await store.create_location(location)

    assert await store.get_location(location.id) == location


async def test_create_location_with_parent_containment(clean_neo4j):
    store = LocationStore(clean_neo4j)
    parent = Location(id=str(uuid4()), name="City", description="A city")
    child = Location(id=str(uuid4()), name="Market", description="A market")

    await store.create_location(parent)
    await store.create_location(child, contained_in=parent.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Location {id: $parent_id})-[:CONTAINS]->(:Location {id: $child_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"parent_id": parent.id, "child_id": child.id},
    )
    assert result.records[0]["link_count"] == 1
