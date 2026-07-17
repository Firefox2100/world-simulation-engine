from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.model import Simulation
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.world_store import WorldStore
from tests.integration_test.database_service.helpers import create_world, make_author, make_world


async def test_missing_simulation_returns_none(clean_neo4j):
    store = SimulationStore(clean_neo4j)

    assert await store.get_simulation(str(uuid4())) is None


async def test_create_simulation(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = SimulationStore(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    await store.create_simulation(simulation, world.id)

    assert await store.get_simulation(simulation.id) == simulation

    result = await clean_neo4j.execute_query(
        """
        MATCH (simulation:Simulation {id: $simulation_id})-[:BASED_ON]->(world:World {id: $world_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"simulation_id": simulation.id, "world_id": world.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_create_simulation_returns_none_when_world_is_missing(clean_neo4j):
    store = SimulationStore(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    assert await store.create_simulation(simulation, str(uuid4())) is None
    assert await store.get_simulation(simulation.id) is None


async def test_list_update_and_delete_simulation(clean_neo4j):
    first_world = await create_world(clean_neo4j)
    second_world = await create_world(clean_neo4j)
    store = SimulationStore(clean_neo4j)
    first_simulation = Simulation(
        id=str(uuid4()),
        name="A Test Simulation",
        description="A test simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    second_simulation = Simulation(
        id=str(uuid4()),
        name="B Test Simulation",
        description="Another test simulation",
        current_time=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
    )

    await store.create_simulation(first_simulation, first_world.id)
    await store.create_simulation(second_simulation, second_world.id)

    assert await store.list_simulations() == [first_simulation, second_simulation]
    assert await store.list_simulations(limit=1) == [first_simulation]
    assert await store.list_simulations(limit=1, skip=1) == [second_simulation]
    assert await store.list_simulations(skip=2) == []
    assert await store.list_simulations(world_id=first_world.id) == [first_simulation]

    updated_simulation = await store.update_simulation(
        first_simulation.id,
        {
            "name": "Updated Simulation",
            "description": "An updated test simulation",
            "current_time": datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        },
    )

    assert updated_simulation == first_simulation.model_copy(
        update={
            "name": "Updated Simulation",
            "description": "An updated test simulation",
            "current_time": datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        }
    )
    assert await store.get_simulation(first_simulation.id) == updated_simulation
    assert await store.update_simulation(str(uuid4()), {"name": "Missing Simulation"}) is None

    assert await store.delete_simulation(first_simulation.id) is True
    assert await store.get_simulation(first_simulation.id) is None
    assert await store.delete_simulation(first_simulation.id) is False
    assert await store.list_simulations() == [second_simulation]


async def test_list_simulations_filters_by_author_and_world(clean_neo4j):
    world_store = WorldStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    author = make_author()
    other_author = make_author()
    world = make_world()
    other_world = make_world()
    simulation = Simulation(
        id=str(uuid4()),
        name="A Test Simulation",
        description="A test simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    other_simulation = Simulation(
        id=str(uuid4()),
        name="B Test Simulation",
        description="Another test simulation",
        current_time=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
    )

    await world_store.create_author(author)
    await world_store.create_author(other_author)
    await world_store.create_world(world, author.id)
    await world_store.create_world(other_world, other_author.id)
    await simulation_store.create_simulation(simulation, world.id)
    await simulation_store.create_simulation(other_simulation, other_world.id)

    assert await simulation_store.list_simulations(author_id=author.id) == [simulation]
    assert await simulation_store.list_simulations(author_id=author.id, limit=1, skip=0) == [simulation]
    assert await simulation_store.list_simulations(
        author_id=author.id,
        world_id=world.id,
    ) == [simulation]
    assert await simulation_store.list_simulations(
        author_id=author.id,
        world_id=other_world.id,
    ) == []
