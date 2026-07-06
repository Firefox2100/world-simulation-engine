import pytest
from testcontainers.neo4j import Neo4jContainer
from neo4j import AsyncGraphDatabase


@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:2026.04.0", username="neo4j", password="testpassword")\
            .with_env("NEO4J_PLUGINS", '["apoc","graph-data-science"]')\
            .with_env("NEO4J_apoc_export_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_use__neo4j__config", "true") as container:
        yield container


@pytest.fixture
async def neo4j_driver(neo4j_container):
    driver = AsyncGraphDatabase.driver(
        neo4j_container.get_connection_url(),
        auth=("neo4j", "testpassword"),
    )

    await driver.verify_connectivity()

    yield driver

    await driver.close()


@pytest.fixture
async def clean_neo4j(neo4j_driver):
    await neo4j_driver.execute_query("MATCH (n) DETACH DELETE n")
    yield neo4j_driver
    await neo4j_driver.execute_query("MATCH (n) DETACH DELETE n")
