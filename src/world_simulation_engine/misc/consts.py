import json
import importlib.resources
from pathlib import Path
from typing import Any, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from .enums import SupportedLanguage


class Prompts(TypedDict, total=False):
    action_proposal: list[dict]
    action_reaction: list[dict]
    action_suggester: list[dict]
    action_validator: list[dict]
    image_prompt_builder: list[dict]
    image_transient_prompt_builder: list[dict]
    input_interpreter: list[dict]
    memory_summarizer: list[dict]
    emotion_updater: list[dict]
    relationship_updater: list[dict]
    subjective_model_updater: list[dict]
    variable_updater: list[dict]
    st_lorebook_classifier: list[dict]
    st_character_extractor: list[dict]
    st_location_extractor: list[dict]
    st_location_synthesizer: list[dict]
    st_world_lore_extractor: list[dict]
    st_narrative_event_extractor: list[dict]
    st_narrative_relationship_extractor: list[dict]
    st_intent_extractor: list[dict]
    st_variable_schema_extractor: list[dict]
    st_variable_initial_value_extractor: list[dict]
    st_item_extractor: list[dict]
    st_equipment_extractor: list[dict]
    st_equipment_initial_value_extractor: list[dict]
    narrator: list[dict]
    ooc_handler: list[dict]
    scene_coordinator: list[dict]
    speech_repair: list[dict]
    state_committer: list[dict]
    resolve_perceived_character: list[dict]
    resolve_perceived_background_characters: list[dict]
    resolve_perceived_items: list[dict]
    resolve_perceived_equipment: list[dict]
    resolve_perceived_containers: list[dict]
    resolve_perceived_landmarks: list[dict]
    turn_image_trigger: list[dict]


class Workflows(TypedDict, total=False):
    character: dict[str, Any]
    location: dict[str, Any]
    item: dict[str, Any]
    scene: dict[str, Any]


PROMPT_NAMES = [
    "action_proposal",
    "action_reaction",
    "action_suggester",
    "action_validator",
    "image_prompt_builder",
    "image_transient_prompt_builder",
    "input_interpreter",
    "memory_summarizer",
    "emotion_updater",
    "relationship_updater",
    "subjective_model_updater",
    "variable_updater",
    "st_lorebook_classifier",
    "st_character_extractor",
    "st_location_extractor",
    "st_location_synthesizer",
    "st_world_lore_extractor",
    "st_narrative_event_extractor",
    "st_narrative_relationship_extractor",
    "st_intent_extractor",
    "st_variable_schema_extractor",
    "st_variable_initial_value_extractor",
    "st_item_extractor",
    "st_equipment_extractor",
    "st_equipment_initial_value_extractor",
    "narrator",
    "ooc_handler",
    "scene_coordinator",
    "speech_repair",
    "state_committer",
    "resolve_perceived_character",
    "resolve_perceived_background_characters",
    "resolve_perceived_items",
    "resolve_perceived_equipment",
    "resolve_perceived_containers",
    "resolve_perceived_landmarks",
    "turn_image_trigger",
]


WORKFLOW_NAMES = [
    "character",
    "location",
    "item",
    "scene",
]


def _load_builtin_prompt(language: str, name: str) -> list[dict]:
    file_path = importlib.resources.files("world_simulation_engine.data.prompts") / language / f"{name}.json"

    with open(str(file_path), "r", encoding="utf-8") as f:
        return json.load(f)


def _load_override_prompt(language: str, name: str) -> list[dict] | None:
    from .config import CONFIG

    data_path = Path(CONFIG.data_folder) / "prompts" / language / f"{name}.json"
    if data_path.is_file():
        with open(str(data_path), "r", encoding="utf-8") as f:
            return json.load(f)

    return None


def _load_prompt(language: str, name: str) -> list[dict]:
    override_prompt = _load_override_prompt(language, name)

    if override_prompt is not None:
        return override_prompt

    return _load_builtin_prompt(language, name)


def load_prompt() -> dict["SupportedLanguage", Prompts]:
    from .enums import SupportedLanguage

    result = {}
    for language in SupportedLanguage:
        result[language] = Prompts()
        for prompt_name in PROMPT_NAMES:
            try:
                result[language][prompt_name] = _load_prompt(language.value, prompt_name)
            except FileNotFoundError:
                pass

    return result


def _load_builtin_workflow(name: str) -> dict[str, Any]:
    file_path = importlib.resources.files("world_simulation_engine.data.comfyui_workflows") / f"{name}.json"

    with open(str(file_path), "r", encoding="utf-8") as f:
        return json.load(f)


def _load_override_workflow(name: str) -> dict[str, Any] | None:
    from .config import CONFIG

    data_path = Path(CONFIG.data_folder) / "comfyui_workflows" / f"{name}.json"
    if data_path.is_file():
        with open(str(data_path), "r", encoding="utf-8") as f:
            return json.load(f)

    return None


def _load_workflow(name: str) -> dict[str, Any]:
    override_workflow = _load_override_workflow(name)

    if override_workflow is not None:
        return override_workflow

    return _load_builtin_workflow(name)


def load_workflow() -> Workflows:
    result = {}

    for workflow_name in WORKFLOW_NAMES:
        try:
            result[workflow_name] = _load_workflow(workflow_name)
        except FileNotFoundError:
            pass

    return result


PROMPTS = load_prompt()
WORKFLOWS = load_workflow()
