from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model.connection_profile import LlmConnectionProfile
from world_simulation_engine.model.agent_preset import OllamaAgentBackendConfiguration, AgentProfile
from world_simulation_engine.service.world_agent.world_agent import WorldAgent


class TestWorldAgent:
    def test_init(self):
        agent = WorldAgent(
            profile=AgentProfile(
                backend_configuration=OllamaAgentBackendConfiguration(
                    connection=1,
                    model="llama3.1:7b",
                ),
            ),
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url="http://127.0.0.1:11434",
            )
        )

        assert agent.profile.backend_configuration.connection == 1

        assert agent._connection.provider == LlmProvider.OLLAMA
        assert agent._connection.base_url == "http://127.0.0.1:11434"
        assert agent._connection.api_key is None
