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
        "base_url": "http://localhost:11434",
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


def alltalk_connection_payload(name: str = "Local AllTalk") -> dict:
    return {
        "type": ConnectionType.ALLTALK,
        "name": name,
        "base_url": "http://localhost:7851",
        "api_key": "test-key",
    }


def alltalk_xtts_payload() -> dict:
    return {
        "language": "en",
        "temperature": 0.75,
        "repetition_penalty": 10,
    }


def alltalk_piper_payload() -> dict:
    return {
        "speed": 1.1,
    }


def comfyui_connection_payload(name: str = "Local ComfyUI") -> dict:
    return {
        "type": ConnectionType.COMFYUI,
        "name": name,
        "base_url": "http://localhost:8188",
        "api_key": "test-key",
    }


def comfyui_image_payload() -> dict:
    return {
        "model": "sd_xl_base.safetensors",
        "image_width": 1024,
        "image_height": 1024,
        "steps": 20,
    }


def whisper_cpp_connection_payload(name: str = "Local whisper.cpp") -> dict:
    return {
        "type": ConnectionType.WHISPERCPP,
        "name": name,
        "base_url": "http://localhost:8080",
        "api_key": "test-key",
    }


def whisper_cpp_stt_payload() -> dict:
    return {
        "language": "en",
        "temperature": 0.0,
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
    assert client.get(f"/config/llm/{ollama_chat['id']}").json() == {
        **ollama_chat,
        "connection": connection,
    }
    assert client.get("/config/llm").json() == [
        {
            **ollama_chat,
            "connection": connection,
        },
        openai_chat,
    ]
    assert client.delete(f"/config/llm/{ollama_chat['id']}/connection").status_code == 204
    assert client.get(f"/config/llm/{ollama_chat['id']}/connection").status_code == 404
    assert client.put(
        f"/config/llm/{ollama_chat['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    linked_ollama_chat = {
        **ollama_chat,
        "connection": connection,
    }

    update_response = client.patch(
        f"/config/llm/{ollama_chat['id']}",
        json={
            "temperature": 0.7,
            "repeat_penalty": 1.1,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **linked_ollama_chat,
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
    assert client.get(f"/config/embeddings/{ollama_embed['id']}").json() == {
        **ollama_embed,
        "connection": connection,
    }
    assert client.get("/config/embeddings").json() == [
        {
            **ollama_embed,
            "connection": connection,
        },
        openai_embed,
    ]
    assert client.delete(f"/config/embeddings/{ollama_embed['id']}/connection").status_code == 204
    assert client.get(f"/config/embeddings/{ollama_embed['id']}/connection").status_code == 404
    assert client.put(
        f"/config/embeddings/{ollama_embed['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    linked_ollama_embed = {
        **ollama_embed,
        "connection": connection,
    }

    update_response = client.patch(
        f"/config/embeddings/{ollama_embed['id']}",
        json={"dimension": 1024},
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **linked_ollama_embed,
        "dimension": 1024,
    }

    delete_response = client.delete(f"/config/embeddings/{ollama_embed['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/config/embeddings/{ollama_embed['id']}").status_code == 404


def test_tts_config_crud_and_connection_link(config_api):
    client = config_api.client
    connection = client.post("/config/connections", json=alltalk_connection_payload()).json()
    xtts_create_response = client.post("/config/tts/alltalk/xtts", json=alltalk_xtts_payload())
    piper_create_response = client.post("/config/tts/alltalk/piper", json=alltalk_piper_payload())

    assert xtts_create_response.status_code == 200
    assert piper_create_response.status_code == 200
    xtts_config = xtts_create_response.json()
    piper_config = piper_create_response.json()
    assert xtts_config["provider"] == "alltalk"
    assert xtts_config["engine"] == "xtts"
    assert piper_config["engine"] == "piper"
    assert client.get(f"/config/tts/{xtts_config['id']}").json() == xtts_config
    listed = client.get("/config/tts").json()
    assert {c["id"] for c in listed} == {xtts_config["id"], piper_config["id"]}

    link_response = client.put(
        f"/config/tts/{xtts_config['id']}/connection",
        json={"connection_id": connection["id"]},
    )

    assert link_response.status_code == 200
    assert link_response.json() == connection
    assert client.get(f"/config/tts/{xtts_config['id']}/connection").json() == connection
    assert client.get(f"/config/tts/{xtts_config['id']}").json() == {
        **xtts_config,
        "connection": connection,
    }
    assert client.delete(f"/config/tts/{xtts_config['id']}/connection").status_code == 204
    assert client.get(f"/config/tts/{xtts_config['id']}/connection").status_code == 404
    assert client.put(
        f"/config/tts/{xtts_config['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    linked_xtts_config = {
        **xtts_config,
        "connection": connection,
    }

    update_response = client.patch(
        f"/config/tts/{xtts_config['id']}",
        json={
            "temperature": 0.5,
            "speed": 1.2,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **linked_xtts_config,
        "temperature": 0.5,
        "speed": 1.2,
    }

    delete_response = client.delete(f"/config/tts/{xtts_config['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/config/tts/{xtts_config['id']}").status_code == 404


def test_simulation_and_world_tts_config_links(config_api):
    client = config_api.client
    tts_config = client.post("/config/tts/alltalk/xtts", json=alltalk_xtts_payload()).json()
    replacement_tts_config = client.post("/config/tts/alltalk/piper", json=alltalk_piper_payload()).json()

    link_response = client.put(
        f"/simulations/{config_api.simulation.id}/tts-connection",
        json={
            "component": ComponentType.NARRATOR_TTS,
            "config_id": tts_config["id"],
        },
    )
    replacement_link_response = client.put(
        f"/simulations/{config_api.simulation.id}/tts-connection",
        json={
            "component": ComponentType.NARRATOR_TTS,
            "config_id": replacement_tts_config["id"],
        },
    )

    assert link_response.status_code == 200
    assert link_response.json() == tts_config
    assert replacement_link_response.status_code == 200
    assert replacement_link_response.json() == replacement_tts_config
    assert client.get(
        f"/simulations/{config_api.simulation.id}/tts-connection",
        params={"component": ComponentType.NARRATOR_TTS},
    ).json() == replacement_tts_config
    assert client.get(f"/simulations/{config_api.simulation.id}/tts-connections").json() == [
        {"component": ComponentType.NARRATOR_TTS, "config": replacement_tts_config},
    ]
    assert client.delete(
        f"/simulations/{config_api.simulation.id}/tts-connection",
        params={"component": ComponentType.NARRATOR_TTS},
    ).status_code == 204
    assert client.get(
        f"/simulations/{config_api.simulation.id}/tts-connection",
        params={"component": ComponentType.NARRATOR_TTS},
    ).status_code == 404

    world_link_response = client.put(
        f"/worlds/{config_api.world.id}/tts-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.NARRATOR_TTS,
                    "config_id": tts_config["id"],
                },
            ],
        },
    )

    assert world_link_response.status_code == 200
    assert world_link_response.json() == [
        {"component": ComponentType.NARRATOR_TTS, "config": tts_config},
    ]
    assert client.get(f"/worlds/{config_api.world.id}/tts-connections").json() == world_link_response.json()
    assert client.get(
        f"/worlds/{config_api.world.id}/tts-connection",
        params={"component": ComponentType.NARRATOR_TTS},
    ).json() == tts_config


def test_image_config_crud_and_connection_link(config_api):
    client = config_api.client
    connection = client.post("/config/connections", json=comfyui_connection_payload()).json()
    create_response = client.post("/config/images/comfyui", json=comfyui_image_payload())

    assert create_response.status_code == 200
    image_config = create_response.json()
    assert image_config["provider"] == "comfyui"
    assert client.get(f"/config/images/{image_config['id']}").json() == image_config
    assert client.get("/config/images").json() == [image_config]

    link_response = client.put(
        f"/config/images/{image_config['id']}/connection",
        json={"connection_id": connection["id"]},
    )

    assert link_response.status_code == 200
    assert link_response.json() == connection
    assert client.get(f"/config/images/{image_config['id']}/connection").json() == connection
    assert client.get(f"/config/images/{image_config['id']}").json() == {
        **image_config,
        "connection": connection,
    }
    assert client.delete(f"/config/images/{image_config['id']}/connection").status_code == 204
    assert client.get(f"/config/images/{image_config['id']}/connection").status_code == 404
    assert client.put(
        f"/config/images/{image_config['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    linked_image_config = {
        **image_config,
        "connection": connection,
    }

    update_response = client.patch(
        f"/config/images/{image_config['id']}",
        json={
            "steps": 25,
            "cfg": 7,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **linked_image_config,
        "steps": 25,
        "cfg": 7,
    }

    delete_response = client.delete(f"/config/images/{image_config['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/config/images/{image_config['id']}").status_code == 404


def test_stt_config_crud_and_connection_link(config_api):
    client = config_api.client
    connection = client.post("/config/connections", json=whisper_cpp_connection_payload()).json()
    create_response = client.post("/config/stt/whispercpp", json=whisper_cpp_stt_payload())

    assert create_response.status_code == 200
    stt_config = create_response.json()
    assert stt_config["provider"] == "whispercpp"
    assert client.get(f"/config/stt/{stt_config['id']}").json() == stt_config
    assert client.get("/config/stt").json() == [stt_config]

    link_response = client.put(
        f"/config/stt/{stt_config['id']}/connection",
        json={"connection_id": connection["id"]},
    )

    assert link_response.status_code == 200
    assert link_response.json() == connection
    assert client.get(f"/config/stt/{stt_config['id']}/connection").json() == connection
    assert client.get(f"/config/stt/{stt_config['id']}").json() == {
        **stt_config,
        "connection": connection,
    }
    assert client.delete(f"/config/stt/{stt_config['id']}/connection").status_code == 204
    assert client.get(f"/config/stt/{stt_config['id']}/connection").status_code == 404
    assert client.put(
        f"/config/stt/{stt_config['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    linked_stt_config = {
        **stt_config,
        "connection": connection,
    }

    update_response = client.patch(
        f"/config/stt/{stt_config['id']}",
        json={
            "temperature": 0.5,
            "initial_prompt": "World Simulation Engine",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        **linked_stt_config,
        "temperature": 0.5,
        "initial_prompt": "World Simulation Engine",
    }

    delete_response = client.delete(f"/config/stt/{stt_config['id']}")

    assert delete_response.status_code == 204
    assert client.get(f"/config/stt/{stt_config['id']}").status_code == 404


def test_simulation_and_world_image_config_links(config_api):
    client = config_api.client
    image_config = client.post("/config/images/comfyui", json=comfyui_image_payload()).json()
    replacement_image_config = client.post(
        "/config/images/comfyui", json={**comfyui_image_payload(), "steps": 30},
    ).json()

    link_response = client.put(
        f"/simulations/{config_api.simulation.id}/image-connection",
        json={
            "component": ComponentType.SCENE_IMAGE_GENERATOR,
            "config_id": image_config["id"],
        },
    )
    replacement_link_response = client.put(
        f"/simulations/{config_api.simulation.id}/image-connection",
        json={
            "component": ComponentType.SCENE_IMAGE_GENERATOR,
            "config_id": replacement_image_config["id"],
        },
    )

    assert link_response.status_code == 200
    assert link_response.json() == image_config
    assert replacement_link_response.status_code == 200
    assert replacement_link_response.json() == replacement_image_config
    assert client.get(
        f"/simulations/{config_api.simulation.id}/image-connection",
        params={"component": ComponentType.SCENE_IMAGE_GENERATOR},
    ).json() == replacement_image_config
    assert client.get(f"/simulations/{config_api.simulation.id}/image-connections").json() == [
        {"component": ComponentType.SCENE_IMAGE_GENERATOR, "config": replacement_image_config},
    ]
    assert client.delete(
        f"/simulations/{config_api.simulation.id}/image-connection",
        params={"component": ComponentType.SCENE_IMAGE_GENERATOR},
    ).status_code == 204
    assert client.get(
        f"/simulations/{config_api.simulation.id}/image-connection",
        params={"component": ComponentType.SCENE_IMAGE_GENERATOR},
    ).status_code == 404

    world_link_response = client.put(
        f"/worlds/{config_api.world.id}/image-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.SCENE_IMAGE_GENERATOR,
                    "config_id": image_config["id"],
                },
            ],
        },
    )

    assert world_link_response.status_code == 200
    assert world_link_response.json() == [
        {"component": ComponentType.SCENE_IMAGE_GENERATOR, "config": image_config},
    ]
    assert client.get(f"/worlds/{config_api.world.id}/image-connections").json() == world_link_response.json()
    assert client.get(
        f"/worlds/{config_api.world.id}/image-connection",
        params={"component": ComponentType.SCENE_IMAGE_GENERATOR},
    ).json() == image_config


