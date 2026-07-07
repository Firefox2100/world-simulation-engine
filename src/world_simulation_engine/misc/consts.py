import json
import importlib.resources
from pathlib import Path
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from .enums import SupportedLanguage


class Prompts(TypedDict):
    action_proposal: list[dict]


def _load_builtin_prompt(language: str, name: str) -> list[dict]:
    file_path = importlib.resources.files("world_simulation_engine.data.prompts") / language / f"{name}.json"

    with open(str(file_path), "r") as f:
        return json.load(f)


def _load_override_prompt(language: str, name: str) -> list[dict] | None:
    from .config import CONFIG

    data_path = Path(CONFIG.data_folder) / "prompts" / language / f"{name}.json"
    if data_path.is_file():
        with open(str(data_path), "r") as f:
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
        result[language] = Prompts(
            action_proposal=_load_prompt(language.value, "action_proposal")
        )

    return result


PROMPTS = load_prompt()
