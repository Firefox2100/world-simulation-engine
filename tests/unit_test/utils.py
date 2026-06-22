from typing import Any
from langchain_core.language_models import FakeMessagesListChatModel, LanguageModelInput
from langchain_core.runnables import RunnableLambda, Runnable
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
                return result

            if hasattr(schema, "model_validate_json"):  # Pydantic v2
                return schema.model_validate_json(result.content)

            return result

        return RunnableLambda(invoke)
