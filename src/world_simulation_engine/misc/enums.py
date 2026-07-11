from enum import StrEnum


class ActionModality(StrEnum):
    PHYSICAL = "physical"
    VERBAL = "verbal"
    MENTAL_ATTENTION = "mental_attention"
    MIXED = "mixed"


class ActionType(StrEnum):
    SPEAK = "speak"
    MOVE = "move"
    CHANGE_POSTURE = "change_posture"
    LOOK = "look"
    OBSERVE = "observe"
    TOUCH = "touch"
    TAKE = "take"
    DROP = "drop"
    GIVE = "give"
    USE = "use"
    MANIPULATE = "manipulate"
    ATTACK = "attack"
    DEFEND = "defend"
    WAIT = "wait"
    CONTINUE_ACTIVITY = "continue_activity"
    STOP_ACTIVITY = "stop_activity"
    SOCIAL_SIGNAL = "social_signal"
    OTHER = "other"


class ComponentType(StrEnum):
    ACTION_VALIDATOR = "action_validator"
    CHARACTER_SIMULATOR = "character_simulator"
    INPUT_INTERPRETER = "input_interpreter"
    PERSPECTIVE_RESOLVER = "perspective_resolver"


class ConnectionType(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"


class ContainerState(StrEnum):
    HIDDEN = "hidden"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    OPEN = "open"


class IntentHorizon(StrEnum):
    IMMEDIATE = "immediate"
    SHORT = "short"
    DAY = "day"
    LONG = "long"
    OPEN_ENDED = "open_ended"


class IntentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class IntentType(StrEnum):
    NEED = "need"                   # hunger, safety, rest
    OBLIGATION = "obligation"       # promise, job, debt
    QUEST = "quest"                 # accepted explicit objective
    AGENDA = "agenda"               # personal scheme
    ASPIRATION = "aspiration"       # be a better painter
    RELATIONSHIP = "relationship"   # involving another character
    HABIT = "habit"                 # routine but not hard constraint, repetitive
    REACTION = "reaction"           # respond to an event


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class EventInvolvement(StrEnum):
    WITNESS = "witness"
    PARTICIPATE = "participate"
    HEAR = "hear"
    INFER = "infer"
    BELIEVE = "believe"
    SUSPECT = "suspect"


class MemoryStance(StrEnum):
    REMEMBER = "remember"
    INFER = "infer"
    BELIEVE = "believe"
    DOUBT = "doubt"
    DENY = "deny"
    MISTAKE = "mistake"


class MemorySupportType(StrEnum):
    DIRECT = "direct"
    INFERRED = "inferred"
    REPORTED = "reported"
    CONTRADICTS = "contradicts"


class Salience(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SupportedLanguage(StrEnum):
    CHINESE = "zh"
    ENGLISH = "en"


class SystemMessagePolicy(StrEnum):
    PRESERVE = "preserve"
    MERGE_TO_TOP = "merge_to_top"
    DROP = "drop"


class TurnType(StrEnum):
    USER_INPUT = "user_input"
    SYSTEM_RESPONSE = "system_response"
    SYSTEM_CONTINUE = "system_continue"


class Visibility(StrEnum):
    VISIBLE = "visible"
    AUDIBLE = "audible"
    INFERRED = "inferred"
    INVISIBLE = "invisible"
