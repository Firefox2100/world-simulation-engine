from neo4j import AsyncDriver

from world_simulation_engine.model import Author, World


def _author_from_node(author_node) -> Author:
    return Author(
        id=author_node["id"],
        name=author_node["name"],
        url=author_node.get("url"),
    )


def _world_from_node(world_node) -> World:
    starting_time = world_node["starting_time"]
    if hasattr(starting_time, "to_native"):
        starting_time = starting_time.to_native()

    return World(
        id=world_node["id"],
        name=world_node["name"],
        description=world_node.get("description"),
        starting_time=starting_time,
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

    async def list_authors(self) -> list[Author]:
        result = await self._driver.execute_query(
            """
            MATCH (a:Author)
            RETURN a
            ORDER BY a.name
            """
        )

        return [
            _author_from_node(record["a"])
            for record in result.records
        ]

    async def get_author(self, author_id: str) -> Author | None:
        result = await self._driver.execute_query(
            "MATCH (a:Author {id: $id}) RETURN a LIMIT 1",
            parameters_={"id": author_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _author_from_node(record["a"])

    async def update_author(self,
                            author_id: str,
                            properties: dict,
                            ) -> Author | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (a:Author {id: $id})
            SET a += $properties
            RETURN a LIMIT 1
            """,
            parameters_={
                "id": author_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _author_from_node(record["a"])

    async def delete_author(self, author_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (a:Author {id: $id})
            WITH collect(a) AS authors
            FOREACH (author IN authors | DETACH DELETE author)
            RETURN size(authors) AS deleted
            """,
            parameters_={"id": author_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def get_author_by_world(self, world_id: str) -> Author | None:
        result = await self._driver.execute_query(
            "MATCH (a:Author)-[:CREATED]->(w:World {id: $id}) RETURN a",
            parameters_={"id": world_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _author_from_node(record["a"])

    async def update_world_author(self,
                                  world_id: str,
                                  author_id: str,
                                  ) -> Author | None:
        result = await self._driver.execute_query(
            """
            MATCH (w:World {id: $world_id})
            MATCH (a:Author {id: $author_id})
            OPTIONAL MATCH (:Author)-[created:CREATED]->(w)
            DELETE created
            MERGE (a)-[:CREATED]->(w)
            RETURN a LIMIT 1
            """,
            parameters_={
                "world_id": world_id,
                "author_id": author_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _author_from_node(record["a"])

    async def list_worlds(self,
                          author_id: str | None = None,
                          ) -> list[World]:
        if author_id is not None:
            result = await self._driver.execute_query(
                """
                MATCH (:Author {id: $author_id})-[:CREATED]->(w:World)
                RETURN w
                ORDER BY w.name
                """,
                parameters_={"author_id": author_id},
            )
        else:
            result = await self._driver.execute_query(
                """
                MATCH (w:World)
                RETURN w
                ORDER BY w.name
                """
            )

        return [
            _world_from_node(record["w"])
            for record in result.records
        ]

    async def create_world(self,
                           world: World,
                           author_id: str,
                           previous_version: str | None = None,
                           ) -> World | None:
        result = await self._driver.execute_query(
            """
            MATCH (a:Author {id: $author_id})
            CREATE (w:World {
                id: $world_id,
                name: $world_name,
                description: $world_description,
                starting_time: $world_starting_time,
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
                "world_starting_time": world.starting_time,
                "world_url": world.url,
                "world_version": world.version,
                "world_language": world.language,
                "previous_version": previous_version,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _world_from_node(record["w"])

    async def get_world(self, world_id: str) -> World | None:
        result = await self._driver.execute_query(
            "MATCH (w:World {id: $id}) RETURN w LIMIT 1",
            parameters_={"id": world_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _world_from_node(record["w"])

    async def update_world(self,
                           world_id: str,
                           properties: dict,
                           ) -> World | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (w:World {id: $id})
            SET w += $properties
            RETURN w LIMIT 1
            """,
            parameters_={
                "id": world_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _world_from_node(record["w"])

    async def delete_world(self, world_id: str) -> World | None:
        result = await self._driver.execute_query(
            """
            MATCH (w:World {id: $id})
            WITH w, properties(w) AS properties
            DETACH DELETE w
            RETURN properties LIMIT 1
            """,
            parameters_={"id": world_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _world_from_node(record["properties"])
