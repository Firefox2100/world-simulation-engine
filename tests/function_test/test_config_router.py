from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, SupportedLanguage
from world_simulation_engine.model import Author, Simulation, World
from world_simulation_engine.router import config_router
from world_simulation_engine.service import DatabaseService


@dataclass(frozen=True)
class ConfigRouterTestClient:
    client: TestClient
    world: World
    simulation: Simulation


@pytest.fixture
def config_api(neo4j_container):
    author = Author(id=str(uuid4()), name="Config API Author")
    world = World(
        id=str(uuid4()),
        name="Config World",
        description="A world used to configure simulations",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )
    simulation = Simulation(
        id=str(uuid4()),
        name="Config Simulation",
        description="A simulation used to test configs",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
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
        await database.world.create_world(world, author.id)
        await database.simulation.create_simulation(simulation, world.id)
        app.state.database = database

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(config_router)

    with TestClient(app) as client:
        yield ConfigRouterTestClient(
            client=client,
            world=world,
            simulation=simulation,
        )


def connection_payload(name: str = "OpenAI") -> dict:
    return {
        "type": ConnectionType.OPENAI,
        "name": name,
        "api_key": "test-key",
    }


def ollama_chat_payload(name: str = "Local Chat") -> dict:
    return {
        "name": name,
        "model": "llama3.1",
        "temperature": 0.5,
        "context_window": 4096,
        "num_predict": 512,
    }


def openai_chat_payload(name: str = "OpenAI Chat") -> dict:
    return {
        "name": name,
        "model": "gpt-test",
        "temperature": 0.2,
        "context_window": 8192,
    }


def ollama_embed_payload() -> dict:
    return {
        "model": "nomic-embed-text",
        "dimension": 768,
        "context_window": 2048,
    }


def openai_embed_payload() -> dict:
    return {
        "model": "text-embedding-test",
        "dimension": 1536,
    }


def test_connection_config_crud(config_api):
    client = config_api.client

    create_response = client.post("/config/connections", json=connection_payload())

    assert create_response.status_code == 200
    connection = create_response.json()
    assert connection["id"]
    assert connection["name"] == "OpenAI"
    assert client.get("/config/connections").json() == [connection]
    assert client.get(f"/config/connections/{connection['id']}").json() == connection

    update_response = client.patch(
        f"/config/connections/{connection['id']}",
        json={
            "name": "Updated OpenAI",
            "base_url": "https://api.example.com",
        },
    )

    assert update_response.status_code == 200
    updated_connection = update_response.json()
    assert updated_connection == {
        **connection,
        "name": "Updated OpenAI",
        "base_url": "https://api.example.com",
    }

    delete_response = client.delete(f"/config/connections/{connection['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/config/connections/{connection['id']}").status_code == 404


def test_llm_config_crud_and_connection_link(config_api):
    client = config_api.client
    connection = client.post("/config/connections", json=connection_payload("Local Ollama")).json()
    ollama_create_response = client.post("/config/llm/ollama", json=ollama_chat_payload())
    openai_create_response = client.post("/config/llm/openai", json=openai_chat_payload())

    assert ollama_create_response.status_code == 200
    assert openai_create_response.status_code == 200
    ollama_chat = ollama_create_response.json()
    openai_chat = openai_create_response.json()
    assert client.get("/config/llm").json() == [ollama_chat, openai_chat]
    assert client.get(f"/config/llm/{ollama_chat['id']}").json() == ollama_chat

    link_response = client.put(
        f"/config/llm/{ollama_chat['id']}/connection",
        json={"connection_id": connection["id"]},
    )

    assert link_response.status_code == 200
    assert link_response.json() == connection
    assert client.get(f"/config/llm/{ollama_chat['id']}/connection").json() == connection
    assert client.delete(f"/config/llm/{ollama_chat['id']}/connection").status_code == 204
    assert client.get(f"/config/llm/{ollama_chat['id']}/connection").status_code == 404
    assert client.put(
        f"/config/llm/{ollama_chat['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200

    update_response = client.patch(
        f"/config/llm/{ollama_chat['id']}",
        json={
            "temperature": 0.7,
            "repeat_penalty": 1.1,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **ollama_chat,
        "temperature": 0.7,
        "repeat_penalty": 1.1,
    }

    delete_response = client.delete(f"/config/llm/{ollama_chat['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/config/llm/{ollama_chat['id']}").status_code == 404


def test_embedding_config_crud_and_connection_link(config_api):
    client = config_api.client
    connection = client.post("/config/connections", json=connection_payload()).json()
    ollama_create_response = client.post("/config/embeddings/ollama", json=ollama_embed_payload())
    openai_create_response = client.post("/config/embeddings/openai", json=openai_embed_payload())

    assert ollama_create_response.status_code == 200
    assert openai_create_response.status_code == 200
    ollama_embed = ollama_create_response.json()
    openai_embed = openai_create_response.json()
    assert client.get("/config/embeddings").json() == [ollama_embed, openai_embed]
    assert client.get(f"/config/embeddings/{ollama_embed['id']}").json() == ollama_embed

    link_response = client.put(
        f"/config/embeddings/{ollama_embed['id']}/connection",
        json={"connection_id": connection["id"]},
    )

    assert link_response.status_code == 200
    assert link_response.json() == connection
    assert client.get(f"/config/embeddings/{ollama_embed['id']}/connection").json() == connection
    assert client.delete(f"/config/embeddings/{ollama_embed['id']}/connection").status_code == 204
    assert client.get(f"/config/embeddings/{ollama_embed['id']}/connection").status_code == 404
    assert client.put(
        f"/config/embeddings/{ollama_embed['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200

    update_response = client.patch(
        f"/config/embeddings/{ollama_embed['id']}",
        json={"dimension": 1024},
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **ollama_embed,
        "dimension": 1024,
    }

    delete_response = client.delete(f"/config/embeddings/{ollama_embed['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/config/embeddings/{ollama_embed['id']}").status_code == 404


def test_simulation_model_config_links(config_api):
    client = config_api.client
    chat = client.post("/config/llm/openai", json=openai_chat_payload()).json()
    replacement_chat = client.post("/config/llm/openai", json=openai_chat_payload("Replacement Chat")).json()
    embed = client.post("/config/embeddings/openai", json=openai_embed_payload()).json()

    chat_link_response = client.put(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        json={
            "component": ComponentType.NARRATOR,
            "config_id": chat["id"],
        },
    )
    replacement_chat_link_response = client.put(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        json={
            "component": ComponentType.NARRATOR,
            "config_id": replacement_chat["id"],
        },
    )
    embed_link_response = client.put(
        f"/simulations/{config_api.simulation.id}/embedding-connection",
        json={
            "component": ComponentType.CHARACTER_SIMULATOR,
            "config_id": embed["id"],
        },
    )

    assert chat_link_response.status_code == 200
    assert chat_link_response.json() == chat
    assert replacement_chat_link_response.status_code == 200
    assert replacement_chat_link_response.json() == replacement_chat
    assert client.get(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        params={"component": ComponentType.NARRATOR},
    ).json() == replacement_chat
    assert embed_link_response.status_code == 200
    assert embed_link_response.json() == embed
    assert client.get(
        f"/simulations/{config_api.simulation.id}/embedding-connection",
        params={"component": ComponentType.CHARACTER_SIMULATOR},
    ).json() == embed
    assert client.delete(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        params={"component": ComponentType.NARRATOR},
    ).status_code == 204
    assert client.get(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        params={"component": ComponentType.NARRATOR},
    ).status_code == 404
    assert client.delete(
        f"/simulations/{config_api.simulation.id}/embedding-connection",
        params={"component": ComponentType.CHARACTER_SIMULATOR},
    ).status_code == 204
    assert client.get(
        f"/simulations/{config_api.simulation.id}/embedding-connection",
        params={"component": ComponentType.CHARACTER_SIMULATOR},
    ).status_code == 404


def test_component_model_config_batch_links(config_api):
    client = config_api.client
    narrator_chat = client.post("/config/llm/openai", json=openai_chat_payload("Narrator Chat")).json()
    character_chat = client.post("/config/llm/openai", json=openai_chat_payload("Character Chat")).json()
    embed = client.post("/config/embeddings/openai", json=openai_embed_payload()).json()

    world_chat_response = client.put(
        f"/worlds/{config_api.world.id}/llm-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.NARRATOR,
                    "config_id": narrator_chat["id"],
                },
                {
                    "component": ComponentType.CHARACTER_SIMULATOR,
                    "config_id": character_chat["id"],
                },
            ],
        },
    )
    world_embed_response = client.put(
        f"/worlds/{config_api.world.id}/embedding-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.CHARACTER_SIMULATOR,
                    "config_id": embed["id"],
                },
            ],
        },
    )

    assert world_chat_response.status_code == 200
    assert world_chat_response.json() == [
        {
            "component": ComponentType.CHARACTER_SIMULATOR,
            "config": character_chat,
        },
        {
            "component": ComponentType.NARRATOR,
            "config": narrator_chat,
        },
    ]
    assert client.get(f"/worlds/{config_api.world.id}/llm-connections").json() == world_chat_response.json()
    assert world_embed_response.status_code == 200
    assert world_embed_response.json() == [
        {
            "component": ComponentType.CHARACTER_SIMULATOR,
            "config": embed,
        },
    ]
    assert client.get(f"/worlds/{config_api.world.id}/embedding-connections").json() == world_embed_response.json()

    remove_response = client.put(
        f"/worlds/{config_api.world.id}/llm-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.NARRATOR,
                    "config_id": None,
                },
            ],
        },
    )

    assert remove_response.status_code == 200
    assert remove_response.json() == [
        {
            "component": ComponentType.CHARACTER_SIMULATOR,
            "config": character_chat,
        },
    ]
    assert client.put(
        f"/simulations/{config_api.simulation.id}/llm-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.NARRATOR,
                    "config_id": narrator_chat["id"],
                },
            ],
        },
    ).status_code == 200
    assert client.get(f"/simulations/{config_api.simulation.id}/llm-connections").json() == [
        {
            "component": ComponentType.NARRATOR,
            "config": narrator_chat,
        },
    ]


