from types import SimpleNamespace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from world_simulation_engine.misc.enums import ConnectionType, MessageRole
from world_simulation_engine.model import ConnectionConfig, EntityRelationship, InterpersonalRelationshipDetails, \
    OpenAiChatModelConfig, PromptMessage, RelationshipEntityRef, RelationshipScope
from world_simulation_engine.service.llm_service import LlmService


async def test_prepare_llm_service_requires_component_chat_config():
    database = Mock()
    database.config.get_chat_by_source = AsyncMock(return_value=None)
    database.config.get_connection_by_source = AsyncMock()
    component = InputInterpreter(database=database)

    with pytest.raises(ValueError, match="does not have a chat model configured"):
        await component._prepare_llm_service("simulation_1")

    database.config.get_chat_by_source.assert_awaited_once()
    database.config.get_connection_by_source.assert_not_called()


async def test_prepare_llm_service_requires_connection_for_chat_config():
    chat_config = OpenAiChatModelConfig(id="chat_1", name="Test chat", model="gpt-test")
    database = Mock()
    database.config = SimpleNamespace(
        get_chat_by_source=AsyncMock(return_value=chat_config),
        get_connection_by_source=AsyncMock(return_value=None),
    )
    component = InputInterpreter(database=database)

    with pytest.raises(ValueError, match="does not have a connection configured"):
        await component._prepare_llm_service("simulation_1")

    database.config.get_connection_by_source.assert_awaited_once_with(source_id="chat_1")


async def test_prepare_llm_service_builds_llm_when_config_is_complete(monkeypatch):
    chat_config = OpenAiChatModelConfig(id="chat_1", name="Test chat", model="gpt-test")
    connection_config = ConnectionConfig(
        id="connection_1",
        type=ConnectionType.OPENAI,
        name="Test connection",
        api_key="test-key",
    )
    database = Mock()
    database.config = SimpleNamespace(
        get_chat_by_source=AsyncMock(return_value=chat_config),
        get_connection_by_source=AsyncMock(return_value=connection_config),
    )
    component = InputInterpreter(database=database)
    created = {}

    class FakeLlmService:
        def __init__(self, *, model_config, connection_config):
            created["model_config"] = model_config
            created["connection_config"] = connection_config

    monkeypatch.setattr(
        "world_simulation_engine.component.simulator.simulator_component.LlmService",
        FakeLlmService,
    )

    llm = await component._prepare_llm_service("simulation_1")

    assert isinstance(llm, FakeLlmService)
    assert created == {
        "model_config": chat_config,
        "connection_config": connection_config,
    }


def test_relationship_context_message_renders_compact_directional_facts():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    relationship = EntityRelationship(
        scope_type=RelationshipScope.SIMULATION,
        scope_id="simulation_1",
        source=RelationshipEntityRef(type="character", id="character_1", name="Alex"),
        target=RelationshipEntityRef(type="character", id="character_2", name="Blair"),
        label="trusts",
        public_description="Alex relies on Blair.",
        details=InterpersonalRelationshipDetails(trust=0.5),
        created_at=now,
        last_changed_at=now,
    )
    prompts = InputInterpreter._with_relationship_context([
        PromptMessage(role=MessageRole.USER, content="Existing context."),
    ])
    service = LlmService(model_config=Mock(), connection_config=Mock())

    messages = service._compose_messages(
        prompts,
        data={"relationships": [relationship.model_dump()]},
    )

    assert len(messages) == 1
    assert "Alex (character_1) --trusts--> Blair (character_2)" in messages[0].content
    assert "trust" in messages[0].content