def test_simulation_model_config_links(config_api):
    client = config_api.client
    connection = client.post("/config/connections", json=connection_payload()).json()
    chat = client.post("/config/llm/openai", json=openai_chat_payload()).json()
    replacement_chat = client.post("/config/llm/openai", json=openai_chat_payload("Replacement Chat")).json()
    embed = client.post("/config/embeddings/openai", json=openai_embed_payload()).json()
    assert client.put(
        f"/config/llm/{replacement_chat['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    linked_replacement_chat = {
        **replacement_chat,
        "connection": connection,
    }

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
    assert replacement_chat_link_response.json() == linked_replacement_chat
    assert client.get(
        f"/simulations/{config_api.simulation.id}/llm-connection",
        params={"component": ComponentType.NARRATOR},
    ).json() == linked_replacement_chat
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
    connection = client.post("/config/connections", json=connection_payload()).json()
    narrator_chat = client.post("/config/llm/openai", json=openai_chat_payload("Narrator Chat")).json()
    character_chat = client.post("/config/llm/openai", json=openai_chat_payload("Character Chat")).json()
    embed = client.post("/config/embeddings/openai", json=openai_embed_payload()).json()
    assert client.put(
        f"/config/llm/{narrator_chat['id']}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 200
    narrator_chat_with_connection = {
        **narrator_chat,
        "connection": connection,
    }

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
            "config": narrator_chat_with_connection,
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
            "config": narrator_chat_with_connection,
        },
    ]


