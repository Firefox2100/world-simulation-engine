from neo4j import AsyncDriver

from world_simulation_engine.model import Author, World


def _author_from_node(author_node) -> Author:
    return Author(
        id=author_node["id"],
        name=author_node["name"],
        url=author_node.get("url"),
    )


def _world_from_node(world_node) -> World:
    return World(
        id=world_node["id"],
        name=world_node["name"],
        description=world_node.get("description"),
        version=world_node["version"],
        url=world_node.get("url"),
        language=world_node["language"],
    )


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

        return _author_from_node(record["a"])

    async def get_author_by_world(self, world_id: str) -> Author | None:
        result = await self._driver.execute_query(
            "MATCH (a:Author)-[:CREATED]->(w:World {id: $id}) RETURN a",
            parameters_={"id": world_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _author_from_node(record["a"])

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
                version: $world_version,
                language: $world_language
            })
            MERGE (a)-[:CREATED]->(w)
            WITH w
            OPTIONAL MATCH (p:World {id: $previous_version})
            FOREACH (_ IN CASE
                WHEN $previous_version IS NOT NULL AND p IS NOT NULL
                THEN [1]
                ELSE []
            END |
                MERGE (w)-[:NEW_VERSION_OF]->(p)
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
                "world_language": world.language,
                "previous_version": previous_version,
            },
        )

    async def get_world(self, world_id: str) -> World | None:
        result = await self._driver.execute_query(
            "MATCH (w:World {id: $id}) RETURN w LIMIT 1",
            parameters_={"id": world_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _world_from_node(record["w"])
