import inspect

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import SupportedLanguage, ComponentType, MessageRole
from world_simulation_engine.misc.placeholder import PlaceholderContext, render_placeholders
from world_simulation_engine.model import EmotionVector, PromptMessage, Simulation, SubjectiveEntityClaim
from world_simulation_engine.service import DatabaseService, EmbedService, LlmService
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

    async def _prepare_embed_service(self, simulation_id: str) -> EmbedService:
        embed_config = await self._db.config.get_embed_by_source(
            source_id=simulation_id,
            component=self.COMPONENT_TYPE,
        )
        if not embed_config:
            raise ValueError(
                f"Simulation {simulation_id} does not have an embedding model configured for "
                f"{self.COMPONENT_TYPE}"
            )
        connection_config = await self._db.config.get_connection_by_embed_source(
            source_id=embed_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Embedding config {embed_config.id} does not have a connection configured"
            )
        return EmbedService(
            model_config=embed_config,
            connection_config=connection_config,
        )

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
Use each actor's emotion only for that actor's risk, interruption, intent urgency, and tone. Let high arousal or negative valence surface as physical tension, clipped phrasing, guarded posture, or abrupt movement; let calm or positive states surface as looser, slower, more open description. Do not default to calm or neutral framing when the emotion values indicate otherwise. Never disclose one actor's private emotion to another."""
        else:
            content = f"""## Private emotion constraint

{{% if {expression} %}}- valence {{{{ {expression}.valence }}}}; arousal {{{{ {expression}.arousal }}}}; dominance {{{{ {expression}.dominance }}}}; extensions {{{{ {expression}.dimensions }}}}
Use this as a soft constraint for risk tolerance, interruption, intent urgency, and tone. Let high arousal or negative valence surface as tension, clipped phrasing, or abrupt action; let calm or positive states surface as looser, slower phrasing. Do not default to calm or neutral framing when the emotion values indicate otherwise. Do not state numeric values or expose private emotion.
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

    async def _unconsumed_trigger_activations(self, *, simulation_id: str, effect_type) -> list:
        """Compatibility-safe lookup for tests and older database adapters (see _subjective_claims)."""
        store = getattr(self._db, "trigger", None)
        method = getattr(store, "list_unconsumed_activations", None)
        if not inspect.iscoroutinefunction(method):
            return []
        return await method(simulation_id=simulation_id, effect_type=effect_type)

    async def _mark_trigger_activations_consumed(self, activation_ids: list[str]) -> None:
        if not activation_ids:
            return
        store = getattr(self._db, "trigger", None)
        method = getattr(store, "mark_activations_consumed", None)
        if not inspect.iscoroutinefunction(method):
            return
        await method(activation_ids)

    @staticmethod
    def _with_trigger_context(prompt: list[PromptMessage]) -> list[PromptMessage]:
        """Append fired trigger beats as must-include narration content.

        Callers must only invoke this when `trigger_beats` is non-empty - unlike the emotion/
        relationship/subjective-claim helpers above (always appended, with an inline empty-case
        fallback), this one is never called at all when there is nothing to inject, so a dormant
        trigger's mere existence never appears in the prompt even as an empty section header.
        """
        content = """## Must-include story beats

{% for beat in trigger_beats %}
- {{ beat }}
{% endfor %}

Weave every must-include beat above into this narration naturally, in your own words - do not quote it verbatim or explain why it is happening now."""
        return [*prompt, PromptMessage(role=MessageRole.USER, content=content)]

    @staticmethod
    def _with_forced_action_context(prompt: list[PromptMessage]) -> list[PromptMessage]:
        """Same "only append when there is something to inject" contract as
        `_with_trigger_context` above - never called when there is no forced directive."""
        content = """## Forced action this turn

{% for directive in trigger_forced_directives %}
- {{ directive }}
{% endfor %}

Propose actions that carry out every forced directive above, in character and in your own words - do not ignore, delay, or contradict it."""
        return [*prompt, PromptMessage(role=MessageRole.USER, content=content)]

    @staticmethod
    def _placeholder_context(**named_entities) -> PlaceholderContext:
        """Build a placeholder roster from already-fetched entities, grouped by keyword.

        Each keyword must be one of `PlaceholderContext`'s groups (character, location, item, ...)
        and its value an iterable of objects with `.id`/`.name`, e.g.
        `_placeholder_context(character=[actor, *perceived_characters], location=[location])`.
        """
        context = PlaceholderContext()
        for group, entities in named_entities.items():
            for entity in entities:
                context.add(group, id=entity.id, name=entity.name)
        return context

    @staticmethod
    def _render_placeholders(text: str, context: PlaceholderContext) -> str:
        """Resolve `{{ character['id'].name }}`-style references against `context`.

        Lazy by design: stored text keeps its raw placeholder syntax forever, so renaming an
        entity after import - or at any point - is reflected the next time this is called, rather
        than requiring every reference to be rewritten.
        """
        return render_placeholders(text, context)
