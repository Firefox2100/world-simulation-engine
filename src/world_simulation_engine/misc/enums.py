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
    ACTION_SUGGESTER = "action_suggester"
    ACTION_VALIDATOR = "action_validator"
    CHARACTER_SIMULATOR = "character_simulator"
    INPUT_INTERPRETER = "input_interpreter"
    MEMORY_SUMMARIZER = "memory_summarizer"
    NARRATOR = "narrator"
    OOC_HANDLER = "ooc_handler"
    PERSPECTIVE_RESOLVER = "perspective_resolver"
    SCENE_COORDINATOR = "scene_coordinator"
    STATE_COMMITTER = "state_committer"
    CHARACTER_IMAGE_GENERATOR = "character_image_generator"
    CHARACTER_PORTRAIT_IMAGE_GENERATOR = "character_portrait_image_generator"
    LOCATION_IMAGE_GENERATOR = "location_image_generator"
    ITEM_IMAGE_GENERATOR = "item_image_generator"
    SCENE_IMAGE_GENERATOR = "scene_image_generator"
    TURN_IMAGE_TRIGGER = "turn_image_trigger"
    NARRATOR_TTS = "narrator_tts"
    ST_LOREBOOK_CLASSIFIER = "st_lorebook_classifier"
    ST_CHARACTER_EXTRACTOR = "st_character_extractor"
    ST_LOCATION_EXTRACTOR = "st_location_extractor"
    ST_WORLD_LORE_EXTRACTOR = "st_world_lore_extractor"
    ST_NARRATIVE_EXTRACTOR = "st_narrative_extractor"
    ST_INTENT_EXTRACTOR = "st_intent_extractor"
    ST_VARIABLE_SCHEMA_EXTRACTOR = "st_variable_schema_extractor"


class ConnectionType(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GOOGLE_GENAI = "google_genai"
    MISTRALAI = "mistralai"
    COHERE = "cohere"
    PERPLEXITY = "perplexity"
    GROQ = "groq"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    CLOUDFLARE = "cloudflare"
    COMFYUI = "comfyui"
    ALLTALK = "alltalk"
    WHISPERCPP = "whispercpp"


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


class SceneCoordinationProblemType(StrEnum):
    EXCLUSIVE_RESOURCE = "exclusive_resource"
    INTERRUPTION = "interruption"
    CONSENT_REQUIRED = "consent_required"
    REACTION_TRIGGER = "reaction_trigger"
    CONTESTED_ACTION = "contested_action"
    MUTUALLY_INCOMPATIBLE = "mutually_incompatible"
    REPEATED_REACTION = "repeated_reaction"
    OTHER = "other"


class SceneCoordinationStatus(StrEnum):
    COMPLETE = "complete"
    PROBLEM = "problem"
    STOPPED = "stopped"


class ImageGenerationType(StrEnum):
    STATE = "state"
    CHARACTER_PORTRAIT = "character_portrait"
    SCENE = "scene"


class ImageGenerationMode(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"
    ALWAYS = "always"


class TtsGenerationMode(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"


class TtsEngine(StrEnum):
    XTTS = "xtts"
    PIPER = "piper"
    VITS = "vits"
    PARLER = "parler"
    F5TTS = "f5tts"


class TtsTextFilteringMode(StrEnum):
    NONE = "none"
    STANDARD = "standard"
    HTML = "html"


class TtsTextNotInsideMode(StrEnum):
    CHARACTER = "character"
    NARRATOR = "narrator"
    SILENT = "silent"


class MediaType(StrEnum):
    PNG = "image/png"
    JSON = "application/json"
    WAV = "audio/wav"


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


class GraphStateSnapshotType(StrEnum):
    BEFORE_USER_INPUT = "before_user_input"
    AFTER_USER_INPUT = "after_user_input"
    AFTER_CHARACTER_ROUND = "after_character_round"


class GenerationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationAuditCategory(StrEnum):
    GENERATION = "generation"
    SCHEDULER = "scheduler"
    RETRIEVAL = "retrieval"
    VALIDATION = "validation"
    COORDINATION = "coordination"
    COMMIT = "commit"
    TIME = "time"
    BACKGROUND = "background"
    ERROR = "error"


class SimulationAuditOrigin(StrEnum):
    CODE = "code"
    LLM_PROPOSAL = "llm_proposal"
    VALIDATION = "validation"
    COMMIT = "commit"
    BACKGROUND = "background"


class SimulationAuditStatus(StrEnum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    COMMITTED = "committed"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class SimulationGenerationRequestType(StrEnum):
    USER_INPUT_GENERATION = "user_input_generation"
    CONTINUE_GENERATION = "continue_generation"
    REGENERATION = "regeneration"


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


class LorebookItemBucket(StrEnum):
    """What one piece of SillyTavern card content (a top-level field or lorebook entry) is about,
    for routing to the right stage-2 extractor of the import pipeline."""
    CHARACTER_BIO = "character_bio"
    CHARACTER_VOICE = "character_voice"
    RELATIONSHIP = "relationship"
    HISTORY_EVENT = "history_event"
    WORLD_LORE = "world_lore"
    LOCATION = "location"
    PACING_INSTRUCTION = "pacing_instruction"
    HIDDEN_TRUTH = "hidden_truth"
    VARIABLE_META = "variable_meta"
    IRRELEVANT = "irrelevant"