def test_global_llm_connections_link_and_unlink_without_a_source(config_api):
    client = config_api.client
    classifier_chat = client.post("/config/llm/openai", json=openai_chat_payload("Classifier Chat")).json()
    character_chat = client.post("/config/llm/openai", json=openai_chat_payload("Character Extractor Chat")).json()
    components = [ComponentType.ST_LOREBOOK_CLASSIFIER, ComponentType.ST_CHARACTER_EXTRACTOR]

    assert client.get(
        "/config/llm/global-connections",
        params={"components": components},
    ).json() == []

    link_response = client.put(
        "/config/llm/global-connections",
        json={
            "assignments": [
                {"component": ComponentType.ST_LOREBOOK_CLASSIFIER, "config_id": classifier_chat["id"]},
                {"component": ComponentType.ST_CHARACTER_EXTRACTOR, "config_id": character_chat["id"]},
            ],
        },
    )

    assert link_response.status_code == 200
    assert link_response.json() == [
        {"component": ComponentType.ST_LOREBOOK_CLASSIFIER, "config": classifier_chat},
        {"component": ComponentType.ST_CHARACTER_EXTRACTOR, "config": character_chat},
    ]
    assert client.get(
        "/config/llm/global-connections",
        params={"components": components},
    ).json() == link_response.json()

    reassign_response = client.put(
        "/config/llm/global-connections",
        json={
            "assignments": [
                {"component": ComponentType.ST_LOREBOOK_CLASSIFIER, "config_id": character_chat["id"]},
            ],
        },
    )

    assert reassign_response.status_code == 200
    assert reassign_response.json() == [{"component": ComponentType.ST_LOREBOOK_CLASSIFIER, "config": character_chat}]

    unlink_response = client.put(
        "/config/llm/global-connections",
        json={
            "assignments": [
                {"component": ComponentType.ST_LOREBOOK_CLASSIFIER, "config_id": None},
                {"component": ComponentType.ST_CHARACTER_EXTRACTOR, "config_id": None},
            ],
        },
    )

    assert unlink_response.status_code == 200
    assert unlink_response.json() == []
    assert client.get(
        "/config/llm/global-connections",
        params={"components": components},
    ).json() == []


