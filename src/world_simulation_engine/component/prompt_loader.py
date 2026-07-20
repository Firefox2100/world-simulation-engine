import json

from pydantic import TypeAdapter

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import PromptMessage
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.storage_service import StorageService


class PromptLoader:
    _PROMPT_ADAPTER = TypeAdapter(list[PromptMessage])

    def __init__(self,
                 database: DatabaseService,
                 storage: StorageService,
                 ):
        self._db = database
        self._storage = storage

    async def load_prompt(self,
                          *,
                          simulation_id: str,
                          language: SupportedLanguage,
                          prompt_name: str,
                          ) -> list[PromptMessage]:
        media = await self._db.media.get_prompt_media(
            simulation_id=simulation_id,
            language=language,
            prompt_name=prompt_name,
        )
        if media:
            content = await self._storage.get_bytes(media.hash)
            prompt_data = json.loads(content.decode("utf-8"))
        else:
            prompt_data = PROMPTS[language][prompt_name]

        return self._PROMPT_ADAPTER.validate_python(prompt_data)
