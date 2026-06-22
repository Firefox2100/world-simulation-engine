import pytest
from unittest.mock import patch, PropertyMock

from world_simulation_engine.service.world_agent.world_agent import WorldAgent
from .utils import FakeStructuredListChatModel


@pytest.fixture
def fake_model():
    fake_model = FakeStructuredListChatModel(responses=[])

    with patch.object(WorldAgent, "model", new_callable=PropertyMock) as mock_model:
        mock_model.return_value = fake_model

        yield fake_model
