from datetime import timedelta

from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import Character, Intent, MemorySummaryProposal, SceneCoordinationResult, \
    Simulation, StateCommitProposal, Turn, World
from world_simulation_engine.service.database.memory_store import MemoryRecallRecord

from .simulator_component import SimulatorComponent


class ActorAbstractContext(BaseModel):
    actor: Character
    recent_memories: list[MemoryRecallRecord] = Field(default_factory=list)
    intents: list[Intent] = Field(default_factory=list)


class MemorySummarizerContext(BaseModel):
    world: World
    simulation: Simulation
    turn: Turn
    source: str
    user_input: str | None = None
    narration: str | None = None
    coordination_result: SceneCoordinationResult
    state_commit: StateCommitProposal
    actors: list[ActorAbstractContext] = Field(default_factory=list)


class MemorySummarizer(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.MEMORY_SUMMARIZER

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             turn: Turn,
                             coordination_result: SceneCoordinationResult,
                             state_commit: StateCommitProposal,
                             source: str,
                             user_input: str | None = None,
                             narration: str | None = None,
                             ) -> MemorySummarizerContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        actor_ids = {
            accepted.actor_id
            for accepted in coordination_result.accepted_actions
        }
        if coordination_result.problem:
            actor_ids.update(coordination_result.problem.involved_actor_ids)

        actors = []
        for actor_id in sorted(actor_ids):
            actor = await self._db.character.get_character(actor_id)
            if not actor:
                continue

            actors.append(
                ActorAbstractContext(
                    actor=actor,
                    recent_memories=await self._db.memory.get_recent_turn_memory_candidates(
                        character_id=actor_id,
                        source_id=simulation_id,
                    ),
                    intents=await self._db.intent.get_active_intent_candidates(
                        character_id=actor_id,
                        current_time=simulation.current_time,
                        deadline_delta=timedelta(hours=24),
                        priority_threshold=0,
                        urgency_threshold=0,
                    ),
                )
            )

        return MemorySummarizerContext(
            world=world,
            simulation=simulation,
            turn=turn,
            source=source,
            user_input=user_input,
            narration=narration,
            coordination_result=coordination_result,
            state_commit=state_commit,
            actors=actors,
        )

    async def _summarize_actions(self,
                                 *,
                                 world_id: str,
                                 simulation_id: str,
                                 turn: Turn,
                                 coordination_result: SceneCoordinationResult,
                                 state_commit: StateCommitProposal,
                                 source: str,
                                 user_input: str | None = None,
                                 narration: str | None = None,
                                 run_name: str,
                                 ) -> MemorySummaryProposal:
        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            turn=turn,
            coordination_result=coordination_result,
            state_commit=state_commit,
            source=source,
            user_input=user_input,
            narration=narration,
        )
        prompt = self._prepare_prompt(
            language=context.world.language,
            prompt_name="memory_summarizer",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        return await llm.invoke_structured_with_repair(
            output_model=MemorySummaryProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return a valid MemorySummaryProposal only. Do not propose physical state changes, narration, "
                "validation records, or scheduler records."
            ),
            run_name=run_name,
        )

    async def summarize_user_actions(self,
                                     *,
                                     world_id: str,
                                     simulation_id: str,
                                     turn: Turn,
                                     coordination_result: SceneCoordinationResult,
                                     state_commit: StateCommitProposal,
                                     user_input: str | None = None,
                                     ) -> MemorySummaryProposal:
        return await self._summarize_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            turn=turn,
            coordination_result=coordination_result,
            state_commit=state_commit,
            source="user",
            user_input=user_input,
            run_name="memory_summarizer.summarize_user_actions",
        )

    async def summarize_character_actions(self,
                                          *,
                                          world_id: str,
                                          simulation_id: str,
                                          turn: Turn,
                                          coordination_result: SceneCoordinationResult,
                                          state_commit: StateCommitProposal,
                                          user_input: str | None = None,
                                          narration: str | None = None,
                                          ) -> MemorySummaryProposal:
        return await self._summarize_actions(
            world_id=world_id,
            simulation_id=simulation_id,
            turn=turn,
            coordination_result=coordination_result,
            state_commit=state_commit,
            source="character",
            user_input=user_input,
            narration=narration,
            run_name="memory_summarizer.summarize_character_actions",
        )
