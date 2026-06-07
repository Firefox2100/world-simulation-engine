from world_simulation_engine.misc.enums import LlmProvider, MessageRole
from world_simulation_engine.model.connection_profile import LlmConnectionProfile
from world_simulation_engine.model.prompt_message import PromptMessage
from world_simulation_engine.model.agent_preset import OllamaAgentProfile
from world_simulation_engine.service.world_agent.world_agent import WorldAgent


class TestWorldAgent:
    def test_init(self):
        agent = WorldAgent(
            profile=OllamaAgentProfile(
                connection=LlmConnectionProfile(
                    provider=LlmProvider.OLLAMA,
                    base_url="http://127.0.0.1:11434",
                ),
                model="llama3.1:7b",
                prompts=[
                    PromptMessage(
                        role=MessageRole.SYSTEM,
                        content="You are a helpful assistant."
                    ),
                    PromptMessage(
                        role=MessageRole.USER,
                        content="Hello!"
                    )
                ],
            ),
        )

        assert agent.profile.connection.provider == LlmProvider.OLLAMA
        assert agent.profile.connection.base_url == "http://127.0.0.1:11434"
        assert agent.profile.connection.api_key is None
