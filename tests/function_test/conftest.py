import pytest
from unittest.mock import patch, PropertyMock
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding

from world_simulation_engine.service.world_agent.world_agent import WorldAgent
from world_simulation_engine.service.embedding import EmbeddingService
from world_simulation_engine.app import create_app
from .utils import FakeStructuredListChatModel


@pytest.fixture
def fake_model():
    fake_model = FakeStructuredListChatModel(responses=[])

    with patch.object(WorldAgent, "model", new_callable=PropertyMock) as mock_model:
        mock_model.return_value = fake_model

        yield fake_model


@pytest.fixture
def mock_app():
    with patch("world_simulation_engine.app.CONFIG") as mock_config:
        fake_embed = DeterministicFakeEmbedding(size=1024)

        with patch.object(EmbeddingService, "model", new_callable=PropertyMock) as mock_embed:
            mock_embed.return_value = fake_embed
            mock_config.database_path = ":memory:"

            app = create_app()
            yield app


@pytest.fixture
def mock_client(mock_app):
    with TestClient(mock_app) as client:
        yield client
