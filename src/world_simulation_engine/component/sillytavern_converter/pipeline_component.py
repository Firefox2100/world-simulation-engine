"""Shared base for LLM-driven SillyTavern import pipeline stages.

These stages run before any World exists, so - unlike `SimulatorComponent`'s per-world/per-
simulation config lookup - they use a flat "global" chat config, mirroring the approach this
codebase already established for STT (`ConfigStore.get_global_stt`/`get_global_chat`): no
World/Simulation-like scope node, just the one chat config configured for this component, looked
up directly. See SILLYTAVERN_IMPORT_PLAN.md §6.

Prompt loading has no equivalent "global override" mechanism yet (STT has no prompt concept to
draw a precedent from) - these components always use the built-in default prompt for their
language, the same one exercised in evaluation testing.
"""

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import PromptMessage
from world_simulation_engine.service import LlmService

from ..simulator.simulator_component import SimulatorComponent


class SillyTavernPipelineComponent(SimulatorComponent):
    """`SimulatorComponent` minus the per-world config/prompt lookups, plus global chat lookup.

    Deliberately does not override `_prepare_llm_service`/`_prepare_prompt` (different signature -
    no source/simulation id) so callers can't accidentally invoke the per-world path expecting it
    to do something different here; use `_prepare_global_llm_service`/`_prepare_global_prompt`.
    """

    async def _prepare_global_llm_service(self) -> LlmService:
        chat_config = await self._db.config.get_global_chat(self.COMPONENT_TYPE)
        if not chat_config:
            raise ValueError(
                f"No global chat model is configured for {self.COMPONENT_TYPE}. Configure one with "
                "db.config.link_global_chat(chat_config_id, component)."
            )

        connection_config = await self._db.config.get_connection_by_source(source_id=chat_config.id)
        if not connection_config:
            raise ValueError(
                f"Chat model config {chat_config.id} does not have a connection configured"
            )

        return LlmService(
            model_config=chat_config,
            connection_config=connection_config,
        )

    @staticmethod
    async def _prepare_global_prompt(
            *,
            language: SupportedLanguage,
            prompt_name: str,
    ) -> list[PromptMessage]:
        prompt_data = PROMPTS[language][prompt_name]
        return [PromptMessage.model_validate(p) for p in prompt_data]
