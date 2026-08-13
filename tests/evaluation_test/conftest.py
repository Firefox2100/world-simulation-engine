from __future__ import annotations

import os

import pytest
from neo4j import AsyncGraphDatabase
from testcontainers.neo4j import Neo4jContainer

from world_simulation_engine.misc.enums import ComponentType, ConnectionType
from world_simulation_engine.model import (
    ConnectionConfig,
    OllamaEmbedModelConfig,
    OpenAiEmbedModelConfig,
)
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.embed_service import EmbedService

from eval_llm_config import (
    _env_optional_int,
    build_evaluation_chat_model_config,
    build_evaluation_connection_config,
)
from world_fixtures import DEFAULT_WORLD_DIR, WorldBundle, load_world_bundle


def pytest_collection_modifyitems(items):
    """Group evaluation tests into independently selectable internal workflows."""
    sillytavern_marker = pytest.mark.evaluation_sillytavern
    simulation_marker = pytest.mark.evaluation_simulation

    for item in items:
        if "evaluation_test" not in item.path.parts:
            continue
        marker = sillytavern_marker if item.path.name.startswith("test_sillytavern_") else simulation_marker
        item.add_marker(marker)


@pytest.fixture(scope="session")
def evaluation_connection_config() -> ConnectionConfig:
    return build_evaluation_connection_config()


@pytest.fixture(scope="session")
def evaluation_chat_model_config(evaluation_connection_config: ConnectionConfig):
    return build_evaluation_chat_model_config(evaluation_connection_config)


@pytest.fixture(scope="session")
def evaluation_embed_model_config(evaluation_connection_config: ConnectionConfig):
    if evaluation_connection_config.type == ConnectionType.OPENAI:
        return OpenAiEmbedModelConfig(
            id=os.getenv("WSE_EVAL_EMBED_CONFIG_ID", "eval_embed"),
            name=os.getenv("WSE_EVAL_EMBED_CONFIG_NAME", "Evaluation embedding"),
            model=os.getenv("WSE_EVAL_EMBED_MODEL", "text-embedding-3-small"),
            dimension=_env_optional_int("WSE_EVAL_EMBED_DIMENSION"),
        )

    return OllamaEmbedModelConfig(
        id=os.getenv("WSE_EVAL_EMBED_CONFIG_ID", "eval_embed"),
        name=os.getenv("WSE_EVAL_EMBED_CONFIG_NAME", "Evaluation embedding"),
        model=os.getenv("WSE_EVAL_EMBED_MODEL", "nomic-embed-text"),
        dimension=_env_optional_int("WSE_EVAL_EMBED_DIMENSION"),
        context_window=_env_optional_int("WSE_EVAL_EMBED_CONTEXT_WINDOW"),
    )


@pytest.fixture
def evaluation_embed_service(
    evaluation_connection_config: ConnectionConfig,
    evaluation_embed_model_config,
) -> EmbedService:
    return EmbedService(
        model_config=evaluation_embed_model_config,
        connection_config=evaluation_connection_config,
    )


@pytest.fixture(scope="session")
def ollama_chat_model_config(evaluation_chat_model_config):
    return evaluation_chat_model_config


@pytest.fixture(scope="session")
def ollama_embed_model_config(evaluation_embed_model_config):
    return evaluation_embed_model_config


@pytest.fixture(scope="session")
def evaluation_neo4j_container():
    image = os.getenv("WSE_EVAL_NEO4J_IMAGE", "neo4j:2026.04.0")
    password = os.getenv("WSE_EVAL_NEO4J_PASSWORD", "testpassword")
    with Neo4jContainer(image, username="neo4j", password=password)\
            .with_env("NEO4J_PLUGINS", '["apoc","graph-data-science"]')\
            .with_env("NEO4J_apoc_export_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_use__neo4j__config", "true") as container:
        yield container


@pytest.fixture
async def evaluation_neo4j_driver(evaluation_neo4j_container):
    password = os.getenv("WSE_EVAL_NEO4J_PASSWORD", "testpassword")
    driver = AsyncGraphDatabase.driver(
        evaluation_neo4j_container.get_connection_url(),
        auth=("neo4j", password),
    )
    await driver.verify_connectivity()

    try:
        yield driver
    finally:
        await driver.close()


@pytest.fixture
async def evaluation_database(evaluation_neo4j_driver, evaluation_embed_service):
    await evaluation_neo4j_driver.execute_query("MATCH (n) DETACH DELETE n")
    database = DatabaseService(evaluation_neo4j_driver, embed_service=evaluation_embed_service)
    try:
        yield database
    finally:
        await evaluation_neo4j_driver.execute_query("MATCH (n) DETACH DELETE n")


@pytest.fixture
async def mock_graph_world_setup(evaluation_database, request) -> WorldBundle:
    """The evaluation world bundle to seed for this test - loaded from a directory in the shape
    world_fixtures.py documents. Defaults to tests/evaluation_test/worlds/blackwater_observatory/,
    but a test can run against a *specific* discovered world (see workflow_helpers.py's
    WORLD_DIRS/`_cases_for`) via indirect parametrization:

        @pytest.mark.parametrize(
            ("mock_graph_world_setup", "case"), SOME_CASES, indirect=["mock_graph_world_setup"],
        )

    where each entry in SOME_CASES is a (world_dir, case) pair - pytest passes world_dir through
    to this fixture as `request.param` and `case` straight to the test. Function-scoped, matching
    evaluation_database: each test gets a fresh testcontainer database, so the bundle is
    (re-)loaded into it once per test rather than reused across tests."""
    world_dir = getattr(request, "param", DEFAULT_WORLD_DIR)
    return await load_world_bundle(evaluation_database, world_dir)


@pytest.fixture
async def evaluation_seeded_database(
    evaluation_database,
    mock_graph_world_setup,
    evaluation_connection_config,
    evaluation_chat_model_config,
    evaluation_embed_model_config,
):
    await evaluation_database.config.create_connection(evaluation_connection_config)
    await evaluation_database.config.create_chat(evaluation_chat_model_config)
    await evaluation_database.config.create_embed(evaluation_embed_model_config)
    await evaluation_database.config.link_connection(
        source_id=evaluation_chat_model_config.id,
        connection_id=evaluation_connection_config.id,
    )
    await evaluation_database.config.link_connection(
        source_id=evaluation_embed_model_config.id,
        connection_id=evaluation_connection_config.id,
    )
    await evaluation_database.config.link_chat(
        source_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        component=ComponentType.INPUT_INTERPRETER,
    )
    await evaluation_database.config.link_embed(
        source_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_embed_model_config.id,
        component=ComponentType.CHARACTER_SIMULATOR,
    )

    return evaluation_database
