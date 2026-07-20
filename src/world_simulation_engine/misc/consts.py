import json
import importlib.resources
from pathlib import Path
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from .enums import SupportedLanguage


class Prompts(TypedDict, total=False):
    action_proposal: list[dict]
    action_reaction: list[dict]
    action_validator: list[dict]
    input_interpreter: list[dict]
    memory_summarizer: list[dict]
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

    prompt_names = [
        "action_proposal",
        "action_reaction",
        "action_validator",
        "input_interpreter",
        "memory_summarizer",
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

    result = {}
    for language in SupportedLanguage:
        result[language] = Prompts()
        for prompt_name in prompt_names:
            try:
                result[language][prompt_name] = _load_prompt(language.value, prompt_name)
            except FileNotFoundError:
                pass

    return result


PROMPTS = load_prompt()
