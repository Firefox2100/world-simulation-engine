from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import Author, World
from world_simulation_engine.router import world_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class WorldRouterTestClient:
    client: TestClient
    author: Author
    other_author: Author
    seeded_world: World
    other_world: World


@pytest.fixture
def world_api(neo4j_container):
    author = Author(
        id=str(uuid4()),
        name="World API Author",
        url="https://example.com/authors/world-api",
    )
    other_author = Author(
        id=str(uuid4()),
        name="Other World API Author",
        url="https://example.com/authors/other-world-api",
    )
    seeded_world = World(
        id=str(uuid4()),
        name="Seeded World",
        description="A seeded world for world router tests",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/seeded",
        language=SupportedLanguage.ENGLISH,
    )
    other_world = World(
        id=str(uuid4()),
        name="Other Seeded World",
        description="Another seeded world for world router tests",
        starting_time=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/other-seeded",
        language=SupportedLanguage.CHINESE,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        driver = AsyncGraphDatabase.driver(
            neo4j_container.get_connection_url(),
            auth=("neo4j", "testpassword"),
        )
        await driver.verify_connectivity()
        await driver.execute_query("MATCH (n) DETACH DELETE n")

        database = DatabaseService(driver)
        await database.world.create_author(author)
        await database.world.create_author(other_author)
        await database.world.create_world(seeded_world, author.id)
        await database.world.create_world(other_world, other_author.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(world_router)

    with TestClient(app) as client:
        yield WorldRouterTestClient(
            client=client,
            author=author,
            other_author=other_author,
            seeded_world=seeded_world,
            other_world=other_world,
        )


def test_create_list_get_update_and_delete_world(world_api):
    client = world_api.client

    create_response = client.post(
        "/worlds",
        json={
            "name": "Created World",
            "description": "Created through the world API",
            "starting_time": "2026-03-01T12:00:00Z",
            "author_id": world_api.author.id,
            "version": 2,
            "url": "https://example.com/worlds/created",
            "language": "en",
        },
    )

    assert create_response.status_code == 200
    created_world = create_response.json()
    assert created_world["id"]
    assert created_world["name"] == "Created World"
    assert created_world["description"] == "Created through the world API"
    assert created_world["starting_time"] == "2026-03-01T12:00:00Z"
    assert created_world["version"] == 2
    assert created_world["url"] == "https://example.com/worlds/created"
    assert created_world["language"] == "en"

    list_response = client.get("/worlds")

    assert list_response.status_code == 200
    assert {
        world["id"]
        for world in list_response.json()
    } == {
        world_api.seeded_world.id,
        world_api.other_world.id,
        created_world["id"],
    }

    filtered_list_response = client.get("/worlds", params={"author_id": world_api.author.id})

    assert filtered_list_response.status_code == 200
    assert {
        world["id"]
        for world in filtered_list_response.json()
    } == {
        world_api.seeded_world.id,
        created_world["id"],
    }

    get_response = client.get(f"/worlds/{created_world['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_world

    update_response = client.patch(
        f"/worlds/{created_world['id']}",
        json={
            "name": "Updated World",
            "description": "Updated through the world API",
            "starting_time": "2026-04-01T12:00:00Z",
            "version": 3,
            "url": "https://example.com/worlds/updated",
            "language": "zh",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": created_world["id"],
        "name": "Updated World",
        "description": "Updated through the world API",
        "starting_time": "2026-04-01T12:00:00Z",
        "version": 3,
        "url": "https://example.com/worlds/updated",
        "language": "zh",
    }

    delete_response = client.delete(f"/worlds/{created_world['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    missing_response = client.get(f"/worlds/{created_world['id']}")

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == f"World {created_world['id']} not found"


def test_world_endpoints_return_404_for_missing_resources(world_api):
    client = world_api.client
    missing_world_id = str(uuid4())
    missing_author_id = str(uuid4())

    create_response = client.post(
        "/worlds",
        json={
            "name": "Missing Author World",
            "starting_time": "2026-05-01T12:00:00Z",
            "author_id": missing_author_id,
            "language": "en",
        },
    )
    get_response = client.get(f"/worlds/{missing_world_id}")
    update_response = client.patch(f"/worlds/{missing_world_id}", json={"name": "Missing World"})
    delete_response = client.delete(f"/worlds/{missing_world_id}")

    assert create_response.status_code == 404
    assert create_response.json()["detail"] == f"Author {missing_author_id} not found"
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"World {missing_world_id} not found"
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == f"World {missing_world_id} not found"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == f"World {missing_world_id} not found"
