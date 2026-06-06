from enum import StrEnum


class LlmProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class NarrationPermission(StrEnum):
    VISIBLE = "visible"
    MAY_HINT = "may_hint"
    INVISIBLE = "invisible"


class WorldEntryVisibility(StrEnum):
    KNOWN = "known"
    SUSPECTED = "suspected"
    PERCEIVED = "perceived"
    INFERRED = "inferred"
