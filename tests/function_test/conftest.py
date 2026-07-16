import pytest
from testcontainers.neo4j import Neo4jContainer


@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:2026.04.0", username="neo4j", password="testpassword")\
            .with_env("NEO4J_PLUGINS", '["apoc","graph-data-science"]')\
            .with_env("NEO4J_apoc_export_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_use__neo4j__config", "true") as container:
        yield container
