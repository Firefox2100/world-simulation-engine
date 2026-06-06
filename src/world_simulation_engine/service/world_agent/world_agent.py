from typing import Union, TYPE_CHECKING
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model.agent_preset import AgentProfiles, OllamaAgentProfile, OpenAiAgentProfile


if TYPE_CHECKING:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI


class WorldAgent:
    def __init__(self,
                 preset: AgentProfiles,
                 ):
        self._preset = preset
        self._model: Union["ChatOpenAI", "ChatOllama", None] = None

    @staticmethod
    def _create_model(preset: AgentProfiles) -> Union["ChatOpenAI", "ChatOllama"]:
        if preset.profile is None:
            raise ValueError("Profile is required for creating a model.")

        if preset.profile.provider == LlmProvider.OLLAMA:
            if not isinstance(preset, OllamaAgentProfile):
                raise ValueError(f"Preset class mismatch: profile is Ollama while preset is {type(preset)}")

            return ChatOllama(
                model=preset.model,
                reasoning=preset.reasoning,
                mirostat=preset.mirostat,
                mirostat_eta=preset.mirostat_eta,
                mirostat_tau=preset.mirostat_tau,
                num_ctx=preset.context_window,
                num_predict=preset.num_predict,
                repeat_last_n=preset.repeat_penalty_window,
                repeat_penalty=preset.repeat_penalty,
                temperature=preset.temperature,
                seed=preset.seed,
                stop=preset.stop_tokens,
            )

        raise ValueError(f"Unsupported provider: {preset.profile.provider}")

    @property
    def preset(self) -> AgentProfiles:
        return self._preset.model_copy()

    @property
    def model(self) -> Union["ChatOpenAI", "ChatOllama"]:
        if self._model is None:
            self._model = self._create_model(self._preset)

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    def _compose_messages(self) -> list[AIMessage | HumanMessage | SystemMessage | ToolMessage]:
        messages = []

        return messages
