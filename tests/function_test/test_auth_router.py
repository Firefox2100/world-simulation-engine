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
from world_simulation_engine.router import author_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class AuthorRouterTestClient:
    client: TestClient
    seeded_author: Author
    seeded_world: World


@pytest.fixture
def author_api(neo4j_container):
    seeded_author = Author(
        id=str(uuid4()),
        name="Seeded Author",
        url="https://example.com/authors/seeded",
    )
    seeded_world = World(
        id=str(uuid4()),
        name="Seeded World",
        description="A seeded world for author router tests",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/seeded",
        language=SupportedLanguage.ENGLISH,
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
        await database.world.create_author(seeded_author)
        await database.world.create_world(seeded_world, seeded_author.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(author_router)

    with TestClient(app) as client:
        yield AuthorRouterTestClient(
            client=client,
            seeded_author=seeded_author,
            seeded_world=seeded_world,
        )


def test_create_list_get_update_and_delete_author(author_api):
    client = author_api.client

    create_response = client.post(
        "/authors",
        json={
            "name": "Created Author",
            "url": "https://example.com/authors/created",
        },
    )

    assert create_response.status_code == 200
    created_author = create_response.json()
    assert created_author["id"]
    assert created_author["name"] == "Created Author"
    assert created_author["url"] == "https://example.com/authors/created"

    list_response = client.get("/authors")

    assert list_response.status_code == 200
    assert {
        author["id"]
        for author in list_response.json()
    } == {
        author_api.seeded_author.id,
        created_author["id"],
    }

    get_response = client.get(f"/authors/{created_author['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_author

    update_response = client.patch(
        f"/authors/{created_author['id']}",
        json={
            "name": "Updated Author",
            "url": "https://example.com/authors/updated",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": created_author["id"],
        "name": "Updated Author",
        "url": "https://example.com/authors/updated",
    }

    delete_response = client.delete(f"/authors/{created_author['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    missing_response = client.get(f"/authors/{created_author['id']}")

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == f"Author {created_author['id']} not found"


def test_author_endpoints_return_404_for_missing_resources(author_api):
    client = author_api.client
    missing_id = str(uuid4())

    get_response = client.get(f"/authors/{missing_id}")
    update_response = client.patch(f"/authors/{missing_id}", json={"name": "Missing Author"})
    delete_response = client.delete(f"/authors/{missing_id}")

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Author {missing_id} not found"
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == f"Author {missing_id} not found"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == f"Author {missing_id} not found"


def test_get_and_update_world_author(author_api):
    client = author_api.client

    get_response = client.get(f"/worlds/{author_api.seeded_world.id}/author")

    assert get_response.status_code == 200
    assert get_response.json() == author_api.seeded_author.model_dump(mode="json")

    create_response = client.post(
        "/authors",
        json={
            "name": "Replacement Author",
            "url": "https://example.com/authors/replacement",
        },
    )
    replacement_author = create_response.json()

    update_response = client.patch(
        f"/worlds/{author_api.seeded_world.id}/author",
        json={"id": replacement_author["id"]},
    )

    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json() == replacement_author
    assert client.get(f"/worlds/{author_api.seeded_world.id}/author").json() == replacement_author


def test_world_author_endpoints_return_404_for_missing_resources(author_api):
    client = author_api.client
    missing_world_id = str(uuid4())
    missing_author_id = str(uuid4())

    get_response = client.get(f"/worlds/{missing_world_id}/author")
    missing_world_update_response = client.patch(
        f"/worlds/{missing_world_id}/author",
        json={"id": author_api.seeded_author.id},
    )
    missing_author_update_response = client.patch(
        f"/worlds/{author_api.seeded_world.id}/author",
        json={"id": missing_author_id},
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Author for world {missing_world_id} not found"
    assert missing_world_update_response.status_code == 404
    assert missing_world_update_response.json()["detail"] == f"World {missing_world_id} not found"
    assert missing_author_update_response.status_code == 404
    assert missing_author_update_response.json()["detail"] == f"Author {missing_author_id} not found"
