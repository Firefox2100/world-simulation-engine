from neo4j import AsyncDriver

from world_simulation_engine.model import Author, World


class WorldStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_author(self, author: Author):
        await self._driver.execute_query(
            "CREATE (a:Author {id: $id, name: $name, url: $url}) RETURN a",
            parameters_={
                "id": author.id,
                "name": author.name,
                "url": author.url,
            }
        )

    async def get_author(self, author_id: str) -> Author | None:
        result = await self._driver.execute_query(
            "MATCH (a:Author {id: $id}) RETURN a LIMIT 1",
            parameters_={"id": author_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        author_node = record["a"]

        return Author(
            id=author_node["id"],
            name=author_node["name"],
            url=author_node.get("url"),
        )

    async def get_author_of_world(self, world_id: str) -> Author | None:
        result = await self._driver.execute_query(
            "MATCH (a:Author)-[:CREATED]->(w:World {id: $id}) RETURN a",
            parameters_={"id": world_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        author_node = record["a"]

        return Author(
            id=author_node["id"],
            name=author_node["name"],
            url=author_node.get("url"),
        )

    async def create_world(self,
                           world: World,
                           author_id: str,
                           previous_version: str | None = None,
                           ):
        await self._driver.execute_query(
            """
            MATCH (a:Author {id: $author_id})
            CREATE (w:World {
                id: $world_id,
                name: $world_name,
                description: $world_description,
                url: $world_url,
                version: $world_version
            })
            CREATE (a)-[:CREATED]->(w)
            WITH w
            OPTIONAL MATCH (p:World {id: $previous_version})
            FOREACH (_ IN CASE
                WHEN $previous_version IS NOT NULL AND p IS NOT NULL
                THEN [1]
                ELSE []
            END |
                CREATE (w)-[:NEW_VERSION_OF]->(p)
            )
            RETURN w
            """,
            parameters_={
                "author_id": author_id,
                "world_id": world.id,
                "world_name": world.name,
                "world_description": world.description,
                "world_url": world.url,
                "world_version": world.version,
                "previous_version": previous_version,
            },
        )
