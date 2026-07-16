from datetime import UTC, datetime
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


async def test_list_update_and_delete_author(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    first_author = make_author().model_copy(update={"name": "A Test Author"})
    second_author = make_author().model_copy(update={"name": "B Test Author"})

    await repo.create_author(first_author)
    await repo.create_author(second_author)

    stored_authors = await repo.list_authors()

    assert stored_authors == [first_author, second_author]

    updated_author = await repo.update_author(
        first_author.id,
        {
            "name": "Updated Author",
            "url": "https://example.com/authors/updated",
        },
    )

    assert updated_author == first_author.model_copy(
        update={
            "name": "Updated Author",
            "url": "https://example.com/authors/updated",
        }
    )
    assert await repo.get_author(first_author.id) == updated_author
    assert await repo.update_author(str(uuid4()), {"name": "Missing Author"}) is None

    assert await repo.delete_author(first_author.id) is True
    assert await repo.get_author(first_author.id) is None
    assert await repo.delete_author(first_author.id) is False
    assert await repo.list_authors() == [second_author]


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
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
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


async def test_create_world_returns_none_when_author_is_missing(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    world = make_world()

    assert await repo.create_world(world, str(uuid4())) is None
    assert await repo.get_world(world.id) is None


async def test_list_worlds(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    first_author = make_author().model_copy(update={"name": "First Author"})
    second_author = make_author().model_copy(update={"name": "Second Author"})
    first_world = make_world().model_copy(update={"name": "A Test World"})
    second_world = make_world().model_copy(update={"name": "B Test World"})
    third_world = make_world().model_copy(update={"name": "C Test World"})

    await repo.create_author(first_author)
    await repo.create_author(second_author)
    await repo.create_world(first_world, first_author.id)
    await repo.create_world(second_world, first_author.id)
    await repo.create_world(third_world, second_author.id)

    assert await repo.list_worlds() == [first_world, second_world, third_world]
    assert await repo.list_worlds(first_author.id) == [first_world, second_world]
    assert await repo.list_worlds(str(uuid4())) == []


async def test_update_and_delete_world(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    author = make_author()
    world = make_world()

    await repo.create_author(author)
    await repo.create_world(world, author.id)

    updated_world = await repo.update_world(
        world.id,
        {
            "name": "Updated World",
            "description": "An updated test world",
            "starting_time": datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            "version": 2,
            "url": "https://example.com/worlds/updated",
            "language": SupportedLanguage.CHINESE,
        },
    )

    assert updated_world == world.model_copy(
        update={
            "name": "Updated World",
            "description": "An updated test world",
            "starting_time": datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
            "version": 2,
            "url": "https://example.com/worlds/updated",
            "language": SupportedLanguage.CHINESE,
        }
    )
    assert await repo.get_world(world.id) == updated_world
    assert await repo.update_world(str(uuid4()), {"name": "Missing World"}) is None

    assert await repo.delete_world(world.id) == updated_world
    assert await repo.get_world(world.id) is None
    assert await repo.delete_world(world.id) is None


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


async def test_update_world_author_reassigns_author(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    first_author = make_author().model_copy(update={"name": "First Author"})
    second_author = make_author().model_copy(update={"name": "Second Author"})
    world = make_world()

    await repo.create_author(first_author)
    await repo.create_author(second_author)
    await repo.create_world(world, first_author.id)

    updated_author = await repo.update_world_author(world.id, second_author.id)

    assert updated_author == second_author
    assert await repo.get_author_by_world(world.id) == second_author

    result = await clean_neo4j.execute_query(
        """
        MATCH (author:Author)-[:CREATED]->(world:World {id: $world_id})
        RETURN author.id AS author_id
        """,
        parameters_={"world_id": world.id},
    )

    assert [
        record["author_id"]
        for record in result.records
    ] == [second_author.id]


async def test_update_world_author_returns_none_for_missing_world_or_author(clean_neo4j):
    repo = WorldStore(clean_neo4j)
    author = make_author()
    world = make_world()

    await repo.create_author(author)
    await repo.create_world(world, author.id)

    assert await repo.update_world_author(str(uuid4()), author.id) is None
    assert await repo.update_world_author(world.id, str(uuid4())) is None