def test_config_endpoints_return_404_for_missing_resources(config_api):
    client = config_api.client
    missing_id = str(uuid4())
    connection = client.post("/config/connections", json=connection_payload()).json()
    chat = client.post("/config/llm/openai", json=openai_chat_payload()).json()
    embed = client.post("/config/embeddings/openai", json=openai_embed_payload()).json()

    assert client.get(f"/config/connections/{missing_id}").status_code == 404
    assert client.patch(f"/config/connections/{missing_id}", json={"name": "Missing"}).status_code == 404
    assert client.delete(f"/config/connections/{missing_id}").status_code == 404
    assert client.get(f"/config/llm/{missing_id}").status_code == 404
    assert client.patch(f"/config/llm/{missing_id}", json={"name": "Missing"}).status_code == 404
    assert client.delete(f"/config/llm/{missing_id}").status_code == 404
    assert client.get(f"/config/embeddings/{missing_id}").status_code == 404
    assert client.patch(f"/config/embeddings/{missing_id}", json={"dimension": 1}).status_code == 404
    assert client.delete(f"/config/embeddings/{missing_id}").status_code == 404
    assert client.put(f"/config/llm/{missing_id}/connection", json={"connection_id": connection["id"]}).status_code == \
        404
    assert client.put(f"/config/llm/{chat['id']}/connection", json={"connection_id": missing_id}).status_code == 404
    assert client.get(f"/config/llm/{missing_id}/connection").status_code == 404
    assert client.delete(f"/config/llm/{missing_id}/connection").status_code == 404
    assert client.put(
        f"/config/embeddings/{missing_id}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 404
    assert client.put(
        f"/config/embeddings/{embed['id']}/connection",
        json={"connection_id": missing_id},
    ).status_code == 404
    assert client.get(f"/config/embeddings/{missing_id}/connection").status_code == 404
    assert client.delete(f"/config/embeddings/{missing_id}/connection").status_code == 404
    assert client.put(
        f"/simulations/{missing_id}/llm-connection",
        json={
            "component": ComponentType.NARRATOR,
            "config_id": chat["id"],
        },
    ).status_code == 404
    assert client.put(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        json={
            "component": ComponentType.NARRATOR,
            "config_id": missing_id,
        },
    ).status_code == 404
    assert client.get(
        f"/simulations/{missing_id}/llm-connection",
        params={"component": ComponentType.NARRATOR},
    ).status_code == 404
    assert client.delete(
        f"/simulations/{missing_id}/llm-connection",
        params={"component": ComponentType.NARRATOR},
    ).status_code == 404
    assert client.put(
        f"/simulations/{missing_id}/embedding-connection",
        json={
            "component": ComponentType.CHARACTER_SIMULATOR,
            "config_id": embed["id"],
        },
    ).status_code == 404
    assert client.put(
        f"/simulations/{config_api.simulation.id}/embedding-connection",
        json={
            "component": ComponentType.CHARACTER_SIMULATOR,
            "config_id": missing_id,
        },
    ).status_code == 404
    assert client.get(
        f"/simulations/{missing_id}/embedding-connection",
        params={"component": ComponentType.CHARACTER_SIMULATOR},
    ).status_code == 404
    assert client.delete(
        f"/simulations/{missing_id}/embedding-connection",
        params={"component": ComponentType.CHARACTER_SIMULATOR},
    ).status_code == 404
    assert client.get(f"/worlds/{missing_id}/llm-connections").status_code == 404
    assert client.put(
        f"/worlds/{config_api.world.id}/llm-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.NARRATOR,
                    "config_id": missing_id,
                },
            ],
        },
    ).status_code == 404
    assert client.get(f"/simulations/{missing_id}/embedding-connections").status_code == 404
    assert client.put(
        f"/simulations/{config_api.simulation.id}/embedding-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.CHARACTER_SIMULATOR,
                    "config_id": missing_id,
                },
            ],
        },
    ).status_code == 404
