import asyncio
import hashlib
import json
from datetime import timedelta
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from uuid import uuid4
from langgraph.constants import START, END
from langgraph.graph.state import StateGraph, CompiledStateGraph
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import GraphStateSnapshotType, SceneCoordinationProblemType, \
    SceneCoordinationStatus, SimulationGenerationRequestType, TurnType
from world_simulation_engine.model import AcceptedSceneAction, ActionValidationResult, GenerationJob, World, \
    Simulation, InputInterpretation, \
    ActionCandidateSet, ActionProposal, CharacterActionPlan, ProposedAction, SceneCoordinationResult, \
    GraphStateSnapshot, MemorySummaryProposal, NarrationProposal, ReactionHistoryEntry, StateCommitProposal, Turn
from world_simulation_engine.component.prompt_loader import PromptLoader
from world_simulation_engine.service import DatabaseService
from .action_validator import ActionValidator
from .character_simulator import CharacterSimulator
from .input_interpreter import InputInterpreter
from .memory_summarizer import MemorySummarizer
from .narrator import Narrator
from .scene_coordinator import SceneCoordinator
from .state_committer import StateCommitter


class CharacterActionProposalRecord(BaseModel):
    character_id: str
    proposal: ActionProposal
    rework_attempt: int = Field(default=0, ge=0)


class CharacterActionValidationRecord(BaseModel):
    character_id: str
    proposal: ActionProposal
    validation: ActionValidationResult
    proposal_validations: list[ActionValidationResult] = Field(default_factory=list)


class WorldSimulatorState(BaseModel):
    world: World
    simulation: Simulation

    user_input: str | None
    request_type: SimulationGenerationRequestType = SimulationGenerationRequestType.USER_INPUT_GENERATION

    input_interpretation: InputInterpretation | None = None
    user_action_validation: ActionValidationResult | None = None
    user_action_coordination: SceneCoordinationResult | None = None

    character_actions: list[CharacterActionProposalRecord] = Field(default_factory=list)
    character_action_validations: list[CharacterActionValidationRecord] = Field(default_factory=list)
    character_action_coordination: SceneCoordinationResult | None = None
    previous_character_action_coordination: SceneCoordinationResult | None = None
    character_actions_are_reactions: bool = False
    reaction_history: list[ReactionHistoryEntry] = Field(default_factory=list)
    narration: NarrationProposal | str | None = None
    committed_turn: Turn | None = None
    state_commit_proposal: StateCommitProposal | None = None
    memory_summary_proposal: MemorySummaryProposal | None = None


class CharacterActionProposalState(BaseModel):
    world_id: str
    simulation_id: str
    character_id: str
    user_input: str
    character_actions: list[CharacterActionProposalRecord] = Field(default_factory=list)
    character_action_validations: list[CharacterActionValidationRecord] = Field(default_factory=list)
    character_action_coordination: SceneCoordinationResult | None = None
    previous_character_action_coordination: SceneCoordinationResult | None = None
    character_actions_are_reactions: bool = False
    reaction_history: list[ReactionHistoryEntry] = Field(default_factory=list)
    narration: NarrationProposal | str | None = None
    committed_turn: Turn | None = None
    state_commit_proposal: StateCommitProposal | None = None
    memory_summary_proposal: MemorySummaryProposal | None = None


@dataclass
class _SimulatorRun:
    thread_id: str
    simulation_id: str
    queue: asyncio.Queue[Any] = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    final_state: Any = None
    error: BaseException | None = None


