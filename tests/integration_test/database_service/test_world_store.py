from uuid import uuid4

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, World
from world_simulation_engine.service.database.world_store import WorldStore
from tests.integration_test.database_service.helpers import make_author, make_world


async def test_missing_author_and_world_return_none(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    missing_id = str(uuid4())

    assert await repo.get_author(missing_id) is None
    assert await repo.get_author_by_world(missing_id) is None
    assert await repo.get_world(missing_id) is None


async def test_create_author(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    author_id = str(uuid4())
    author = Author(
        id=author_id,
        name="Test Author",
        url=None,
    )

    await repo.create_author(author=author)

    stored_author = await repo.get_author(author_id)

    assert stored_author == author


async def test_create_world(clean_neo4j):
    repo = WorldStore(clean_neo4j)

    author_id = str(uuid4())
    author = Author(
        id=author_id,
        name="Test Author",
        url=None,
    )

    world_id = str(uuid4())
    world = World(
        id=world_id,
        name="Test World",
        description="Test World",
        version=1,
        url="https://example.com/test-world",
        language=SupportedLanguage.ENGLISH,
    )

    await repo.create_author(author=author)

    await repo.create_world(
        world=world,
        author_id=author_id
    )

    stored_world = await repo.get_world(world_id)

    assert stored_world == world


async def test_create_world_links_author_and_previous_version(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    author = make_author()
    first_world = make_world()
    next_world = first_world.model_copy(update={"id": str(uuid4()), "version": 2})

    await repo.create_author(author)
    await repo.create_world(first_world, author.id)
    await repo.create_world(next_world, author.id, previous_version=first_world.id)

    assert await repo.get_author_by_world(first_world.id) == author
    assert await repo.get_world(next_world.id) == next_world

    result = await clean_neo4j.execute_query(
        """
        MATCH (next:World {id: $next_id})-[:NEW_VERSION_OF]->(previous:World {id: $previous_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"next_id": next_world.id, "previous_id": first_world.id},
    )
    assert result.records[0]["link_count"] == 1
