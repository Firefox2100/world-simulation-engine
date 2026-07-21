import json
import importlib.resources
from pathlib import Path
from typing import Any, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from .enums import SupportedLanguage


class Prompts(TypedDict, total=False):
    action_proposal: list[dict]
    action_reaction: list[dict]
    action_validator: list[dict]
    input_interpreter: list[dict]
    memory_summarizer: list[dict]
    relationship_updater: list[dict]
    narrator: list[dict]
    scene_coordinator: list[dict]
    speech_repair: list[dict]
    state_committer: list[dict]
    resolve_perceived_character: list[dict]
    resolve_perceived_background_characters: list[dict]
    resolve_perceived_items: list[dict]
    resolve_perceived_equipment: list[dict]
    resolve_perceived_containers: list[dict]
    resolve_perceived_landmarks: list[dict]


class Workflows(TypedDict, total=False):
    character: dict[str, Any]


PROMPT_NAMES = [
    "action_proposal",
    "action_reaction",
    "action_validator",
    "input_interpreter",
    "memory_summarizer",
    "relationship_updater",
    "narrator",
    "scene_coordinator",
    "speech_repair",
    "state_committer",
    "resolve_perceived_character",
    "resolve_perceived_background_characters",
    "resolve_perceived_items",
    "resolve_perceived_equipment",
    "resolve_perceived_containers",
    "resolve_perceived_landmarks",
]


WORKFLOW_NAMES = [
    "character",
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
