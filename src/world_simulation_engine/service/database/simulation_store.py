from neo4j import AsyncDriver

from world_simulation_engine.model import Simulation


def _simulation_from_node(simulation_node) -> Simulation:
    current_time = simulation_node["current_time"]
    if hasattr(current_time, "to_native"):
        current_time = current_time.to_native()

    return Simulation(
        id=simulation_node["id"],
        name=simulation_node["name"],
        description=simulation_node.get("description"),
        current_time=current_time,
    )


class SimulationStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_simulation(self,
                                simulation: Simulation,
                                world_id: str,
                                ):
        await self._driver.execute_query(
            """
            MATCH (w:World {id: $world_id})
            CREATE (s:Simulation {
                id: $simulation_id,
                name: $world_name,
                description: $world_description,
                current_time: $current_time
            })
            CREATE (s)-[:BASED_ON]->(w)
            RETURN s
            """,
            parameters_={
                "simulation_id": simulation.id,
                "world_id": world_id,
                "world_name": simulation.name,
                "world_description": simulation.description,
                "current_time": simulation.current_time,
            },
        )

    async def get_simulation(self, simulation_id: str) -> Simulation | None:
        result = await self._driver.execute_query(
            "MATCH (s:Simulation {id: $id}) RETURN s LIMIT 1",
            parameters_={
                "id": simulation_id,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _simulation_from_node(record["s"])

    async def update_current_time(self,
                                  simulation_id: str,
                                  current_time,
                                  ) -> Simulation:
        result = await self._driver.execute_query(
            """
            MATCH (s:Simulation {id: $id})
            SET s.current_time = $current_time
            RETURN s
            """,
            parameters_={
                "id": simulation_id,
                "current_time": current_time,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            raise ValueError(f"Simulation {simulation_id} not found")

        return _simulation_from_node(record["s"])
