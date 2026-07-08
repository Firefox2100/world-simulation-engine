from neo4j import AsyncDriver

from world_simulation_engine.model import Container


def _container_from_node(container_node) -> Container:
    return Container(
        id=container_node["id"],
        name=container_node["name"],
        description=container_node["description"],
        state=container_node["state"],
    )


class ContainerStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self.driver = driver

    async def create_container(self, container: Container):
        await self.driver.execute_query(
            """
            CREATE (c:Container {
                id: $id,
                name: $name,
                description: $description,
                state: $state,
            })
            """,
            parameters_={
                "id": container.id,
                "name": container.name,
                "description": container.description,
                "state": container.state,
            }
        )

    async def get_container(self, container_id: str) -> Container | None:
        result = await self.driver.execute_query(
            "MATCH (c:Container {id: $id}) RETURN c LIMIT 1",
            parameters_={"id": container_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _container_from_node(record)