def test_global_llm_connections_returns_404_for_a_missing_config(config_api):
    client = config_api.client

    response = client.put(
        "/config/llm/global-connections",
        json={
            "assignments": [
                {"component": ComponentType.ST_LOREBOOK_CLASSIFIER, "config_id": str(uuid4())},
            ],
        },
    )

    assert response.status_code == 404


def test_config_endpoints_return_404_for_missing_resources(config_api):
    client = config_api.client
    missing_id = str(uuid4())
    connection = client.post("/config/connections", json=connection_payload()).json()
    chat = client.post("/config/llm/openai", json=openai_chat_payload()).json()
    embed = client.post("/config/embeddings/openai", json=openai_embed_payload()).json()
    tts = client.post("/config/tts/alltalk/xtts", json=alltalk_xtts_payload()).json()
    image = client.post("/config/images/comfyui", json=comfyui_image_payload()).json()
    stt = client.post("/config/stt/whispercpp", json=whisper_cpp_stt_payload()).json()

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
    assert client.get(f"/config/tts/{missing_id}").status_code == 404
    assert client.patch(f"/config/tts/{missing_id}", json={"speed": 1.0}).status_code == 404
    assert client.delete(f"/config/tts/{missing_id}").status_code == 404
    assert client.put(
        f"/config/tts/{missing_id}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 404
    assert client.put(
        f"/config/tts/{tts['id']}/connection",
        json={"connection_id": missing_id},
    ).status_code == 404
    assert client.get(f"/config/tts/{missing_id}/connection").status_code == 404
    assert client.delete(f"/config/tts/{missing_id}/connection").status_code == 404
    assert client.put(
        f"/simulations/{missing_id}/tts-connection",
        json={
            "component": ComponentType.NARRATOR_TTS,
            "config_id": tts["id"],
        },
    ).status_code == 404
    assert client.put(
        f"/simulations/{config_api.simulation.id}/tts-connection",
        json={
            "component": ComponentType.NARRATOR_TTS,
            "config_id": missing_id,
        },
    ).status_code == 404
    assert client.get(
        f"/simulations/{missing_id}/tts-connection",
        params={"component": ComponentType.NARRATOR_TTS},
    ).status_code == 404
    assert client.delete(
        f"/simulations/{missing_id}/tts-connection",
        params={"component": ComponentType.NARRATOR_TTS},
    ).status_code == 404
    assert client.get(f"/simulations/{missing_id}/tts-connections").status_code == 404
    assert client.put(
        f"/worlds/{config_api.world.id}/tts-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.NARRATOR_TTS,
                    "config_id": missing_id,
                },
            ],
        },
    ).status_code == 404
    assert client.get(f"/config/images/{missing_id}").status_code == 404
    assert client.patch(f"/config/images/{missing_id}", json={"steps": 20}).status_code == 404
    assert client.delete(f"/config/images/{missing_id}").status_code == 404
    assert client.put(
        f"/config/images/{missing_id}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 404
    assert client.put(
        f"/config/images/{image['id']}/connection",
        json={"connection_id": missing_id},
    ).status_code == 404
    assert client.get(f"/config/images/{missing_id}/connection").status_code == 404
    assert client.delete(f"/config/images/{missing_id}/connection").status_code == 404
    assert client.put(
        f"/simulations/{missing_id}/image-connection",
        json={
            "component": ComponentType.SCENE_IMAGE_GENERATOR,
            "config_id": image["id"],
        },
    ).status_code == 404
    assert client.put(
        f"/simulations/{config_api.simulation.id}/image-connection",
        json={
            "component": ComponentType.SCENE_IMAGE_GENERATOR,
            "config_id": missing_id,
        },
    ).status_code == 404
    assert client.get(
        f"/simulations/{missing_id}/image-connection",
        params={"component": ComponentType.SCENE_IMAGE_GENERATOR},
    ).status_code == 404
    assert client.delete(
        f"/simulations/{missing_id}/image-connection",
        params={"component": ComponentType.SCENE_IMAGE_GENERATOR},
    ).status_code == 404
    assert client.get(f"/simulations/{missing_id}/image-connections").status_code == 404
    assert client.put(
        f"/worlds/{config_api.world.id}/image-connections",
        json={
            "assignments": [
                {
                    "component": ComponentType.SCENE_IMAGE_GENERATOR,
                    "config_id": missing_id,
                },
            ],
        },
    ).status_code == 404
    assert client.get(f"/config/stt/{missing_id}").status_code == 404
    assert client.patch(f"/config/stt/{missing_id}", json={"temperature": 1.0}).status_code == 404
    assert client.delete(f"/config/stt/{missing_id}").status_code == 404
    assert client.put(
        f"/config/stt/{missing_id}/connection",
        json={"connection_id": connection["id"]},
    ).status_code == 404
    assert client.put(
        f"/config/stt/{stt['id']}/connection",
        json={"connection_id": missing_id},
    ).status_code == 404
    assert client.get(f"/config/stt/{missing_id}/connection").status_code == 404
    assert client.delete(f"/config/stt/{missing_id}/connection").status_code == 404
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


def test_simulation_image_generation_config_get_and_update(config_api):
    client = config_api.client

    default_response = client.get(f"/simulations/{config_api.simulation.id}/image-generation-config")

    assert default_response.status_code == 200
    assert default_response.json()["mode"] == "manual"
    assert default_response.json()["fallback_turns"] == 10

    update_response = client.put(
        f"/simulations/{config_api.simulation.id}/image-generation-config",
        json={"mode": "auto", "fallback_turns": 5},
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["mode"] == "auto"
    assert body["fallback_turns"] == 5

    get_response = client.get(f"/simulations/{config_api.simulation.id}/image-generation-config")
    assert get_response.json()["mode"] == "auto"
    assert get_response.json()["fallback_turns"] == 5
    # Updating again reuses the same config node rather than creating a new one.
    assert get_response.json()["id"] == body["id"]

    always_response = client.put(
        f"/simulations/{config_api.simulation.id}/image-generation-config",
        json={"mode": "always", "fallback_turns": 5},
    )
    assert always_response.json()["id"] == body["id"]
    assert always_response.json()["mode"] == "always"


def test_simulation_image_generation_config_missing_simulation_returns_404(config_api):
    client = config_api.client
    missing_id = str(uuid4())

    assert client.get(f"/simulations/{missing_id}/image-generation-config").status_code == 404
    assert client.put(
        f"/simulations/{missing_id}/image-generation-config",
        json={"mode": "auto", "fallback_turns": 5},
    ).status_code == 404
