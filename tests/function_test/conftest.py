import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from world_simulation_engine.app import create_app


@pytest.fixture
def mock_app():
    with patch("world_simulation_engine.app.CONFIG") as mock_config:
        mock_config.database_path = ":memory:"

        app = create_app()
        yield app


@pytest.fixture
def mock_client(mock_app):
    with TestClient(mock_app) as client:
        yield client
