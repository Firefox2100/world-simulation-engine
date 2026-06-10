from copy import deepcopy
from typing import Union, Any, TypeVar, Generic, TYPE_CHECKING
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from jinja2.sandbox import SandboxedEnvironment

from world_simulation_engine.misc.enums import LlmProvider, MessageRole, SystemMessagePolicy
from world_simulation_engine.model import AgentProfile, OllamaAgentBackendConfiguration, \
    OpenAiAgentBackendConfiguration, PromptMessage, LlmConnectionProfile

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI


LcMessage = AIMessage | HumanMessage | SystemMessage | ToolMessage


AgentProfileT = TypeVar("AgentProfileT", bound="AgentProfile")


class WorldAgent(Generic[AgentProfileT]):
    def __init__(self,
                 profile: AgentProfileT,
                 connection: LlmConnectionProfile,
                 ):
        self._profile = profile
        self._connection = connection
        self._model: Union["ChatOpenAI", "ChatOllama", None] = None

    def _create_model(self) -> Union["ChatOpenAI", "ChatOllama"]:
        if self._connection.provider == LlmProvider.OLLAMA:
            if not isinstance(self._profile.backend_configuration, OllamaAgentBackendConfiguration):
                raise ValueError(
                    f"Profile class mismatch: connection profile is Ollama while profile is {type(self._profile)}"
                )

            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=self._profile.backend_configuration.model,
                reasoning=self._profile.backend_configuration.reasoning,
                mirostat=self._profile.backend_configuration.mirostat,
                mirostat_eta=self._profile.backend_configuration.mirostat_eta,
                mirostat_tau=self._profile.backend_configuration.mirostat_tau,
                num_ctx=self._profile.backend_configuration.context_window,
                num_predict=self._profile.backend_configuration.num_predict,
                repeat_last_n=self._profile.backend_configuration.repeat_penalty_window,
                repeat_penalty=self._profile.backend_configuration.repeat_penalty,
                temperature=self._profile.backend_configuration.temperature,
                seed=self._profile.backend_configuration.seed,
                stop=self._profile.backend_configuration.stop_tokens,
                base_url=self._connection.base_url,
            )

        raise ValueError(f"Unsupported provider: {self._connection.provider}")

    @property
    def profile(self) -> AgentProfileT:
        return self._profile.model_copy()

    @property
    def model(self) -> Union["ChatOpenAI", "ChatOllama"]:
        if self._model is None:
            self._model = self._create_model()

        if self._model is None:
            raise ValueError("Model is not initialized.")

        return self._model

    def _message_postprocess(self, messages: list[LcMessage]) -> list[LcMessage]:
        """
        Post process the composed message sequence.
        :param messages: The LangChain messages to process
        :return: The merged messages, if configured to do so
        """

        def is_empty_message(msg: LcMessage) -> bool:
            if isinstance(msg, ToolMessage):
                return False

            content = msg.content

            if content is None:
                return True

            if isinstance(content, str):
                return content.strip() == ""

            if isinstance(content, list):
                return len(content) == 0

            return False

        def merge_content(a, b):
            if isinstance(a, str) and isinstance(b, str):
                return f"{a.rstrip()}{self.profile.message_merge_separator}{b.lstrip()}"

            if isinstance(a, list) and isinstance(b, list):
                return a + b

            if isinstance(a, str) and isinstance(b, list):
                return [{"type": "text", "text": a}] + b

            if isinstance(a, list) and isinstance(b, str):
                return a + [{"type": "text", "text": b}]

            return f"{str(a).rstrip()}\n\n{str(b).lstrip()}"

        def ai_has_tool_calls(msg: AIMessage) -> bool:
            return bool(
                getattr(msg, "tool_calls", None)
                or msg.additional_kwargs.get("tool_calls")
            )

        cleaned = deepcopy(messages)
        if self.profile.remove_empty_messages:
            cleaned = [m for m in cleaned if not is_empty_message(m)]

        if self.profile.system_message_policy == SystemMessagePolicy.MERGE_TO_TOP:
            # Merge all the system messages into one at the top
            system_messages: list[SystemMessage] = []
            non_system: list[LcMessage] = []

            for msg in cleaned:
                if isinstance(msg, SystemMessage):
                    system_messages.append(msg)
                else:
                    non_system.append(msg)

            if system_messages:
                merged_system_content = system_messages[0].content
                for msg in system_messages[1:]:
                    merged_system_content = merge_content(merged_system_content, msg.content)

                cleaned = [
                    SystemMessage(
                        content=merged_system_content,
                    )
                ] + non_system
        elif self.profile.system_message_policy == SystemMessagePolicy.DROP:
            # Remove all system messages that are not at the top
            cleaned = [m for m in cleaned if not (isinstance(m, SystemMessage) and m != cleaned[0])]

        # Merge adjacent message
        result = []
        for msg in cleaned:
            if not result:
                result.append(msg)
                continue

            prev = result[-1]

            if isinstance(prev, HumanMessage) and isinstance(msg, HumanMessage):
                if self.profile.merge_adjacent_user:
                    result[-1] = HumanMessage(content=merge_content(prev.content, msg.content))
                    continue

            if isinstance(prev, AIMessage) and isinstance(msg, AIMessage):
                if self.profile.merge_adjacent_assistant:
                    if not self.profile.merge_assistant_with_tool_calls and \
                            (ai_has_tool_calls(prev) or ai_has_tool_calls(msg)):
                        continue

                    result[-1] = AIMessage(content=merge_content(prev.content, msg.content))
                    continue

            result.append(msg)

        return result

    @staticmethod
    def _compose_messages(prompts: list[PromptMessage],
                          data: dict[str, Any],
                          ) -> list[LcMessage]:
        messages = []

        sandbox = SandboxedEnvironment()

        for prompt in prompts:
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
