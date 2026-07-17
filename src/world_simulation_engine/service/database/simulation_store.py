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
                                ) -> Simulation | None:
        result = await self._driver.execute_query(
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

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _simulation_from_node(record["s"])

    async def list_simulations(self,
                               author_id: str | None = None,
                               world_id: str | None = None,
                               limit: int | None = None,
                               skip: int = 0,
                               ) -> list[Simulation]:
        pagination = """
                SKIP $skip
        """
        if limit is not None:
            pagination += """
                LIMIT $limit
            """
        if author_id is not None and world_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Author {id: $author_id})-[:CREATED]->(:World {id: $world_id})<-[:BASED_ON]-(s:Simulation)
                RETURN s
                ORDER BY s.name
                """ + pagination,
                parameters_={
                    "author_id": author_id,
                    "world_id": world_id,
                    "limit": limit,
                    "skip": skip,
                },
            )
        elif author_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Author {id: $author_id})-[:CREATED]->(:World)<-[:BASED_ON]-(s:Simulation)
                RETURN s
                ORDER BY s.name
                """ + pagination,
                parameters_={
                    "author_id": author_id,
                    "limit": limit,
                    "skip": skip,
                },
            )
        elif world_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:World {id: $world_id})<-[:BASED_ON]-(s:Simulation)
                RETURN s
                ORDER BY s.name
                """ + pagination,
                parameters_={
                    "world_id": world_id,
                    "limit": limit,
                    "skip": skip,
                },
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (s:Simulation)
                RETURN s
                ORDER BY s.name
                """ + pagination,
                parameters_={
                    "limit": limit,
                    "skip": skip,
                },
            )

        return [
            _simulation_from_node(record["s"])
            for record in result.records
        ]

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

    async def update_simulation(self,
                                simulation_id: str,
                                properties: dict,
                                ) -> Simulation | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (s:Simulation {id: $id})
            SET s += $properties
            RETURN s LIMIT 1
            """,
            parameters_={
                "id": simulation_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _simulation_from_node(record["s"])

    async def delete_simulation(self, simulation_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (s:Simulation {id: $id})
            WITH s, 1 AS deleted
            OPTIONAL MATCH path = (s)-[:CONTAINS|HOLDS|PART_OF*0..]->(node)
            WITH deleted, collect(DISTINCT s) + collect(DISTINCT node) AS nodes
            FOREACH (node IN nodes | DETACH DELETE node)
            RETURN deleted
            """,
            parameters_={"id": simulation_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

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
