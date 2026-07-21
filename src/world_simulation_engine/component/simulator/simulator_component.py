from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage, ComponentType, MessageRole
from world_simulation_engine.model import PromptMessage
from world_simulation_engine.service import DatabaseService, LlmService
from ..prompt_loader import PromptLoader


class SimulatorComponent:
    COMPONENT_TYPE: ComponentType = None

    def __init__(self,
                 database: DatabaseService,
                 prompt_loader: PromptLoader | None = None,
                 ):
        self._db = database
        self._prompt_loader = prompt_loader

    async def _prepare_prompt(self,
                              *,
                              simulation_id: str,
                              language: SupportedLanguage,
                              prompt_name: str,
                              ) -> list[PromptMessage]:
        if self._prompt_loader:
            return await self._prompt_loader.load_prompt(
                simulation_id=simulation_id,
                language=language,
                prompt_name=prompt_name,
            )

        prompt_data = PROMPTS[language][prompt_name]
        return [PromptMessage.model_validate(p) for p in prompt_data]

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

    @staticmethod
    def _with_relationship_context(
            prompt: list[PromptMessage],
            *,
            nested_under_perspective: bool = False,
            nested_under_actors: bool = False,
    ) -> list[PromptMessage]:
        if nested_under_actors:
            content = """## Scoped entity relationships by actor

{% for actor_context in actors %}
Actor {{ actor_context.actor.id }}:
{% for entry in actor_context.relationships %}
- {{ entry.source.name or entry.source.id }} ({{ entry.source.id }}) --{{ entry.label }}--> {{ entry.target.name or entry.target.id }} ({{ entry.target.id }}); confidence: {{ entry.confidence }}; details: {{ entry.details }}{% if entry.public_description %}; public: {{ entry.public_description }}{% endif %}{% if entry.private_description %}; private to this actor: {{ entry.private_description }}{% endif %}
{% else %}
- none
{% endfor %}
{% else %}
- none
{% endfor %}

Use objective compatibility/spatial facts as constraints. Use private records only for the actor section containing them."""
        else:
            prefix = "perspective." if nested_under_perspective else ""
            content = f"""## Known entity relationships

{{% for entry in {prefix}relationships %}}
- {{{{ entry.source.name or entry.source.id }}}} ({{{{ entry.source.id }}}}) --{{{{ entry.label }}}}--> {{{{ entry.target.name or entry.target.id }}}} ({{{{ entry.target.id }}}}); confidence: {{{{ entry.confidence }}}}; details: {{{{ entry.details }}}}{{% if entry.public_description %}}; public: {{{{ entry.public_description }}}}{{% endif %}}{{% if entry.private_description %}}; private interpretation: {{{{ entry.private_description }}}}{{% endif %}}
{{% else %}}
- none
{{% endfor %}}

Treat objective compatibility/spatial facts as constraints and subjective records as this actor's beliefs. Do not invent missing relationships."""
        return [
            *prompt,
            PromptMessage(role=MessageRole.USER, content=content),
        ]
