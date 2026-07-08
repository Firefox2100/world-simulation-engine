from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage, ComponentType
from world_simulation_engine.model import PromptMessage
from world_simulation_engine.service import DatabaseService, LlmService


class SimulatorComponent:
    COMPONENT_TYPE: ComponentType = None

    def __init__(self,
                 database: DatabaseService,
                 ):
        self._db = database

    @staticmethod
    def _prepare_prompt(language: SupportedLanguage,
                        prompt_name: str,
                        ) -> list[PromptMessage]:
        prompt_data = PROMPTS[language][prompt_name]
        prompt = [PromptMessage.model_validate(p) for p in prompt_data]

        return prompt

    async def _prepare_llm_service(self,
                                   simulation_id: str,
                                   ) -> LlmService:
        chat_config = await self._db.config.get_chat_by_source(
            source_id=simulation_id,
            component=self.COMPONENT_TYPE,
        )
        if not chat_config:
            raise ValueError(
                f"Simulation {simulation_id} does not have a chat model configured for character simulation"
            )

        connection_config = await self._db.config.get_connection_by_source(
            source_id=chat_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Chat model config {chat_config.id} does not have a connection configured"
            )

        llm = LlmService(
            model_config=chat_config,
            connection_config=connection_config,
        )

        return llm