class WorldSimulator:
    _MAX_VALIDATION_REWORK_ATTEMPTS = 3
    _RUN_DONE = object()

    def __init__(self,
                 database: DatabaseService,
                 prompt_loader: PromptLoader | None = None,
                 langfuse_handler: CallbackHandler | None = None,
                 ):
        self._db = database
        self._prompt_loader = prompt_loader
        self._langfuse_handler = langfuse_handler

        self._action_validator = ActionValidator(
            database=database,
            prompt_loader=prompt_loader,
        )
        self._character_simulator = CharacterSimulator(
            database=database,
            prompt_loader=prompt_loader,
            langfuse_handler=self._langfuse_handler
        )
        self._input_interpreter = InputInterpreter(
            database=database,
            prompt_loader=prompt_loader,
        )
        self._memory_summarizer = MemorySummarizer(
            database=database,
            prompt_loader=prompt_loader,
        )
        self._narrator = Narrator(
            database=database,
            prompt_loader=prompt_loader,
        )
        self._scene_coordinator = SceneCoordinator(
            database=database,
            prompt_loader=prompt_loader,
        )
        self._state_committer = StateCommitter(
            database=database,
            prompt_loader=prompt_loader,
        )

        self._user_input_graph = self._build_user_input_generation_graph()
        self._character_round_graph = self._build_character_round_generation_graph()
        self._simulator_graph = self._user_input_graph
        self._run_registry: dict[str, _SimulatorRun] = {}
        self._completed_run_registry: dict[str, _SimulatorRun] = {}
        self._simulation_run_locks: dict[str, asyncio.Lock] = {}
        self._run_registry_lock = asyncio.Lock()

    async def start_generation(
            self,
            state: WorldSimulatorState,
            request_type: SimulationGenerationRequestType = \
                SimulationGenerationRequestType.USER_INPUT_GENERATION,
            regenerate_turn_sequence: int | None = None,
            client_request_id: str | None = None,
    ) -> str:
        """
        Schedule a simulator graph run in the background and return its thread id.
        """
        request_fingerprint = self._generation_request_fingerprint(
            state=state,
            request_type=request_type,
            regenerate_turn_sequence=regenerate_turn_sequence,
        )
        if client_request_id:
            existing_job = await self._db.generation_job.get_job_by_client_request_id(
                simulation_id=state.simulation.id,
                client_request_id=client_request_id,
            )
            if existing_job:
                if existing_job.request_fingerprint != request_fingerprint:
                    raise ValueError(
                        f"Client request id {client_request_id} was already used for a different "
                        "generation request"
                    )
                return existing_job.id

        thread_id = str(uuid4())
        run = _SimulatorRun(
            thread_id=thread_id,
            simulation_id=state.simulation.id,
        )

        async with self._run_registry_lock:
            if client_request_id:
                existing_job = await self._db.generation_job.get_job_by_client_request_id(
                    simulation_id=state.simulation.id,
                    client_request_id=client_request_id,
                )
                if existing_job:
                    if existing_job.request_fingerprint != request_fingerprint:
                        raise ValueError(
                            f"Client request id {client_request_id} was already used for a different "
                            "generation request"
                        )
                    return existing_job.id

            active_job = await self._db.generation_job.get_active_job(state.simulation.id)
            if active_job:
                if client_request_id:
                    existing_job = await self._db.generation_job.get_job_by_client_request_id(
                        simulation_id=state.simulation.id,
                        client_request_id=client_request_id,
                    )
                    if existing_job and existing_job.request_fingerprint == request_fingerprint:
                        return existing_job.id
                raise RuntimeError(f"Simulation {state.simulation.id} already has an active generation")

            simulation_lock = self._simulation_run_locks.setdefault(
                state.simulation.id,
                asyncio.Lock(),
            )
            if simulation_lock.locked():
                raise RuntimeError(f"Simulation {state.simulation.id} already has an active generation")

            try:
                await simulation_lock.acquire()
                try:
                    await self._db.generation_job.create_job(
                        GenerationJob(
                            id=thread_id,
                            simulation_id=state.simulation.id,
                            client_request_id=client_request_id,
                            request_fingerprint=request_fingerprint,
                            request_type=request_type,
                            regenerate_turn_sequence=regenerate_turn_sequence,
                        )
                    )
                except RuntimeError:
                    if client_request_id:
                        existing_job = await self._db.generation_job.get_job_by_client_request_id(
                            simulation_id=state.simulation.id,
                            client_request_id=client_request_id,
                        )
                        if existing_job and existing_job.request_fingerprint == request_fingerprint:
                            simulation_lock.release()
                            return existing_job.id
                    raise

                state = await self._prepare_generation_state(
                    state=state,
                    request_type=request_type,
                    regenerate_turn_sequence=regenerate_turn_sequence,
                )
                self._run_registry[thread_id] = run
                self._completed_run_registry.pop(thread_id, None)
                if state.request_type == SimulationGenerationRequestType.USER_INPUT_GENERATION:
                    await self._save_graph_state_snapshot(
                        state=state,
                        type=GraphStateSnapshotType.BEFORE_USER_INPUT,
                        turn=await self._latest_turn(state.simulation.id),
                    )
            except BaseException:
                self._run_registry.pop(thread_id, None)
                try:
                    job = await self._db.generation_job.get_job(thread_id)
                    if job:
                        await self._db.generation_job.mark_failed(
                            thread_id,
                            "Generation failed during setup",
                        )
                except BaseException:
                    pass
                if simulation_lock.locked():
                    simulation_lock.release()
                raise

        run.task = asyncio.create_task(
            self._run_generation(
                run=run,
                state=state,
                simulation_lock=simulation_lock,
            )
        )
        return thread_id

    async def stream_generation(self, thread_id: str) -> AsyncIterator[Any]:
        """
        Stream graph output for a running thread.

        If the background run has already finished and been removed from the active registry, this returns the final
        state once.
        """
        async with self._run_registry_lock:
            run = self._run_registry.get(thread_id)
            completed_run = self._completed_run_registry.get(thread_id)

        if run is None:
            if completed_run is None:
                raise KeyError(f"Generation thread {thread_id} not found")
            if completed_run.error:
                raise completed_run.error
            if completed_run.final_state is not None:
                yield completed_run.final_state
            return

        while True:
            item = await run.queue.get()
            if item is self._RUN_DONE:
                break

            yield item

        if run.error:
            raise run.error

    async def get_generation_final_state(self, thread_id: str) -> Any:
        async with self._run_registry_lock:
            run = self._run_registry.get(thread_id) or self._completed_run_registry.get(thread_id)

        if run is None:
            raise KeyError(f"Generation thread {thread_id} not found")

        if run.task:
            await run.task

        if run.error:
            raise run.error

        return run.final_state

    def is_generation_running(self, thread_id: str) -> bool:
        return thread_id in self._run_registry

    def _graph_for_request_type(self, request_type: SimulationGenerationRequestType) -> CompiledStateGraph:
        if request_type == SimulationGenerationRequestType.USER_INPUT_GENERATION:
            return self._user_input_graph

        if request_type in {
            SimulationGenerationRequestType.CONTINUE_GENERATION,
            SimulationGenerationRequestType.REGENERATION,
        }:
            return self._character_round_graph

        raise ValueError(f"Unsupported generation request type: {request_type}")

    async def _run_generation(
            self,
            *,
            run: _SimulatorRun,
            state: WorldSimulatorState,
            simulation_lock: asyncio.Lock,
    ):
        try:
            await self._db.generation_job.mark_running(run.thread_id, stage="starting")
            graph = self._graph_for_request_type(state.request_type)
            current_stage = "starting"
            async for chunk in graph.astream(
                    state,
                    config=self._graph_run_config(run.thread_id),
                    stream_mode="values",
            ):
                run.final_state = chunk
                next_stage = self._stage_from_chunk(chunk) or current_stage
                if next_stage != current_stage:
                    await self._db.generation_job.update_job(
                        run.thread_id,
                        {"stage": next_stage},
                    )
                    current_stage = next_stage
                await run.queue.put(chunk)
            await self._db.generation_job.mark_completed(
                run.thread_id,
                final_turn_id=self._final_turn_id(run.final_state),
            )
        except BaseException as exc:
            run.error = exc
            try:
                await self._db.generation_job.mark_failed(run.thread_id, str(exc))
            except BaseException:
                # Preserve the generation error even if persistence is also unavailable.
                pass
        finally:
            async with self._run_registry_lock:
                self._run_registry.pop(run.thread_id, None)
                self._completed_run_registry[run.thread_id] = run
                if simulation_lock.locked():
                    simulation_lock.release()

            await run.queue.put(self._RUN_DONE)

    @staticmethod
    def _generation_request_fingerprint(
            *,
            state: WorldSimulatorState,
            request_type: SimulationGenerationRequestType,
            regenerate_turn_sequence: int | None,
    ) -> str:
        payload = json.dumps(
            {
                "simulation_id": state.simulation.id,
                "request_type": request_type,
                "user_input": state.user_input,
                "regenerate_turn_sequence": regenerate_turn_sequence,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _stage_from_chunk(chunk: Any) -> str | None:
        if not isinstance(chunk, dict):
            return None
        if chunk.get("memory_summary_proposal"):
            return "memory_summarizer"
        if chunk.get("committed_turn") or chunk.get("state_commit_proposal"):
            return "state_committer"
        if chunk.get("narration"):
            return "narrator"
        if chunk.get("character_action_coordination") or chunk.get("user_action_coordination"):
            return "scene_coordinator"
        if chunk.get("character_action_validations") or chunk.get("user_action_validation"):
            return "action_validator"
        if chunk.get("character_actions"):
            return "character_simulator"
        if chunk.get("input_interpretation"):
            return "input_interpreter"
        return None

    @staticmethod
    def _final_turn_id(state: Any) -> str | None:
        if not isinstance(state, dict):
            return None
        turn = state.get("committed_turn")
        if hasattr(turn, "id"):
            return turn.id
        if isinstance(turn, dict):
            return turn.get("id")
        return None

    def _graph_run_config(self, thread_id: str) -> dict:
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
        }
        if self._langfuse_handler:
            config["callbacks"] = [self._langfuse_handler]

        return config

    async def interpret_user_input(self, state: WorldSimulatorState):
        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        if not state.user_input:
            raise RuntimeError("No user input supplied")

        interpretation = await self._input_interpreter.interpret(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            character_id=user_character.id,
            user_input=state.user_input,
        )

        return {
            "input_interpretation": interpretation,
        }

    async def validate_user_action(self, state: WorldSimulatorState):
        if not state.input_interpretation:
            raise RuntimeError("No input interpretation supplied")

        if any(item.type == "ooc" for item in state.input_interpretation.items):
            # TODO: Handle OOC commands before validating user actions.
            raise NotImplementedError("OOC command handling is not implemented yet")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        await self._ensure_user_input_only_controls_user_character(
            state=state,
            user_character=user_character,
        )

        actions = [
            item.action
            for item in state.input_interpretation.items
            if item.type == "action"
        ]
        validation = await self._action_validator.validate_actions(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            character_id=user_character.id,
            actions=actions,
        )

        return {
            "user_action_validation": validation,
        }

    async def _ensure_user_input_only_controls_user_character(
            self,
            *,
            state: WorldSimulatorState,
            user_character,
    ):
        if not state.input_interpretation:
            raise RuntimeError("No input interpretation supplied")
        if any(item.type == "ooc" for item in state.input_interpretation.items):
            return

        user_location = await self._db.location.get_location_by_character(user_character.id)
        if not user_location:
            return

        nearby_characters = await self._db.get_characters_in_location(user_location.id)
        other_names = []
        for character, _, _, _ in nearby_characters:
            if character.id == user_character.id:
                continue
            if character.name:
                other_names.extend([character.name, character.name.split()[0]])

        action_verbs = (
            "answers",
            "asks",
            "decides",
            "does",
            "goes",
            "moves",
            "says",
            "speaks",
            "takes",
            "tells",
            "walks",
        )
        for item in state.input_interpretation.items:
            if item.type != "action":
                continue
            source = item.source_text.strip().lower()
            for name in other_names:
                normalized_name = name.lower()
                if any(source.startswith(f"{normalized_name} {verb}") for verb in action_verbs):
                    raise RuntimeError(
                        "User input may only describe actions attempted by the user character. "
                        f"Other character action was found in: {item.source_text}"
                    )

    async def coordinate_user_actions(self, state: WorldSimulatorState):
        if not state.user_action_validation:
            raise RuntimeError("No user action validation supplied")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        actions = self._allowed_actions_from_validation(state.user_action_validation)
        coordination = await self._scene_coordinator.coordinate_scene(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            action_plans=[
                CharacterActionPlan(
                    actor_id=user_character.id,
                    actions=actions,
                    candidate_sets=[
                        ActionCandidateSet(
                            proposal_index=0,
                            actions=actions,
                        )
                    ] if actions else [],
                )
            ],
        )

        return {
            "user_action_coordination": coordination,
        }

    async def coordinate_rejected_user_actions(self, state: WorldSimulatorState):
        if not state.user_action_validation:
            raise RuntimeError("No user action validation supplied")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        return {
            "user_action_coordination": self._coordination_from_rejected_user_validation(
                actor_id=user_character.id,
                validation=state.user_action_validation,
            ),
        }

    async def propose_character_actions(self, state: CharacterActionProposalState):
        proposal = await self._character_simulator.propose_actions(
            world_id=state.world_id,
            simulation_id=state.simulation_id,
            character_id=state.character_id,
            user_input=state.user_input,
        )

        return {
            "character_actions": [
                CharacterActionProposalRecord(
                    character_id=state.character_id,
                    proposal=proposal,
                )
            ],
            "character_action_validations": [],
            "character_action_coordination": None,
            "previous_character_action_coordination": None,
            "character_actions_are_reactions": False,
            "reaction_history": [],
        }

    async def validate_character_actions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        validation_records = []
        for entry in state.character_actions:
            validation_records.append(
                await self._validate_character_action_with_rework(
                    world_id=world_id,
                    simulation_id=simulation_id,
                    user_input=state.user_input or "",
                    entry=entry,
                )
            )

        return {
            "character_action_validations": validation_records,
        }

    async def propose_scheduled_character_actions(self, state: WorldSimulatorState):
        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        location = await self._db.location.get_location_by_character(
            character_id=user_character.id
        )
        if not location:
            return {
                "character_actions": [],
                "character_action_validations": [],
                "character_action_coordination": None,
                "previous_character_action_coordination": None,
                "character_actions_are_reactions": False,
                "reaction_history": [],
            }

        # TODO: Replace this local-location activation with the time-based simulation scheduler.
        nearby_characters = await self._db.get_characters_in_location(
            root_location_id=location.id,
        )
        proposals = []
        for character, _, _, _ in nearby_characters:
            if character.id == user_character.id or character.user_controlled:
                continue

            proposal = await self._character_simulator.propose_actions(
                world_id=state.world.id,
                simulation_id=state.simulation.id,
                character_id=character.id,
                user_input=state.user_input or "",
            )
            proposals.append(
                CharacterActionProposalRecord(
                    character_id=character.id,
                    proposal=proposal,
                )
            )

        return {
            "character_actions": proposals,
            "character_action_validations": [],
            "character_action_coordination": None,
            "previous_character_action_coordination": None,
            "character_actions_are_reactions": False,
            "reaction_history": [],
        }

    async def propose_character_reactions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")
        if not state.character_action_coordination.problem:
            raise RuntimeError("No coordination problem supplied for character reaction")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=simulation_id
        )
        user_character_id = user_character.id if user_character else None
        actors_to_react = self._actors_to_react(
            coordination=state.character_action_coordination,
            user_character_id=user_character_id,
        )
        if not actors_to_react:
            return {
                "character_actions": [],
                "character_action_validations": [],
                "previous_character_action_coordination": None,
                "character_action_coordination": state.character_action_coordination,
                "character_actions_are_reactions": False,
                "reaction_history": state.reaction_history,
            }

        action_plans = self._character_action_plans_from_validations(
            state.character_action_validations,
            is_reaction=state.character_actions_are_reactions,
            previous_coordination=state.previous_character_action_coordination,
        )
        reaction_history = self._updated_reaction_history(
            existing=state.reaction_history,
            reactions=state.character_actions if state.character_actions_are_reactions else [],
        )
        proposals = []
        for actor_id in actors_to_react:
            proposal = await self._character_simulator.propose_reaction(
                world_id=world_id,
                simulation_id=simulation_id,
                character_id=actor_id,
                coordination_result=state.character_action_coordination,
                action_plans=action_plans,
                reaction_history=reaction_history,
                user_input=state.user_input or "",
            )
            proposals.append(
                CharacterActionProposalRecord(
                    character_id=actor_id,
                    proposal=proposal,
                )
            )

        return {
            "character_actions": proposals,
            "character_action_validations": [],
            "previous_character_action_coordination": state.character_action_coordination,
            "character_action_coordination": None,
            "character_actions_are_reactions": True,
            "reaction_history": reaction_history,
        }

    async def coordinate_character_actions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_validations:
            raise RuntimeError("No character action validations supplied")

        previous_coordination = state.previous_character_action_coordination
        action_plans = self._character_action_plans_from_validations(
            state.character_action_validations,
            is_reaction=state.character_actions_are_reactions,
            previous_coordination=previous_coordination,
        )
        coordination = await self._scene_coordinator.coordinate_scene(
            world_id=world_id,
            simulation_id=simulation_id,
            action_plans=action_plans,
            reaction_history=state.reaction_history,
            accepted_history=self._accepted_history_from_coordination(previous_coordination),
        )
        if state.character_actions_are_reactions and previous_coordination:
            coordination = self._merge_reaction_coordination(
                previous_coordination=previous_coordination,
                reaction_coordination=coordination,
            )

        return {
            "character_action_coordination": coordination,
            "previous_character_action_coordination": None,
        }

    async def narrate_turn(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        narration = await self._narrator.narrate_turn(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=state.character_action_coordination,
            user_input=state.user_input,
        )

        return {
            "narration": narration,
        }

    async def narrate_user_turn(self, state: WorldSimulatorState):
        coordination = await self._user_coordination_from_state(state)

        narration = await self._narrator.narrate_turn(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            coordination_result=coordination,
            user_input=state.user_input,
        )

        return {
            "narration": narration,
            "user_action_coordination": coordination,
        }

    async def commit_character_actions(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        if not state.narration:
            raise RuntimeError("No narration supplied")

        proposal = await self._state_committer.commit_character_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=state.character_action_coordination,
            user_input=state.user_input,
        )
        simulation = state.simulation if isinstance(state, WorldSimulatorState) else await self._require_simulation(simulation_id)
        turn, simulation = await self._create_turn_and_apply_commit(
            simulation=simulation,
            simulation_id=simulation_id,
            turn_type=TurnType.SYSTEM_RESPONSE if state.user_input else TurnType.SYSTEM_CONTINUE,
            content=Narrator.serialize_content(state.narration),
            proposal=proposal,
            coordination_result=state.character_action_coordination,
        )
        return {
            "committed_turn": turn,
            "state_commit_proposal": proposal,
            "simulation": simulation,
        }

    async def commit_user_actions(self, state: WorldSimulatorState):
        coordination = await self._user_coordination_from_state(state)

        if not state.user_input:
            raise RuntimeError("No user input supplied")

        proposal = await self._state_committer.commit_user_actions(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            coordination_result=coordination,
            user_input=state.user_input,
        )
        turn, simulation = await self._create_turn_and_apply_commit(
            simulation=state.simulation,
            simulation_id=state.simulation.id,
            turn_type=TurnType.USER_INPUT,
            content=state.user_input,
            proposal=proposal,
            coordination_result=coordination,
        )
        return {
            "committed_turn": turn,
            "state_commit_proposal": proposal,
            "simulation": simulation,
            "user_action_coordination": coordination,
        }

    async def summarize_user_memory(self, state: WorldSimulatorState):
        if not state.committed_turn:
            raise RuntimeError("No committed turn supplied")
        if not state.state_commit_proposal:
            raise RuntimeError("No state commit proposal supplied")
        if not state.user_action_coordination:
            raise RuntimeError("No user action coordination supplied")

        proposal = await self._memory_summarizer.summarize_user_actions(
            world_id=state.world.id,
            simulation_id=state.simulation.id,
            turn=state.committed_turn,
            coordination_result=state.user_action_coordination,
            state_commit=state.state_commit_proposal,
            user_input=state.user_input,
        )
        await self._db.memory_summary.apply_memory_summary_proposal(
            proposal=proposal,
            turn_id=state.committed_turn.id,
        )
        await self._save_graph_state_snapshot(
            state=state.model_copy(update={"memory_summary_proposal": proposal}),
            type=GraphStateSnapshotType.AFTER_USER_INPUT,
            turn=state.committed_turn,
        )
        return {
            "memory_summary_proposal": proposal,
        }

    async def _user_coordination_from_state(self, state: WorldSimulatorState) -> SceneCoordinationResult:
        if state.user_action_coordination:
            return state.user_action_coordination

        if not state.user_action_validation:
            raise RuntimeError("No user action validation supplied")

        user_character = await self._db.character.get_user_character_by_simulation(
            simulation_id=state.simulation.id
        )
        if not user_character:
            raise ValueError(f"Simulation {state.simulation.id} has no user character")

        if all(item.allowed for item in state.user_action_validation.validations):
            return self._coordination_from_allowed_user_validation(
                actor_id=user_character.id,
                validation=state.user_action_validation,
            )

        return self._coordination_from_rejected_user_validation(
            actor_id=user_character.id,
            validation=state.user_action_validation,
        )

    async def get_graph_state_snapshot(
            self,
            simulation_id: str,
            type: GraphStateSnapshotType,
    ) -> GraphStateSnapshot | None:
        return await self._db.graph_state_snapshot.get_snapshot(
            simulation_id=simulation_id,
            type=type,
        )

    async def get_graph_state_snapshot_state(
            self,
            simulation_id: str,
            type: GraphStateSnapshotType,
    ) -> WorldSimulatorState | None:
        snapshot = await self.get_graph_state_snapshot(
            simulation_id=simulation_id,
            type=type,
        )
        if not snapshot:
            return None

        return WorldSimulatorState.model_validate(snapshot.state)

    async def summarize_character_memory(self, state: WorldSimulatorState | CharacterActionProposalState):
        world_id = state.world.id if isinstance(state, WorldSimulatorState) else state.world_id
        simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id

        if not state.committed_turn:
            raise RuntimeError("No committed turn supplied")
        if not state.state_commit_proposal:
            raise RuntimeError("No state commit proposal supplied")
        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        proposal = await self._memory_summarizer.summarize_character_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            turn=state.committed_turn,
            coordination_result=state.character_action_coordination,
            state_commit=state.state_commit_proposal,
            user_input=state.user_input,
            narration=Narrator.render_text(state.narration),
        )
        await self._db.memory_summary.apply_memory_summary_proposal(
            proposal=proposal,
            turn_id=state.committed_turn.id,
        )
        if isinstance(state, WorldSimulatorState):
            await self._save_graph_state_snapshot(
                state=state.model_copy(update={"memory_summary_proposal": proposal}),
                type=GraphStateSnapshotType.AFTER_CHARACTER_ROUND,
                turn=state.committed_turn,
            )
        return {
            "memory_summary_proposal": proposal,
        }

    async def route_after_input(self, state: WorldSimulatorState):
        if state.request_type == SimulationGenerationRequestType.USER_INPUT_GENERATION:
            if not state.user_input:
                raise RuntimeError("User input generation requires user input")
            return "interpret_user_input"

        if state.request_type in {
            SimulationGenerationRequestType.CONTINUE_GENERATION,
            SimulationGenerationRequestType.REGENERATION,
        }:
            if state.user_input:
                raise RuntimeError(f"{state.request_type} requires empty user input")
            return "propose_scheduled_character_actions"

        raise ValueError(f"Unsupported generation request type: {state.request_type}")

    async def route_after_input_interpretation(self, state: WorldSimulatorState):
        if not state.input_interpretation:
            raise RuntimeError("No input interpretation supplied")

        if any(item.type == "ooc" for item in state.input_interpretation.items):
            # TODO: Route OOC commands to their own handler.
            raise NotImplementedError("OOC command route is not implemented yet")

        return "validate_user_action"

    async def route_after_user_action_validation(self, state: WorldSimulatorState):
        if not state.user_action_validation:
            raise RuntimeError("No user action validation supplied")

        if all(item.allowed for item in state.user_action_validation.validations):
            return "commit_user_actions"

        return "narrate_user_turn"

    async def route_after_user_coordination(self, state: WorldSimulatorState):
        if not state.user_action_coordination:
            raise RuntimeError("No user action coordination supplied")

        return self._route_after_coordination(
            state.user_action_coordination,
            complete_route="commit_user_actions",
            problem_route="narrate_user_turn",
            user_decision_route="narrate_user_turn",
            stopped_route="narrate_user_turn",
        )

    async def route_after_user_memory_summary(self, state: WorldSimulatorState):
        if not state.user_action_coordination:
            raise RuntimeError("No user action coordination supplied")

        if state.user_action_coordination.status == SceneCoordinationStatus.COMPLETE:
            return "propose_scheduled_character_actions"

        return END

    async def route_after_scheduled_character_actions(self, state: WorldSimulatorState):
        if state.character_actions:
            return "validate_character_actions"

        return END

    async def route_after_character_coordination(self, state: WorldSimulatorState | CharacterActionProposalState):
        if not state.character_action_coordination:
            raise RuntimeError("No character action coordination supplied")

        if (
                state.character_action_coordination.status == SceneCoordinationStatus.PROBLEM
                and state.character_action_coordination.problem
                and not state.character_action_coordination.problem.needs_user_decision
        ):
            simulation_id = state.simulation.id if isinstance(state, WorldSimulatorState) else state.simulation_id
            user_character = await self._db.character.get_user_character_by_simulation(
                simulation_id=simulation_id
            )
            if not self._actors_to_react(
                    coordination=state.character_action_coordination,
                    user_character_id=user_character.id if user_character else None,
            ):
                return "narrate_turn"

        return self._route_after_coordination(
            state.character_action_coordination,
            complete_route="narrate_turn",
            reaction_route="propose_character_reactions",
            user_decision_route="narrate_turn",
            stopped_route="narrate_turn",
        )

    @staticmethod
    def _proposal_sequences(proposal: ActionProposal) -> list[list[ProposedAction]]:
        return [
            proposal.actions,
            *proposal.backup_proposals,
        ]

    async def _validate_character_action_with_rework(
            self,
            *,
            world_id: str,
            simulation_id: str,
            user_input: str,
            entry: CharacterActionProposalRecord,
    ) -> CharacterActionValidationRecord:
        current_entry = entry
        while True:
            proposal_validations = []
            for sequence in self._proposal_sequences(current_entry.proposal):
                proposal_validations.append(
                    await self._action_validator.validate_actions(
                        world_id=world_id,
                        simulation_id=simulation_id,
                        character_id=current_entry.character_id,
                        actions=sequence,
                    )
                )

            validation_record = CharacterActionValidationRecord(
                character_id=current_entry.character_id,
                proposal=current_entry.proposal,
                validation=proposal_validations[0],
                proposal_validations=proposal_validations,
            )
            if self._valid_sequence_candidates_from_record(validation_record):
                return validation_record

            if current_entry.rework_attempt >= self._MAX_VALIDATION_REWORK_ATTEMPTS:
                raise RuntimeError(
                    f"Character {current_entry.character_id} did not propose a valid action after "
                    f"{self._MAX_VALIDATION_REWORK_ATTEMPTS} rework attempts"
                )

            proposal = await self._character_simulator.propose_actions(
                world_id=world_id,
                simulation_id=simulation_id,
                character_id=current_entry.character_id,
                user_input=self._character_rework_input(
                    user_input=user_input,
                    proposal=current_entry.proposal,
                    validation=validation_record.validation,
                    rework_attempt=current_entry.rework_attempt + 1,
                ),
            )
            current_entry = CharacterActionProposalRecord(
                character_id=current_entry.character_id,
                proposal=proposal,
                rework_attempt=current_entry.rework_attempt + 1,
            )

    @staticmethod
    def _character_rework_input(
            *,
            user_input: str,
            proposal: ActionProposal,
            validation: ActionValidationResult,
            rework_attempt: int,
    ) -> str:
        invalid_actions = [
            "\n".join(
                [
                    f"- action_index: {item.action_index}",
                    f"  label: {item.action.label}",
                    f"  reason: {item.reason}",
                    f"  blocking_conditions: {item.blocking_conditions}",
                    f"  warnings: {item.warnings}",
                ]
            )
            for item in validation.validations
            if not item.allowed
        ]
        feedback = "\n".join(invalid_actions) if invalid_actions else "- The previous proposal was not valid."
        return (
            f"{user_input}\n\n"
            f"## Previous action proposal failed validation, rework attempt {rework_attempt}\n\n"
            f"Treat this validator feedback as authoritative context and propose a different ActionProposal.\n"
            f"Do not repeat the invalid action unless the method, target, or immediate purpose meaningfully changes.\n\n"
            f"Failed proposal:\n"
            f"{proposal.model_dump_json(indent=2)}\n\n"
            f"Validation feedback:\n"
            f"{feedback}"
        )

    @staticmethod
    def _allowed_actions_from_validation(validation: ActionValidationResult) -> list[ProposedAction]:
        return [
            item.action
            for item in validation.validations
            if item.allowed
        ]

    @classmethod
    def _valid_sequence_candidates_from_record(
            cls,
            record: CharacterActionValidationRecord,
    ) -> list[tuple[int, list[ProposedAction]]]:
        sequences = cls._proposal_sequences(record.proposal)
        validations = record.proposal_validations or [record.validation]
        candidates = []
        for proposal_index, validation in enumerate(validations):
            if proposal_index >= len(sequences):
                continue
            if validation.validations and all(item.allowed for item in validation.validations):
                candidates.append((proposal_index, sequences[proposal_index]))

        return candidates

    @staticmethod
    def _coordination_from_allowed_user_validation(
            *,
            actor_id: str,
            validation: ActionValidationResult,
    ) -> SceneCoordinationResult:
        accepted_actions = []
        start_offset_seconds = 0
        for item in validation.validations:
            if not item.allowed:
                continue
            duration = item.action.intended_duration_seconds
            accepted_actions.append(
                AcceptedSceneAction(
                    actor_id=actor_id,
                    proposal_index=0,
                    action_index=item.action_index,
                    action=item.action,
                    start_offset_seconds=start_offset_seconds,
                    end_offset_seconds=start_offset_seconds + duration,
                    summary=WorldSimulator._user_action_summary(item.action),
                )
            )
            start_offset_seconds += duration

        return SceneCoordinationResult(
            status=SceneCoordinationStatus.COMPLETE,
            accepted_actions=accepted_actions,
            pending_actions=[],
            coordinator_notes=["User actions were accepted directly after validation."],
        )

    @staticmethod
    def _user_action_summary(action: ProposedAction) -> str:
        if action.utterance:
            return f'User character says "{action.utterance}"'

        return f"User character attempts {action.label.replace('_', ' ')}."

    @staticmethod
    def _coordination_from_rejected_user_validation(
            *,
            actor_id: str,
            validation: ActionValidationResult,
    ) -> SceneCoordinationResult:
        rejected = [
            item
            for item in validation.validations
            if not item.allowed
        ]
        if not rejected:
            return SceneCoordinationResult(
                status=SceneCoordinationStatus.COMPLETE,
                accepted_actions=[],
                pending_actions=[],
                coordinator_notes=["No rejected user actions were supplied."],
            )

        first_rejected = rejected[0]
        return SceneCoordinationResult(
            status=SceneCoordinationStatus.PROBLEM,
            accepted_actions=[],
            problem={
                "type": SceneCoordinationProblemType.OTHER,
                "time_offset_seconds": 0,
                "involved_actor_ids": [actor_id],
                "involved_actions": [
                    {
                        "actor_id": actor_id,
                        "proposal_index": 0,
                        "action_index": first_rejected.action_index,
                    }
                ],
                "description": first_rejected.reason,
                "needs_user_decision": False,
                "actors_to_react": [],
                "resolver_required": False,
            },
            pending_actions=[
                {
                    "actor_id": actor_id,
                    "proposal_index": 0,
                    "action_index": item.action_index,
                    "action": item.action,
                    "reason": item.reason,
                }
                for item in rejected
            ],
            coordinator_notes=[
                *validation.validator_notes,
                "User action validation failed before coordination.",
            ],
        )

    def _character_action_plans_from_validations(
            self,
            validation_records: list[CharacterActionValidationRecord],
            *,
            is_reaction: bool = False,
            previous_coordination: SceneCoordinationResult | None = None,
    ) -> list[CharacterActionPlan]:
        replaces_from_index_by_actor = self._reaction_replacement_indices(previous_coordination) if is_reaction else {}
        plans_by_actor: dict[str, CharacterActionPlan] = {}
        for record in validation_records:
            valid_sequences = self._valid_sequence_candidates_from_record(record)
            if not valid_sequences:
                continue

            plan = plans_by_actor.setdefault(
                record.character_id,
                CharacterActionPlan(
                    actor_id=record.character_id,
                    actions=valid_sequences[0][1],
                    is_reaction=is_reaction,
                    replaces_from_index=replaces_from_index_by_actor.get(record.character_id),
                ),
            )
            plan.action_proposals.append(record.proposal)
            for proposal_index, sequence in valid_sequences:
                if not any(
                        candidate_set.proposal_index == proposal_index
                        for candidate_set in plan.candidate_sets
                ):
                    plan.candidate_sets.append(
                        ActionCandidateSet(
                            proposal_index=proposal_index,
                            actions=sequence,
                        )
                    )

        return list(plans_by_actor.values())

    @staticmethod
    def _reaction_replacement_indices(
            coordination: SceneCoordinationResult | None,
    ) -> dict[str, int]:
        if not coordination or not coordination.problem:
            return {}

        indices: dict[str, int] = {}
        for reference in coordination.problem.involved_actions:
            current = indices.get(reference.actor_id)
            if current is None or reference.action_index < current:
                indices[reference.actor_id] = reference.action_index

        for pending in coordination.pending_actions:
            current = indices.get(pending.actor_id)
            if current is None or pending.action_index < current:
                indices[pending.actor_id] = pending.action_index

        return indices

    @staticmethod
    def _actors_to_react(
            *,
            coordination: SceneCoordinationResult,
            user_character_id: str | None,
    ) -> list[str]:
        if not coordination.problem:
            return []

        candidate_ids = coordination.problem.actors_to_react or coordination.problem.involved_actor_ids
        return [
            actor_id
            for actor_id in candidate_ids
            if actor_id != user_character_id
        ]

    @staticmethod
    def _reaction_signature(proposal: ActionProposal) -> str:
        action_signatures = [
            "|".join(
                [
                    str(action.type),
                    action.label,
                    ",".join(action.target_ids),
                    action.utterance or "",
                ]
            )
            for action in proposal.actions
        ]
        return "||".join(action_signatures)

    def _updated_reaction_history(
            self,
            *,
            existing: list[ReactionHistoryEntry],
            reactions: list[CharacterActionProposalRecord],
    ) -> list[ReactionHistoryEntry]:
        by_key = {
            (entry.actor_id, entry.action_signature): entry.count
            for entry in existing
        }
        for reaction in reactions:
            key = (
                reaction.character_id,
                self._reaction_signature(reaction.proposal),
            )
            by_key[key] = by_key.get(key, 0) + 1

        return [
            ReactionHistoryEntry(
                actor_id=actor_id,
                action_signature=action_signature,
                count=count,
            )
            for (actor_id, action_signature), count in by_key.items()
        ]

    @staticmethod
    def _accepted_history_from_coordination(
            coordination: SceneCoordinationResult | None,
    ) -> list[str]:
        if not coordination:
            return []

        return [
            (
                f"{action.start_offset_seconds}-{action.end_offset_seconds}s: "
                f"{action.actor_id} action {action.action_index} {action.summary}"
            )
            for action in coordination.accepted_actions
        ]

    @staticmethod
    def _merge_reaction_coordination(
            *,
            previous_coordination: SceneCoordinationResult,
            reaction_coordination: SceneCoordinationResult,
    ) -> SceneCoordinationResult:
        notes = [
            *previous_coordination.coordinator_notes,
            *reaction_coordination.coordinator_notes,
        ]
        if previous_coordination.accepted_actions:
            notes.append("Merged previously accepted actions with the character reaction coordination result.")

        return reaction_coordination.model_copy(
            update={
                "accepted_actions": [
                    *previous_coordination.accepted_actions,
                    *reaction_coordination.accepted_actions,
                ],
                "coordinator_notes": notes,
            }
        )

    @staticmethod
    def _route_after_coordination(
            coordination: SceneCoordinationResult,
            *,
            complete_route: str,
            problem_route: str | None = None,
            reaction_route: str | None = None,
            user_decision_route: str | None = None,
            stopped_route: str | None = None,
    ) -> str:
        if coordination.status == SceneCoordinationStatus.COMPLETE:
            return complete_route

        if coordination.status == SceneCoordinationStatus.PROBLEM:
            if coordination.problem and coordination.problem.needs_user_decision:
                if user_decision_route:
                    return user_decision_route

                return complete_route

            if reaction_route:
                return reaction_route

            if problem_route:
                return problem_route

            return complete_route

        if coordination.status == SceneCoordinationStatus.STOPPED:
            if stopped_route:
                return stopped_route

            return complete_route

        raise ValueError(f"Unsupported coordination status: {coordination.status}")

    async def _create_turn_and_apply_commit(
            self,
            *,
            simulation: Simulation,
            simulation_id: str,
            turn_type: TurnType,
            content: str,
            proposal: StateCommitProposal,
            coordination_result: SceneCoordinationResult,
    ) -> tuple[Turn, Simulation]:
        turn = await self._db.turn.create_next_turn(
            source_id=simulation_id,
            turn=Turn(
                sequence=0,
                type=turn_type,
                content=content,
                start_time=simulation.current_time,
            ),
        )
        await self._db.state_commit.apply_state_commit_proposal(
            proposal=proposal,
            source_id=simulation_id,
            turn_id=turn.id,
        )
        advanced_time = simulation.current_time + timedelta(
            seconds=self._coordination_elapsed_seconds(coordination_result)
        )
        updated_simulation = await self._db.simulation.update_current_time(
            simulation_id=simulation_id,
            current_time=advanced_time,
        )
        return turn, updated_simulation

    async def _require_simulation(self, simulation_id: str) -> Simulation:
        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        return simulation

    async def _prepare_generation_state(
            self,
            *,
            state: WorldSimulatorState,
            request_type: SimulationGenerationRequestType,
            regenerate_turn_sequence: int | None,
    ) -> WorldSimulatorState:
        if request_type == SimulationGenerationRequestType.USER_INPUT_GENERATION:
            if not state.user_input:
                raise RuntimeError("User input generation requires user input")
            return state.model_copy(update={"request_type": request_type})

        if state.user_input:
            raise RuntimeError(f"{request_type} requires empty user input")

        if request_type == SimulationGenerationRequestType.CONTINUE_GENERATION:
            snapshot = await self._db.graph_state_snapshot.get_latest_generation_base_snapshot(
                simulation_id=state.simulation.id,
            )
            if not snapshot:
                raise RuntimeError(
                    f"Simulation {state.simulation.id} has no character generation base snapshot to continue from"
                )
            return self._character_round_state_from_snapshot(
                snapshot=snapshot,
                request_type=request_type,
            )

        if request_type == SimulationGenerationRequestType.REGENERATION:
            if regenerate_turn_sequence is None:
                raise RuntimeError("Regeneration requires regenerate_turn_sequence")
            if regenerate_turn_sequence <= 0:
                raise RuntimeError("Regeneration requires a turn after the last user-input base")

            snapshot = await self._db.graph_state_snapshot.get_generation_base_snapshot_by_turn_sequence(
                simulation_id=state.simulation.id,
                turn_sequence=regenerate_turn_sequence - 1,
            )
            if not snapshot:
                raise RuntimeError(
                    f"Cannot regenerate turn {regenerate_turn_sequence}: no saved character-round base after "
                    f"turn {regenerate_turn_sequence - 1}"
                )
            return self._character_round_state_from_snapshot(
                snapshot=snapshot,
                request_type=request_type,
            )

        raise ValueError(f"Unsupported generation request type: {request_type}")

    @staticmethod
    def _character_round_state_from_snapshot(
            *,
            snapshot: GraphStateSnapshot,
            request_type: SimulationGenerationRequestType,
    ) -> WorldSimulatorState:
        return WorldSimulatorState.model_validate(snapshot.state).model_copy(
            update={
                "request_type": request_type,
                "user_input": None,
                "character_actions": [],
                "character_action_validations": [],
                "character_action_coordination": None,
                "previous_character_action_coordination": None,
                "character_actions_are_reactions": False,
                "reaction_history": [],
                "narration": None,
                "committed_turn": None,
                "state_commit_proposal": None,
                "memory_summary_proposal": None,
            },
        )

    async def _latest_turn(self, simulation_id: str) -> Turn | None:
        turns = await self._db.turn.list_turns(
            source_id=simulation_id,
            limit=1,
        )
        return turns[0] if turns else None

    async def _save_graph_state_snapshot(
            self,
            *,
            state: WorldSimulatorState,
            type: GraphStateSnapshotType,
            turn: Turn | None,
    ) -> GraphStateSnapshot:
        return await self._db.graph_state_snapshot.save_snapshot(
            GraphStateSnapshot(
                simulation_id=state.simulation.id,
                type=type,
                turn_id=turn.id if turn else None,
                turn_sequence=turn.sequence if turn else None,
                state=state.model_dump(mode="json"),
            )
        )

    @staticmethod
    def _coordination_elapsed_seconds(coordination: SceneCoordinationResult) -> int:
        if not coordination.accepted_actions:
            return 0

        return max(action.end_offset_seconds for action in coordination.accepted_actions)

    def _add_character_round_nodes(self, graph: StateGraph):
        graph.add_node("propose_scheduled_character_actions", self.propose_scheduled_character_actions)
        graph.add_node("propose_character_reactions", self.propose_character_reactions)
        graph.add_node("validate_character_actions", self.validate_character_actions)
        graph.add_node("coordinate_character_actions", self.coordinate_character_actions)
        graph.add_node("narrate_turn", self.narrate_turn)
        graph.add_node("commit_character_actions", self.commit_character_actions)
        graph.add_node("summarize_character_memory", self.summarize_character_memory)

    def _add_character_round_processing_edges(self, graph: StateGraph):
        graph.add_conditional_edges(
            "propose_scheduled_character_actions",
            self.route_after_scheduled_character_actions,
        )
        graph.add_edge("validate_character_actions", "coordinate_character_actions")
        graph.add_conditional_edges(
            "coordinate_character_actions",
            self.route_after_character_coordination,
        )
        graph.add_edge("propose_character_reactions", "validate_character_actions")
        graph.add_edge("narrate_turn", "commit_character_actions")
        graph.add_edge("commit_character_actions", "summarize_character_memory")
        graph.add_edge("summarize_character_memory", END)

    def _add_character_round_edges(self, graph: StateGraph, start_node: str):
        graph.add_edge(start_node, "propose_scheduled_character_actions")
        self._add_character_round_processing_edges(graph)

    def _build_user_input_generation_graph(self) -> CompiledStateGraph:
        graph = StateGraph(WorldSimulatorState)

        graph.add_node("interpret_user_input", self.interpret_user_input)
        graph.add_node("validate_user_action", self.validate_user_action)
        graph.add_node("narrate_user_turn", self.narrate_user_turn)
        graph.add_node("commit_user_actions", self.commit_user_actions)
        graph.add_node("summarize_user_memory", self.summarize_user_memory)
        self._add_character_round_nodes(graph)

        graph.add_edge(START, "interpret_user_input")
        graph.add_conditional_edges(
            "interpret_user_input",
            self.route_after_input_interpretation,
        )
        graph.add_conditional_edges(
            "validate_user_action",
            self.route_after_user_action_validation,
        )
        graph.add_edge("narrate_user_turn", "commit_user_actions")
        graph.add_edge("commit_user_actions", "summarize_user_memory")
        graph.add_conditional_edges(
            "summarize_user_memory",
            self.route_after_user_memory_summary,
        )
        self._add_character_round_processing_edges(graph)

        return graph.compile()

    def _build_character_round_generation_graph(self) -> CompiledStateGraph:
        graph = StateGraph(WorldSimulatorState)

        self._add_character_round_nodes(graph)
        self._add_character_round_edges(graph, START)

        return graph.compile()
