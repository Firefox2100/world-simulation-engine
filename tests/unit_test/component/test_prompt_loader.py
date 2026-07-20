import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from world_simulation_engine.component.prompt_loader import PromptLoader
from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import PromptMediaFile, PromptMessage


async def test_load_prompt_uses_simulation_or_world_override_media():
    override = [
        {"role": "system", "content": "Configured override"},
        {"role": "user", "content": "{{ user_input }}"},
    ]
    media = PromptMediaFile(
        id="prompt_1",
        title="Override",
        hash="a" * 64,
        filename="input_interpreter",
        prompt_name="input_interpreter",
        language=SupportedLanguage.ENGLISH,
    )
    database = SimpleNamespace(
        media=SimpleNamespace(get_prompt_media=AsyncMock(return_value=media)),
    )
    storage = SimpleNamespace(
        get_bytes=AsyncMock(return_value=json.dumps(override).encode("utf-8")),
    )

    result = await PromptLoader(database=database, storage=storage).load_prompt(
        simulation_id="simulation_1",
        language=SupportedLanguage.ENGLISH,
        prompt_name="input_interpreter",
    )

    assert result == [PromptMessage.model_validate(message) for message in override]
    database.media.get_prompt_media.assert_awaited_once_with(
        simulation_id="simulation_1",
        language=SupportedLanguage.ENGLISH,
        prompt_name="input_interpreter",
    )
    storage.get_bytes.assert_awaited_once_with(media.hash)


async def test_load_prompt_falls_back_to_builtin_when_no_override_exists():
    database = SimpleNamespace(
        media=SimpleNamespace(get_prompt_media=AsyncMock(return_value=None)),
    )
    storage = SimpleNamespace(get_bytes=AsyncMock())

    result = await PromptLoader(database=database, storage=storage).load_prompt(
        simulation_id="simulation_1",
        language=SupportedLanguage.ENGLISH,
        prompt_name="input_interpreter",
    )

    assert result == [
        PromptMessage.model_validate(message)
        for message in PROMPTS[SupportedLanguage.ENGLISH]["input_interpreter"]
    ]
    storage.get_bytes.assert_not_awaited()
