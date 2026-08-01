import json
import re
from copy import deepcopy
from typing import Any, TypeVar, Type, TYPE_CHECKING, cast
from langchain.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel

from world_simulation_engine.misc.enums import ConnectionType, MessageRole, SystemMessagePolicy
from world_simulation_engine.model import Ai21ChatModelConfig, AnthropicChatModelConfig, ChatModelConfigUnion, \
    CloudflareChatModelConfig, CohereChatModelConfig, ConnectionConfig, DeepSeekChatModelConfig, \
    GoogleGenAiChatModelConfig, GroqChatModelConfig, MistralAiChatModelConfig, OllamaChatModelConfig, \
    OpenAiChatModelConfig, OpenRouterChatModelConfig, PerplexityChatModelConfig, PromptMessage, \
    XAiChatModelConfig

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


LcMessage = AIMessage | HumanMessage | SystemMessage | ToolMessage
T = TypeVar("T", bound=BaseModel)


class LlmService:
    _REPAIR_ERROR_LIMIT = 2000
    _REPAIR_RAW_LIMIT = 2000

    def __init__(self,
                 model_config: ChatModelConfigUnion,
                 connection_config: ConnectionConfig,
                 remove_empty_messages: bool = False,
                 message_merge_separator: str = "\n\n",
                 merge_adjacent_user: bool = True,
                 merge_adjacent_assistant: bool = True,
                 merge_assistant_with_tool_calls: bool = False,
                 system_message_policy: SystemMessagePolicy = SystemMessagePolicy.PRESERVE,
                 ):
        self._model_config = model_config
        self._connection_config = connection_config
        self._remove_empty_messages = remove_empty_messages
        self._message_merge_separator = message_merge_separator
        self._merge_adjacent_user = merge_adjacent_user
        self._merge_adjacent_assistant = merge_adjacent_assistant
        self._merge_assistant_with_tool_calls = merge_assistant_with_tool_calls
        self._system_message_policy = system_message_policy

        self._model: "BaseChatModel | None" = None

    @staticmethod
    def _without_none(**kwargs) -> dict[str, Any]:
        return {
            key: value
            for key, value in kwargs.items()
            if value is not None
        }

    def _api_kwargs(self) -> dict[str, Any]:
        return self._without_none(
            api_key=self._connection_config.api_key,
            base_url=self._connection_config.base_url,
        )

    def _openai_kwargs(self, config: OpenAiChatModelConfig) -> dict[str, Any]:
        return self._without_none(
            model=config.model,
            temperature=config.temperature,
            seed=config.seed,
            reasoning=config.reasoning,
            stop_sequences=config.stop_tokens,
            model_kwargs=config.model_kwargs,
            organization=config.organization,
            openai_proxy=config.openai_proxy,
            timeout=config.request_timeout,
            stream_usage=config.stream_usage,
            max_retries=config.max_retries,
            presence_penalty=config.presence_penalty,
            frequency_penalty=config.frequency_penalty,
            logprobs=config.logprobs,
            top_logprobs=config.top_logprobs,
            logit_bias=config.logit_bias,
            streaming=config.streaming,
            n=config.n,
            top_p=config.top_p,
            max_completion_tokens=config.max_completion_tokens,
            reasoning_effort=config.reasoning_effort,
            verbosity=config.verbosity,
            tiktoken_model_name=config.tiktoken_model_name,
            default_headers=config.default_headers,
            default_query=config.default_query,
            http_socket_options=config.http_socket_options,
            stream_chunk_timeout=config.stream_chunk_timeout,
            extra_body=config.extra_body,
            include_response_headers=config.include_response_headers,
            disabled_params=config.disabled_params,
            context_management=config.context_management,
            include=config.include,
            service_tier=config.service_tier,
            store=config.store,
            truncation=config.truncation,
            use_previous_response_id=config.use_previous_response_id,
            use_responses_api=config.use_responses_api,
            **self._api_kwargs(),
        )

    def _openai_compatible_kwargs(self, config: OpenAiChatModelConfig) -> dict[str, Any]:
        max_tokens = getattr(config, "max_tokens", None) or config.max_completion_tokens
        return self._without_none(
            model=config.model,
            temperature=config.temperature,
            seed=config.seed,
            stop=config.stop_tokens,
            model_kwargs=config.model_kwargs,
            timeout=config.request_timeout,
            request_timeout=config.request_timeout,
            stream_usage=config.stream_usage,
            max_retries=config.max_retries,
            presence_penalty=config.presence_penalty,
            frequency_penalty=config.frequency_penalty,
            logprobs=config.logprobs,
            top_logprobs=config.top_logprobs,
            logit_bias=config.logit_bias,
            streaming=config.streaming,
            n=config.n,
            top_p=config.top_p,
            max_tokens=max_tokens,
            max_completion_tokens=config.max_completion_tokens,
            reasoning=config.reasoning,
            reasoning_effort=config.reasoning_effort,
            default_headers=config.default_headers,
            extra_body=config.extra_body,
            **self._api_kwargs(),
        )

    def _expect_config(self, expected_type: type[T]) -> T:
        if not isinstance(self._model_config, expected_type):
            raise ValueError(
                "Model config class mismatch: connection config is "
                f"{self._connection_config.type} while model config is {type(self._model_config)}"
            )
        return self._model_config

    def _create_ollama_model(self):
        config = self._expect_config(OllamaChatModelConfig)
        from langchain_ollama import ChatOllama

        return ChatOllama(**self._without_none(
            model=config.model,
            reasoning=config.reasoning,
            mirostat=config.mirostat,
            mirostat_eta=config.mirostat_eta,
            mirostat_tau=config.mirostat_tau,
            num_ctx=config.context_window,
            num_predict=config.num_predict,
            repeat_last_n=config.repeat_penalty_window,
            repeat_penalty=config.repeat_penalty,
            temperature=config.temperature,
            seed=config.seed,
            stop=config.stop_tokens,
            base_url=self._connection_config.base_url,
            validate_model_on_init=config.validate_model_on_init,
            num_gpu=config.num_gpu,
            num_thread=config.num_thread,
            logprobs=config.logprobs,
            top_logprobs=config.top_logprobs,
            tfs_z=config.tfs_z,
            top_k=config.top_k,
            top_p=config.top_p,
            format=config.format,
            keep_alive=config.keep_alive,
            client_kwargs=config.client_kwargs,
            async_client_kwargs=config.async_client_kwargs,
            sync_client_kwargs=config.sync_client_kwargs,
        ))

    def _create_openai_model(self):
        config = self._expect_config(OpenAiChatModelConfig)
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(**self._openai_kwargs(config))

    def _create_anthropic_model(self):
        config = self._expect_config(AnthropicChatModelConfig)
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(**self._without_none(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
            top_p=config.top_p,
            top_k=config.top_k,
            thinking=config.thinking,
            output_config=config.output_config,
            stream_usage=config.stream_usage,
            streaming=config.streaming,
            default_headers=config.default_headers,
            betas=config.betas,
            service_tier=config.service_tier,
            mcp_servers=config.mcp_servers,
            container=config.container,
            inference_geo=config.inference_geo,
            stop_sequences=config.stop_tokens,
            model_kwargs=config.model_kwargs,
            **self._api_kwargs(),
        ))

    def _create_openrouter_model(self):
        config = self._expect_config(OpenRouterChatModelConfig)
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(**self._openai_compatible_kwargs(config))

    def _create_ai21_model(self):
        config = self._expect_config(Ai21ChatModelConfig)
        from langchain_ai21 import ChatAI21

        return ChatAI21(**self._without_none(
            model=config.model,
            temperature=config.temperature,
            stop=config.stop_tokens,
            model_kwargs=config.model_kwargs,
            streaming=config.streaming,
            max_tokens=config.max_tokens,
            min_tokens=config.min_tokens,
            top_p=config.top_p,
            num_results=config.num_results,
            logit_bias=config.logit_bias,
            presence_penalty=config.presence_penalty,
            count_penalty=config.count_penalty,
            frequency_penalty=config.frequency_penalty,
            **self._api_kwargs(),
        ))

    def _create_google_genai_model(self):
        config = self._expect_config(GoogleGenAiChatModelConfig)
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(**self._without_none(
            model=config.model,
            temperature=config.temperature,
            seed=config.seed,
            stop=config.stop_tokens,
            model_kwargs=config.model_kwargs,
            max_output_tokens=config.max_output_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
            n=config.n,
            max_retries=config.max_retries,
            timeout=config.timeout,
            safety_settings=config.safety_settings,
            response_mime_type=config.response_mime_type,
            response_schema=config.response_schema,
            cached_content=config.cached_content,
            thinking_budget=config.thinking_budget,
            include_thoughts=config.include_thoughts,
            transport=config.transport,
            client_options=config.client_options,
            api_key=self._connection_config.api_key,
            base_url=self._connection_config.base_url,
        ))

    def _create_mistralai_model(self):
        config = self._expect_config(MistralAiChatModelConfig)
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(**self._without_none(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            random_seed=config.random_seed,
            safe_mode=config.safe_mode,
            streaming=config.streaming,
            endpoint=config.endpoint or self._connection_config.base_url,
            timeout=config.timeout,
            max_retries=config.max_retries,
            max_concurrent_requests=config.max_concurrent_requests,
            mistral_api_key=self._connection_config.api_key,
            model_kwargs=config.model_kwargs,
            stop=config.stop_tokens,
        ))

    def _create_cohere_model(self):
        config = self._expect_config(CohereChatModelConfig)
        from langchain_cohere import ChatCohere

        return ChatCohere(**self._without_none(
            model=config.model,
            temperature=config.temperature,
            preamble=config.preamble,
            streaming=config.streaming,
            user_agent=config.user_agent,
            timeout_seconds=config.timeout_seconds,
            cohere_api_key=self._connection_config.api_key,
            base_url=self._connection_config.base_url,
            model_kwargs=config.model_kwargs,
            stop_sequences=config.stop_tokens,
        ))

    def _create_perplexity_model(self):
        config = self._expect_config(PerplexityChatModelConfig)
        from langchain_perplexity import ChatPerplexity

        kwargs = self._openai_compatible_kwargs(config)
        kwargs["pplx_api_key"] = kwargs.pop("api_key", None)
        return ChatPerplexity(**self._without_none(**kwargs))

    def _create_groq_model(self):
        config = self._expect_config(GroqChatModelConfig)
        from langchain_groq import ChatGroq

        return ChatGroq(**self._without_none(
            **self._openai_compatible_kwargs(config),
            reasoning_format=config.reasoning_format,
            response_format=config.response_format,
            parallel_tool_calls=config.parallel_tool_calls,
        ))

    def _create_deepseek_model(self):
        config = self._expect_config(DeepSeekChatModelConfig)
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(**self._openai_compatible_kwargs(config))

    def _create_xai_model(self):
        config = self._expect_config(XAiChatModelConfig)
        from langchain_xai import ChatXAI

        return ChatXAI(**self._without_none(
            **self._openai_compatible_kwargs(config),
            search_parameters=config.search_parameters,
        ))

    def _create_cloudflare_model(self):
        config = self._expect_config(CloudflareChatModelConfig)
        from langchain_cloudflare.chat_models import ChatCloudflareWorkersAI

        return ChatCloudflareWorkersAI(**self._without_none(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
            streaming=config.streaming,
            account_id=config.account_id,
            api_token=self._connection_config.api_key,
            base_url=self._connection_config.base_url,
            endpoint_format=config.endpoint_format,
            ai_gateway=config.ai_gateway,
            model_kwargs=config.model_kwargs,
            stop=config.stop_tokens,
        ))

    def _create_model(self) -> "BaseChatModel":
        if self._connection_config.type == ConnectionType.OLLAMA:
            return self._create_ollama_model()
        if self._connection_config.type == ConnectionType.OPENAI:
            return self._create_openai_model()
        if self._connection_config.type == ConnectionType.ANTHROPIC:
            return self._create_anthropic_model()
        if self._connection_config.type == ConnectionType.OPENROUTER:
            return self._create_openrouter_model()
        if self._connection_config.type == ConnectionType.AI21:
            return self._create_ai21_model()
        if self._connection_config.type == ConnectionType.GOOGLE_GENAI:
            return self._create_google_genai_model()
        if self._connection_config.type == ConnectionType.MISTRALAI:
            return self._create_mistralai_model()
        if self._connection_config.type == ConnectionType.COHERE:
            return self._create_cohere_model()
        if self._connection_config.type == ConnectionType.PERPLEXITY:
            return self._create_perplexity_model()
        if self._connection_config.type == ConnectionType.GROQ:
            return self._create_groq_model()
        if self._connection_config.type == ConnectionType.DEEPSEEK:
            return self._create_deepseek_model()
        if self._connection_config.type == ConnectionType.XAI:
            return self._create_xai_model()
        if self._connection_config.type == ConnectionType.CLOUDFLARE:
            return self._create_cloudflare_model()

        raise ValueError(f"Unsupported provider: {self._connection_config.type}")

    @property
    def model(self) -> "BaseChatModel":
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
                return f"{a.rstrip()}{self._message_merge_separator}{b.lstrip()}"

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
        if self._remove_empty_messages:
            cleaned = [m for m in cleaned if not is_empty_message(m)]

        if self._system_message_policy == SystemMessagePolicy.MERGE_TO_TOP:
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
        elif self._system_message_policy == SystemMessagePolicy.DROP:
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
                if self._merge_adjacent_user:
                    result[-1] = HumanMessage(content=merge_content(prev.content, msg.content))
                    continue

            if isinstance(prev, AIMessage) and isinstance(msg, AIMessage):
                if self._merge_adjacent_assistant:
                    if not self._merge_assistant_with_tool_calls and \
                            (ai_has_tool_calls(prev) or ai_has_tool_calls(msg)):
                        continue

                    result[-1] = AIMessage(content=merge_content(prev.content, msg.content))
                    continue

            result.append(msg)

        return result

    def _compose_messages(self,
                          prompts: list[PromptMessage],
                          data: dict[str, Any],
                          ) -> list[LcMessage]:
        messages = []

        sandbox = SandboxedEnvironment()

        for prompt in prompts:
            rendered_content = sandbox.from_string(
                prompt.content
            ).render(data)

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

        return self._message_postprocess(messages)

    @classmethod
    def _truncate_for_repair(cls, value: Any, limit: int) -> str:
        text = str(value)
        if len(text) <= limit:
            return text

        return f"{text[:limit]}... [truncated {len(text) - limit} chars]"

    @classmethod
    def _parse_raw_with_output_model(cls,
                                     output_model: Type[T],
                                     raw: Any,
                                     ) -> T | None:
        for candidate in cls._raw_structured_candidates(raw):
            try:
                if isinstance(candidate, output_model):
                    return candidate
                if isinstance(candidate, dict):
                    return output_model.model_validate(candidate)
                if isinstance(candidate, str):
                    try:
                        return output_model.model_validate_json(candidate)
                    except Exception:
                        parsed_candidate = cls._first_json_object(candidate)
                        if parsed_candidate is not None:
                            return output_model.model_validate(parsed_candidate)
                        for repaired_candidate in cls._json_repair_candidates(candidate):
                            try:
                                return output_model.model_validate_json(repaired_candidate)
                            except Exception:
                                parsed_repaired_candidate = cls._first_json_object(repaired_candidate)
                                if parsed_repaired_candidate is not None:
                                    return output_model.model_validate(parsed_repaired_candidate)
            except Exception:
                continue

        return None

    @classmethod
    def _raw_structured_candidates(cls, raw: Any) -> list[Any]:
        candidates = []
        content = getattr(raw, "content", raw)
        if content not in (None, ""):
            candidates.append(content)

        tool_calls = getattr(raw, "tool_calls", None)
        additional_kwargs = getattr(raw, "additional_kwargs", None)
        if not tool_calls and isinstance(additional_kwargs, dict):
            tool_calls = additional_kwargs.get("tool_calls")

        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue

                args = tool_call.get("args")
                if args is not None:
                    candidates.append(args)

                function = tool_call.get("function")
                if isinstance(function, dict) and function.get("arguments") is not None:
                    candidates.append(function["arguments"])

        return candidates

    @staticmethod
    def _first_json_object(value: str) -> Any | None:
        start = value.find("{")
        if start == -1:
            return None

        decoder = json.JSONDecoder()
        try:
            parsed, _ = decoder.raw_decode(value[start:])
        except json.JSONDecodeError:
            return None

        return parsed

    @staticmethod
    def _json_type_label(schema: Any, defs: dict[str, Any]) -> str:
        """Render a compact, human-readable type label for one JSON Schema node."""
        if not isinstance(schema, dict):
            return "any"

        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            target = defs.get(name, {})
            # Enum classes (e.g. ActionType) are their own named $defs entry; resolve to the
            # actual allowed values so the guide can spell them out inline like a Literal enum,
            # rather than making the model guess valid values from a bare type name.
            if "enum" in target and "properties" not in target:
                return "enum[" + ", ".join(repr(value) for value in target["enum"]) + "]"
            return name

        for combinator in ("anyOf", "oneOf"):
            if combinator in schema:
                labels = [
                    LlmService._json_type_label(option, defs)
                    for option in schema[combinator]
                ]
                return " | ".join(dict.fromkeys(labels))

        if "allOf" in schema and len(schema["allOf"]) == 1:
            return LlmService._json_type_label(schema["allOf"][0], defs)

        if "const" in schema:
            return repr(schema["const"])

        if "enum" in schema:
            return "enum[" + ", ".join(repr(value) for value in schema["enum"]) + "]"

        schema_type = schema.get("type")
        if schema_type == "array":
            return f"list[{LlmService._json_type_label(schema.get('items', {}), defs)}]"

        return schema_type or "any"

    @staticmethod
    def _json_schema_field_guide(
            schema: Any,
            defs: dict[str, Any],
            *,
            depth: int = 0,
            max_depth: int = 4,
            expanded: set[str] | None = None,
    ) -> list[str]:
        """Recursively describe object fields (name, type, required/optional, description).

        `expanded` tracks referenced type names across the *entire* guide (not just the current
        path), so a type referenced many times (e.g. StateCommitEntityRef inside every
        StateCommitOperation variant) is spelled out once and only referred to by name afterward.
        This keeps discriminated-union/recursive schemas from re-expanding indefinitely and keeps
        the guide short enough to stay useful in a local model's context window.
        """
        if expanded is None:
            expanded = set()

        if not isinstance(schema, dict):
            return []

        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            if name in expanded:
                return []
            expanded.add(name)
            schema = defs.get(name, {})

        for combinator in ("anyOf", "oneOf"):
            if combinator in schema:
                lines = []
                for option in schema[combinator]:
                    lines.extend(LlmService._json_schema_field_guide(
                        option, defs, depth=depth, max_depth=max_depth, expanded=expanded,
                    ))
                return lines

        properties = schema.get("properties")
        if not properties:
            return []

        required = set(schema.get("required", []))
        indent = "  " * depth
        lines = []
        for field_name, field_schema in properties.items():
            type_label = LlmService._json_type_label(field_schema, defs)
            requirement = "required" if field_name in required else "optional"
            description = field_schema.get("description")
            suffix = f" - {description}" if description else ""
            lines.append(f"{indent}- {field_name}: {type_label} ({requirement}){suffix}")

            if depth < max_depth:
                nested_schema = field_schema.get("items", {}) if field_schema.get("type") == "array" else field_schema
                lines.extend(LlmService._json_schema_field_guide(
                    nested_schema, defs, depth=depth + 1, max_depth=max_depth, expanded=expanded,
                ))

        return lines

    @classmethod
    def _schema_guidance_text(cls, output_model: Type[T], *, max_chars: int = 4000) -> str:
        """Build an explicit field guide from the Pydantic schema for the prompt text itself.

        Constrained/native structured-output decoding only guarantees syntactic compliance; small
        local models still routinely skip optional fields or misuse discriminated-union shapes
        unless the schema and its per-field intent are spelled out in the natural-language context
        as well, not only enforced by the decoder.
        """
        schema = output_model.model_json_schema()
        defs = schema.get("$defs", {})
        lines = cls._json_schema_field_guide(schema, defs, expanded={output_model.__name__})
        body = "\n".join(lines)
        if len(body) > max_chars:
            body = f"{body[:max_chars]}\n... (schema truncated)"

        return (
            f"## Output schema field guide for {output_model.__name__}\n\n"
            f"{body}\n\n"
            "Populate every required field. For optional fields, include a concrete value whenever "
            "the context above supports one; only leave an optional field at its default (null/empty) "
            "when nothing in the context applies to it. Do not invent fields that are not listed here."
        )

    @staticmethod
    def _json_repair_candidates(value: str) -> list[str]:
        """
        Return conservative repairs for common local structured-output glitches.

        This intentionally handles only narrow, observed JSON bracket slips and still relies on
        the target Pydantic model for semantic validation.
        """
        start = value.find("{")
        if start == -1:
            return []

        json_text = value[start:]
        repairs = []
        for pattern in (
            r'(\n\s*}\s*)\]\s*(\n\s*)},(\s*\n\s*"problem"\s*:)',
            r'(\n\s*}\s*)\]\s*(\n\s*)\],(\s*\n\s*"problem"\s*:)',
        ):
            repaired = re.sub(pattern, r'\1}\2],\3', json_text, count=1)
            if repaired != json_text and repaired not in repairs:
                repairs.append(repaired)

        return repairs

    async def invoke_structured_with_repair(self,
                                            *,
                                            output_model: Type[T],
                                            messages: list[PromptMessage],
                                            data: dict[str, Any],
                                            repair_instruction: str,
                                            run_name: str,
                                            max_attempts: int = 3,
                                            ) -> T:
        last_error: Exception | None = None
        last_raw: Any = None

        # Route the schema guide through the same PromptMessage/_compose_messages pipeline (rather
        # than appending a raw HumanMessage afterward) so it still passes through adjacent-user
        # merging like the rest of the prompt, instead of leaving two consecutive user turns.
        messages_with_schema_guidance = [
            *messages,
            PromptMessage(
                role=MessageRole.USER,
                content=self._schema_guidance_text(output_model),
            ),
        ]
        base_messages = self._compose_messages(messages_with_schema_guidance, data=data)
        current_messages = base_messages

        for attempt in range(max_attempts):
            structured_model = self.model.with_structured_output(
                output_model,
                method="json_schema",
                include_raw=True,
            )

            try:
                response = await structured_model.ainvoke(
                    current_messages,
                    config={"run_name": f"{run_name}_attempt_{attempt + 1}"},
                )

                raw = response.get("raw")
                parsed = response.get("parsed")
                parsing_error = response.get("parsing_error")

                last_raw = raw

                if parsing_error is not None:
                    fallback_parsed = self._parse_raw_with_output_model(output_model, raw)
                    if fallback_parsed is not None:
                        return fallback_parsed
                    raise parsing_error

                if parsed is None:
                    fallback_parsed = self._parse_raw_with_output_model(output_model, raw)
                    if fallback_parsed is not None:
                        return fallback_parsed
                    raw_content = getattr(raw, "content", None)
                    raise ValueError(
                        f"Structured output parsed=None. Raw content: {raw_content!r}"
                    )

                return cast(output_model, parsed)

            except Exception as exc:
                last_error = exc
                raw_content = getattr(last_raw, "content", None)

                current_messages = [
                    *base_messages,
                    HumanMessage(
                        content=(
                            f"{repair_instruction}\n\n"
                            f"The previous structured-output attempt failed.\n"
                            f"Error type: {type(exc).__name__}\n"
                            f"Error message: {self._truncate_for_repair(exc, self._REPAIR_ERROR_LIMIT)}\n"
                            f"Raw content excerpt: {self._truncate_for_repair(raw_content, self._REPAIR_RAW_LIMIT)}\n\n"
                            "Return the required structured output only. "
                            "Do not return prose. Do not return an empty response."
                        )
                    ),
                ]

        raw_content = getattr(last_raw, "content", None)
        raise RuntimeError(
            f"{run_name} failed after {max_attempts} attempts. "
            f"Last error: {type(last_error).__name__ if last_error else None}: {last_error}. "
            f"Last raw content: {raw_content!r}"
        )

    async def invoke_text(self,
                          *,
                          messages: list[PromptMessage],
                          data: dict[str, Any],
                          run_name: str,
                          ) -> str:
        response = await self.model.ainvoke(
            self._compose_messages(messages, data=data),
            config={"run_name": run_name},
        )
        content = getattr(response, "content", response)

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))

            return "".join(text_parts)

        return str(content)
