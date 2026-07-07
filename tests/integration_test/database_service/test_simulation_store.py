from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.model import Simulation
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_world


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
