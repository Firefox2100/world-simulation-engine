from enum import StrEnum


class ActionType(StrEnum):
    speak = "speak"
    move = "move"
    interact = "interact"
    wait = "wait"
    observe = "observe"
    use_item = "use_item"
    social_signal = "social_signal"
    refuse = "refuse"
    continue_activity = "continue_activity"
    stop_activity = "stop_activity"


class ComponentType(StrEnum):
    CHARACTER_SIMULATOR = "character_simulator"


class ConnectionType(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"


class ContainerState(StrEnum):
    HIDDEN = "hidden"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    OPEN = "open"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Salience(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SupportedLanguage(StrEnum):
    CHINESE = "zh"
    ENGLISH = "en"


class SystemMessagePolicy(StrEnum):
    PRESERVE = "preserve"
    MERGE_TO_TOP = "merge_to_top"
    DROP = "drop"


class Visibility(StrEnum):
    visible = "visible"
    audible = "audible"
    remembered = "remembered"
    inferred = "inferred"
