from typing import Union, Any, TYPE_CHECKING
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from jinja2.sandbox import SandboxedEnvironment

from world_simulation_engine.misc.enums import LlmProvider, MessageRole
from world_simulation_engine.model.agent_preset import AgentProfiles, OllamaAgentProfile, OpenAiAgentProfile

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI


class WorldAgent:
    def __init__(self,
                 profile: AgentProfiles,
                 ):
        self._profile = profile
        self._model: Union["ChatOpenAI", "ChatOllama", None] = None

    @staticmethod
    def _create_model(profile: AgentProfiles) -> Union["ChatOpenAI", "ChatOllama"]:
        if profile.connection is None:
            raise ValueError("Connection profile is required for creating a model.")

        if profile.connection.provider == LlmProvider.OLLAMA:
            if not isinstance(profile, OllamaAgentProfile):
                raise ValueError(f"Profile class mismatch: connection profile is Ollama while profile is {type(profile)}")

            return ChatOllama(
                model=profile.model,
                reasoning=profile.reasoning,
                mirostat=profile.mirostat,
                mirostat_eta=profile.mirostat_eta,
                mirostat_tau=profile.mirostat_tau,
                num_ctx=profile.context_window,
                num_predict=profile.num_predict,
                repeat_last_n=profile.repeat_penalty_window,
                repeat_penalty=profile.repeat_penalty,
                temperature=profile.temperature,
                seed=profile.seed,
                stop=profile.stop_tokens,
                base_url=profile.connection.base_url,
            )

        raise ValueError(f"Unsupported provider: {profile.connection.provider}")

    @property
    def profile(self) -> AgentProfiles:
        return self._profile.model_copy()

    @property
    def model(self) -> Union["ChatOpenAI", "ChatOllama"]:
        if self._model is None:
            self._model = self._create_model(self._profile)

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    def _compose_messages(self,
                          data: dict[str, Any],
                          ) -> list[AIMessage | HumanMessage | SystemMessage | ToolMessage]:
        messages = []

        sandbox = SandboxedEnvironment()

        for prompt in self.profile.prompts:
            rendered_content = sandbox.from_string(
                prompt.content
            ).render(
                data=data,
            )

            if prompt.role == MessageRole.SYSTEM:
                messages.append(
                    SystemMessage(content=rendered_content)
                )
            elif prompt.role == MessageRole.ASSISTANT:
                messages.append(
                    AIMessage(content=rendered_content)
                )
            elif prompt.role == MessageRole.USER:
                messages.append(
                    HumanMessage(content=rendered_content)
                )
            elif prompt.role == MessageRole.TOOL:
                messages.append(
                    ToolMessage(content=rendered_content)
                )
            else:
                raise ValueError(f"Unsupported message role: {prompt.role}")

        return messages
