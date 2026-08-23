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
    TRIGGER_EVALUATOR = "trigger_evaluator"
    CHARACTER_IMAGE_GENERATOR = "character_image_generator"
    CHARACTER_PORTRAIT_IMAGE_GENERATOR = "character_portrait_image_generator"
    LOCATION_IMAGE_GENERATOR = "location_image_generator"
    ITEM_IMAGE_GENERATOR = "item_image_generator"
    SCENE_IMAGE_GENERATOR = "scene_image_generator"
    TURN_IMAGE_TRIGGER = "turn_image_trigger"
    NARRATOR_TTS = "narrator_tts"
    ST_LOREBOOK_CLASSIFIER = "st_lorebook_classifier"
    ST_CHARACTER_EXTRACTOR = "st_character_extractor"
    ST_BACKGROUND_CHARACTER_EXTRACTOR = "st_background_character_extractor"
    ST_LOCATION_EXTRACTOR = "st_location_extractor"
    ST_WORLD_LORE_EXTRACTOR = "st_world_lore_extractor"
    ST_NARRATIVE_EXTRACTOR = "st_narrative_extractor"
    ST_INTENT_EXTRACTOR = "st_intent_extractor"
    ST_VARIABLE_SCHEMA_EXTRACTOR = "st_variable_schema_extractor"
    ST_ITEM_EXTRACTOR = "st_item_extractor"
    ST_EQUIPMENT_EXTRACTOR = "st_equipment_extractor"
    ST_OPENING_TURN_EXTRACTOR = "st_opening_turn_extractor"
    ST_SPATIAL_STATE_EXTRACTOR = "st_spatial_state_extractor"
    ST_PRIVATE_KNOWLEDGE_EXTRACTOR = "st_private_knowledge_extractor"
    ST_OPENING_NARRATIVE_EXTRACTOR = "st_opening_narrative_extractor"


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


class TriggerConditionType(StrEnum):
    """One node in a Trigger's condition tree. LOCATION/VARIABLE are level predicates evaluated
    against current DB state; ALL_OF/ANY_OF/NOT combine them; SEMANTIC is free text judged by the
    trigger_evaluator LLM component instead of code. A single trigger's condition tree is either
    entirely deterministic (LOCATION/VARIABLE/ALL_OF/ANY_OF/NOT) or a single SEMANTIC leaf, never
    mixed - see TriggerEngine for why."""
    LOCATION = "location"        # a character is currently present in a location/landmark
    VARIABLE = "variable"        # an entity's tracked variable currently satisfies a comparison
    TIME = "time"                 # the simulation clock currently satisfies a comparison
    SEMANTIC = "semantic"        # free-text condition judged by an LLM against recent narration/memories
    ALL_OF = "all_of"
    ANY_OF = "any_of"
    NOT = "not"


class SemanticConditionMode(StrEnum):
    """How the trigger_evaluator should judge a SemanticCondition.statement."""
    FACT = "fact"        # has this specific thing become objectively true right now
    PACING = "pacing"     # given the recent story trend, would surfacing this feel natural now -
                          # not "is it true", but "is this the moment" (long-running script beats)


class ComparisonOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"


class TriggerEffectKind(StrEnum):
    EVENT = "event"    # "will happen" / "may happen": fires once on the condition's rising edge
    GATE = "gate"       # "is allowed to happen": tracks open/closed as a standing permission state


class TriggerEffectType(StrEnum):
    NARRATIVE_BEAT = "narrative_beat"    # queued as a must-include beat for the next narration
    FORCED_ACTION = "forced_action"      # queued as a forced next action for a specific character
    STATE_MUTATION = "state_mutation"    # applied immediately as StateCommitOperations
    PERCEIVED_CUE = "perceived_cue"      # queued as ambient, non-forcing information one or more
                                          # characters may notice via PerspectiveResolver - never
                                          # narrated directly, never a command; the character's own
                                          # proposal decides whether/how to act on it, if at all


class TriggerStatus(StrEnum):
    DORMANT = "dormant"      # condition not currently satisfied (event: not yet fired; gate: closed)
    ACTIVE = "active"        # gate: currently open. Not used by EVENT-kind triggers.
    CONSUMED = "consumed"    # event: fired and not repeatable - will never fire again
    DISABLED = "disabled"    # manually turned off, excluded from evaluation entirely


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
    TRIGGER = "trigger"


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
    ITEM = "item"
    PACING_INSTRUCTION = "pacing_instruction"
    HIDDEN_TRUTH = "hidden_truth"
    VARIABLE_META = "variable_meta"
    IRRELEVANT = "irrelevant"
