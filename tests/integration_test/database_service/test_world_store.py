from uuid import uuid4

from world_simulation_engine.model import Author, World
from world_simulation_engine.service.database.world_store import WorldStore


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
