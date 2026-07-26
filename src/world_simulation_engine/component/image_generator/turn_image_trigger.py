from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import PROMPTS
from world_simulation_engine.misc.enums import ActionType, ComponentType, ImageGenerationMode, SupportedLanguage
from world_simulation_engine.misc.logging import log_event
from world_simulation_engine.model import ImageGenerationConfig, PromptMessage, ProposedAction, \
    SceneCoordinationResult, Turn, TurnImageSignificanceDecision
from world_simulation_engine.service import DatabaseService, LlmService, StorageService
from ..prompt_loader import PromptLoader
from ..workflow_loader import WorkflowLoader
from .scene_image_generator import SceneImageGenerator

_SIGNIFICANT_ACTION_TYPES = {
    ActionType.MOVE,
    ActionType.ATTACK,
    ActionType.DEFEND,
    ActionType.GIVE,
    ActionType.TAKE,
    ActionType.MANIPULATE,
    ActionType.USE,
    ActionType.CHANGE_POSTURE,
    ActionType.DROP,
    ActionType.TOUCH,
}
_INSIGNIFICANT_ACTION_TYPES = {
    ActionType.WAIT,
    ActionType.SPEAK,
    ActionType.OBSERVE,
    ActionType.LOOK,
    ActionType.CONTINUE_ACTIVITY,
    ActionType.SOCIAL_SIGNAL,
}


class TurnImageSignificanceContext(BaseModel):
    narration: str = ""
    action_summaries: list[str] = Field(default_factory=list)


def deterministic_turn_significance(actions: list[ProposedAction]) -> bool | None:
    """Classify a turn's accepted actions by type alone. Returns True/False when the action
    types are conclusive, or None when the LLM fallback check is needed."""
    if not actions:
        return False

    types = {action.type for action in actions}
    if types & _SIGNIFICANT_ACTION_TYPES:
        return True
    if types <= _INSIGNIFICANT_ACTION_TYPES:
        return False

    return None


class TurnImageTrigger:
    """Decides whether a completed turn's scene should be automatically illustrated, per the
    simulation's ImageGenerationConfig, then generates and links the image if so.

    manual: never triggers. always: triggers unconditionally. auto: a deterministic action-type
    check decides first; if inconclusive, a lightweight LLM call decides; if still no, a
    configurable per-simulation fallback forces a generation once too many turns have passed
    without one, so the world never goes indefinitely without a fresh image.
    """

    COMPONENT_TYPE = ComponentType.TURN_IMAGE_TRIGGER

    def __init__(self,
                 database: DatabaseService,
                 storage: StorageService | None = None,
                 workflow_loader: WorkflowLoader | None = None,
                 prompt_loader: PromptLoader | None = None,
                 ):
        self._db = database
        self._storage = storage
        self._workflow_loader = workflow_loader
        self._prompt_loader = prompt_loader

    async def _resolve_language(self, simulation_id: str) -> SupportedLanguage:
        world = await self._db.world.get_world_by_simulation(simulation_id)
        if not world:
            raise ValueError(f"World for simulation {simulation_id} not found")

        return world.language

    async def _prepare_prompt(self, *, source_id: str, language: SupportedLanguage) -> list[PromptMessage]:
        if self._prompt_loader:
            return await self._prompt_loader.load_prompt(
                simulation_id=source_id,
                language=language,
                prompt_name="turn_image_trigger",
            )

        prompt_data = PROMPTS[language]["turn_image_trigger"]
        return [PromptMessage.model_validate(p) for p in prompt_data]

    async def _prepare_llm_service(self, source_id: str) -> LlmService:
        chat_config = await self._db.config.get_chat_by_source(
            source_id=source_id,
            component=self.COMPONENT_TYPE,
        )
        if not chat_config:
            raise ValueError(
                f"Source {source_id} does not have a chat model configured for {self.COMPONENT_TYPE}"
            )

        connection_config = await self._db.config.get_connection_by_source(
            source_id=chat_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Chat model config {chat_config.id} does not have a connection configured"
            )

        return LlmService(
            model_config=chat_config,
            connection_config=connection_config,
        )

    async def _llm_significance(self, *, simulation_id: str, narration: str, actions: list[ProposedAction]) -> bool:
        language = await self._resolve_language(simulation_id)
        prompt = await self._prepare_prompt(source_id=simulation_id, language=language)
        llm = await self._prepare_llm_service(simulation_id)

        context = TurnImageSignificanceContext(
            narration=narration,
            action_summaries=[f"{action.label} ({action.type})" for action in actions],
        )
        decision = await llm.invoke_structured_with_repair(
            output_model=TurnImageSignificanceDecision,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return one valid TurnImageSignificanceDecision JSON object only, with significant "
                "(boolean) and reason (one short sentence)."
            ),
            run_name="turn_image_trigger.significance",
        )

        return decision.significant

    async def _turns_since_last_generation(self, *, simulation_id: str, current_sequence: int) -> int:
        last_sequence = await self._db.media.get_last_turn_sequence_with_generated_image(simulation_id)
        if last_sequence is None:
            return current_sequence

        return max(current_sequence - last_sequence, 0)

    async def should_generate(self,
                              *,
                              simulation_id: str,
                              turn: Turn,
                              narration: str,
                              actions: list[ProposedAction],
                              config: ImageGenerationConfig,
                              ) -> bool:
        if config.mode == ImageGenerationMode.MANUAL:
            return False
        if config.mode == ImageGenerationMode.ALWAYS:
            return True

        decision = deterministic_turn_significance(actions)
        if decision is None:
            decision = await self._llm_significance(simulation_id=simulation_id, narration=narration, actions=actions)

        if not decision:
            turns_since = await self._turns_since_last_generation(
                simulation_id=simulation_id,
                current_sequence=turn.sequence,
            )
            if turns_since >= config.fallback_turns:
                decision = True

        return decision

    async def _resolve_scene_location(self, *, coordination_result: SceneCoordinationResult) -> str | None:
        for accepted in coordination_result.accepted_actions:
            location = await self._db.location.get_location_by_character(accepted.actor_id)
            if location:
                return location.id

        return None

    async def maybe_generate(self,
                             *,
                             simulation_id: str,
                             turn: Turn,
                             narration: str,
                             coordination_result: SceneCoordinationResult,
                             ) -> None:
        """Fire-and-forget entry point: evaluate the simulation's ImageGenerationConfig and, if
        triggered, generate and link a scene image for this turn. Never raises - failures (no
        config, no eligible location, no model configured, generation errors) are logged and
        swallowed so this never disrupts the turn pipeline."""
        try:
            config = await self._db.config.get_image_generation_config(simulation_id)
            if not config or config.mode == ImageGenerationMode.MANUAL:
                return

            actions = [accepted.action for accepted in coordination_result.accepted_actions]
            triggered = await self.should_generate(
                simulation_id=simulation_id,
                turn=turn,
                narration=narration,
                actions=actions,
                config=config,
            )
            if not triggered:
                return

            location_id = await self._resolve_scene_location(coordination_result=coordination_result)
            if not location_id:
                return

            scene_generator = SceneImageGenerator(
                database=self._db, storage=self._storage,
                workflow_loader=self._workflow_loader, prompt_loader=self._prompt_loader,
            )
            await scene_generator.generate_scene(
                simulation_id=simulation_id,
                location_id=location_id,
                turn_id=turn.id,
            )
        except Exception as exc:
            log_event(
                "turn_image_generation_failed",
                simulation_id=simulation_id,
                turn_id=turn.id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
