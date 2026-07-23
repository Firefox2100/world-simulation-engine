import inspect

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage, ComponentType, MessageRole
from world_simulation_engine.model import EmotionVector, PromptMessage, Simulation, SubjectiveEntityClaim
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

    async def _effective_emotion(
            self,
            *,
            simulation: Simulation,
            character_id: str,
    ) -> EmotionVector | None:
        """Return private emotion at simulation time without persisting read-time decay."""
        if not simulation.emotion_enabled:
            return None
        emotion_store = getattr(self._db, "emotion", None)
        get_state = getattr(emotion_store, "get_state", None)
        if not inspect.iscoroutinefunction(get_state):
            return EmotionVector()
        state = await get_state(
            simulation_id=simulation.id,
            character_id=character_id,
        )
        if not state:
            return EmotionVector()
        return emotion_store.combined_vector(
            emotion_store.decay_state(state, simulation.current_time),
        )

    @staticmethod
    def _with_emotion_context(
            prompt: list[PromptMessage],
            *,
            expression: str = "emotion",
            actors: bool = False,
            actor_key: str = "actor",
    ) -> list[PromptMessage]:
        """Append a compact numeric state without expanding existing output schemas."""
        if actors:
            content = f"""## Private emotion constraints by actor

{{% for entry in actors %}}
{{% if entry.emotion %}}- {{{{ entry.{actor_key}.name }}}} ({{{{ entry.{actor_key}.id }}}}): valence {{{{ entry.emotion.valence }}}}, arousal {{{{ entry.emotion.arousal }}}}, dominance {{{{ entry.emotion.dominance }}}}, extensions {{{{ entry.emotion.dimensions }}}}
{{% endif %}}{{% endfor %}}
Use each actor's emotion only for that actor's risk, interruption, intent urgency, and tone. Never disclose one actor's private emotion to another."""
        else:
            content = f"""## Private emotion constraint

{{% if {expression} %}}- valence {{{{ {expression}.valence }}}}; arousal {{{{ {expression}.arousal }}}}; dominance {{{{ {expression}.dominance }}}}; extensions {{{{ {expression}.dimensions }}}}
Use this as a soft constraint for risk tolerance, interruption, intent urgency, and tone. Do not state numeric values or expose private emotion.
{{% else %}}- disabled
{{% endif %}}"""
        return [*prompt, PromptMessage(role=MessageRole.USER, content=content)]

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

    async def _subjective_claims(self, *, simulation_id: str, observer_character_id: str,
                                 subject_ids: list[str]) -> list[SubjectiveEntityClaim]:
        """Compatibility-safe observer-scoped recall for tests and older database adapters."""
        store = getattr(self._db, "subjective_entity_claim", None)
        method = getattr(store, "list_claims", None)
        if not inspect.iscoroutinefunction(method):
            return []
        return await method(simulation_id=simulation_id, observer_character_id=observer_character_id,
                            subject_ids=subject_ids, limit=24)

    @staticmethod
    def _with_subjective_claim_context(prompt: list[PromptMessage], *, nested_under_perspective: bool = False,
                                       nested_under_actors: bool = False) -> list[PromptMessage]:
        if nested_under_actors:
            content = """## Private entity models by actor
{% for actor_context in actors %}{% for claim in actor_context.subjective_claims %}
- {{ actor_context.actor.name }} privately {{ claim.stance }} about {{ claim.subject.name or claim.subject.id }}: [{{ claim.category }}] {{ claim.statement }} (confidence {{ claim.confidence }})
{% endfor %}{% endfor %}
Use each claim only for its observer. A belief is not objective fact and must not leak to another actor."""
        else:
            prefix = "perspective." if nested_under_perspective else ""
            content = f"""## Actor's private models of entities
{{% for claim in {prefix}subjective_claims %}}
- {{{{ claim.stance }}}} about {{{{ claim.subject.name or claim.subject.id }}}}: [{{{{ claim.category }}}}] {{{{ claim.statement }}}} (confidence {{{{ claim.confidence }}}})
{{% endfor %}}
Treat these as this actor's fallible beliefs, never as objective facts or another actor's knowledge."""
        return [*prompt, PromptMessage(role=MessageRole.USER, content=content)]
