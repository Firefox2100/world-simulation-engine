from typing import Any, Sequence, Callable
from langchain_core.language_models import FakeMessagesListChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda, Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel


class FakeStructuredListChatModel(FakeMessagesListChatModel):
    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        def invoke(_input):
            result = self.invoke(_input)
            if isinstance(result, schema):
                output = result
            else:
                output = schema.model_validate_json(result.content)

            if include_raw:
                return {
                    "raw": output.model_dump_json(),
                    "parsed": output,
                }

            return output

        return RunnableLambda(invoke)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        def invoke(_input: LanguageModelInput) -> AIMessage:
            result = self.invoke(_input)

            if isinstance(result, AIMessage):
                return result

            if isinstance(result, BaseMessage):
                return AIMessage(
                    content=result.content,
                    additional_kwargs=result.additional_kwargs,
                    response_metadata=result.response_metadata,
                )

            if isinstance(result, dict):
                return AIMessage(**result)

            return AIMessage(content=str(result))

        return RunnableLambda(invoke)
