from enum import StrEnum


class CommitPolicy(StrEnum):
    COMMIT_IF_DISCOVERED = "commit_if_discovered"
    COMMIT_IF_SUCCEEDED = "commit_if_succeeded"
    COMMIT_HIDDEN_IF_NEEDED = "commit_hidden_if_needed"
    RESOLVER_DECIDES = "resolver_decides"


class EquipmentStatus(StrEnum):
    EQUIPPED = "equipped"
    IDLE = "idle"


class FactionRelationshipEntity(StrEnum):
    FACTION = "faction"
    ITEM = "item"
    CHARACTER = "character"


class ImageGenerationProvider(StrEnum):
    COMFY_UI = "comfy_ui"


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


class SandboxObjectType(StrEnum):
    SIMULATION = "simulation"
    STATE = "state"
    CHARACTER = "character"
    LOCATION = "location"
    ENTITY = "entity"
    ITEM = "item"
    EQUIPMENT = "equipment"
    INVENTORY = "inventory"
    TASK = "task"
    WORLD_ENTRY = "world_entry"
    FACTION = "faction"
    FACTION_RELATIONSHIP = "faction_relationship"
    PENDING_GENERATED_PROPOSAL = "pending_generated_proposal"


class SystemMessagePolicy(StrEnum):
    PRESERVE = "preserve"
    MERGE_TO_TOP = "merge_to_top"
    DROP = "drop"


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


class TurnType(StrEnum):
    USER_INPUT = "user_input"
    AI_RESPONSE = "ai_response"
    AI_CONTINUE = "ai_continue"
    AI_WAIT = "ai_wait"


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


class WorldSourceType(StrEnum):
    SILLY_TAVERN = "silly_tavern"
    WORLD_SIMULATION_ENGINE_V1 = "world_simulation_engine_v1"
