from enum import StrEnum


class EquipmentStatus(StrEnum):
    EQUIPPED = "equipped"
    IDLE = "idle"


class FactionRelationshipEntity(StrEnum):
    FACTION = "faction"
    ITEM = "item"
    CHARACTER = "character"


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


class TaskPriority(StrEnum):
    URGENT = "urgent"
    IMPORTANT = "important"
    NORMAL = "normal"
    BACKGROUND = "background"


class TaskStatus(StrEnum):
    PAUSED = "paused"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class TaskType(StrEnum):
    MAIN_QUEST = "main_quest"
    SIDE_QUEST = "side_quest"
    DAILY = "daily"


class WorldEntryRecallType(StrEnum):
    ALWAYS = "always"
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    CHAINED = "chained"


class WorldEntryVisibility(StrEnum):
    KNOWN = "known"
    SUSPECTED = "suspected"
    PERCEIVED = "perceived"
    INFERRED = "inferred"
