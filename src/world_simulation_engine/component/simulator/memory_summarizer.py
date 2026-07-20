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

        proposal = await llm.invoke_structured_with_repair(
            output_model=MemorySummaryProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return one valid MemorySummaryProposal JSON object only. Keep it small: 0-4 operations, no repeats. "
                "Every operation must use type, never name as the operation kind. create_memory needs event_id, "
                "support_type, and character_links; never involved_characters. create_intent needs exact character_id. "
                "Skip weak/uncertain records with no_abstract_change. Do not include physical state, relationships, "
                "narration, validation, scheduler, database instructions, prose, or markdown."
            ),
            run_name=run_name,
        )
        return self._normalize_proposal_references(
            proposal=proposal,
            context=context,
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

    @classmethod
    def _normalize_proposal_references(cls,
                                       *,
                                       proposal: MemorySummaryProposal,
                                       context: MemorySummarizerContext,
                                       ) -> MemorySummaryProposal:
        actor_ids = {
            actor.actor.id
            for actor in context.actors
        }
        actor_ids_by_name = {
            actor.actor.name.lower(): actor.actor.id
            for actor in context.actors
        }
        event_ids_by_name = {}
        event_ids = set()
        for operation in proposal.operations:
            if operation.type != "create_event":
                continue

            event_ids.add(operation.proposed_id)
            event_ids_by_name[operation.name.lower()] = operation.proposed_id
            event_ids_by_name[operation.summary.lower()] = operation.proposed_id

        normalized = proposal.model_dump(mode="json")
        for operation in normalized["operations"]:
            operation_type = operation.get("type")
            if operation_type in {"create_event", "update_event"}:
                cls._resolve_character_list(
                    operation.get("involved_characters", []),
                    actor_ids=actor_ids,
                    actor_ids_by_name=actor_ids_by_name,
                )

            if operation_type == "create_memory":
                cls._resolve_event_reference(
                    operation,
                    field_name="event_id",
                    event_ids=event_ids,
                    event_ids_by_name=event_ids_by_name,
                )
                cls._resolve_character_list(
                    operation.get("character_links", []),
                    actor_ids=actor_ids,
                    actor_ids_by_name=actor_ids_by_name,
                )
                operation["character_links"] = [
                    link
                    for link in operation.get("character_links", [])
                    if link.get("character_id") in actor_ids
                ]
                if not operation["character_links"]:
                    operation.clear()
                    operation.update({
                        "type": "no_abstract_change",
                        "reason": "Skipped memory proposal because no valid character links remained.",
                    })

            elif operation_type == "link_existing_memory":
                cls._resolve_character_id(
                    operation.get("character_link", {}),
                    actor_ids=actor_ids,
                    actor_ids_by_name=actor_ids_by_name,
                )
                if operation.get("character_link", {}).get("character_id") not in actor_ids:
                    operation.clear()
                    operation.update({
                        "type": "no_abstract_change",
                        "reason": "Skipped existing-memory link because the character id was not known.",
                    })

            elif operation_type == "create_intent":
                cls._resolve_character_id(
                    operation,
                    actor_ids=actor_ids,
                    actor_ids_by_name=actor_ids_by_name,
                )
                cls._resolve_event_reference(
                    operation,
                    field_name="created_by_event_id",
                    event_ids=event_ids,
                    event_ids_by_name=event_ids_by_name,
                )
                if operation.get("character_id") not in actor_ids:
                    operation.clear()
                    operation.update({
                        "type": "no_abstract_change",
                        "reason": "Skipped intent proposal because the character id was not known.",
                    })

            elif operation_type == "update_intent":
                cls._resolve_event_reference(
                    operation,
                    field_name="event_id",
                    event_ids=event_ids,
                    event_ids_by_name=event_ids_by_name,
                )

            elif operation_type == "link_turn_to_event":
                cls._resolve_event_reference(
                    operation,
                    field_name="event_id",
                    event_ids=event_ids,
                    event_ids_by_name=event_ids_by_name,
                )

        return MemorySummaryProposal.model_validate(normalized)

    @classmethod
    def _resolve_character_list(cls,
                                entries: list[dict],
                                *,
                                actor_ids: set[str],
                                actor_ids_by_name: dict[str, str],
                                ):
        for entry in entries:
            if isinstance(entry, dict):
                cls._resolve_character_id(
                    entry,
                    actor_ids=actor_ids,
                    actor_ids_by_name=actor_ids_by_name,
                )

    @staticmethod
    def _resolve_character_id(entry: dict,
                              *,
                              actor_ids: set[str],
                              actor_ids_by_name: dict[str, str],
                              ):
        character_id = entry.get("character_id")
        if not isinstance(character_id, str) or character_id in actor_ids:
            return

        normalized_id = actor_ids_by_name.get(character_id.strip().lower())
        if normalized_id:
            entry["character_id"] = normalized_id

    @staticmethod
    def _resolve_event_reference(entry: dict,
                                 *,
                                 field_name: str,
                                 event_ids: set[str | None],
                                 event_ids_by_name: dict[str, str | None],
                                 ):
        event_id = entry.get(field_name)
        if not isinstance(event_id, str) or event_id in event_ids:
            return

        normalized_id = event_ids_by_name.get(event_id.strip().lower())
        if normalized_id:
            entry[field_name] = normalized_id
