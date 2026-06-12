import asyncio
import json
import operator
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Annotated
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from world_simulation_engine.model import Simulation, SimulationState, LlmConnectionProfile, DirectorOutput, \
    PendingGeneratedProposal, CharacterBriefing, BriefingOutput, CharacterActionOutput, CharacterInventory, \
    ResolverOutput
from world_simulation_engine.service import DatabaseService, EmbeddingService, DirectorAgent, WorldGeneratorAgent, \
    MemoryAgent, CharacterAgent, ResolverAgent
from .world_entry_recaller import WorldEntryRecaller


class ConnectionProfileCache(BaseModel):
    director: LlmConnectionProfile | None = None
    memory: LlmConnectionProfile | None = None
    character: LlmConnectionProfile | None = None
    resolver: LlmConnectionProfile | None = None
    world_generator: LlmConnectionProfile | None = None

    embedding: LlmConnectionProfile | None = None


class TurnGeneratorState(BaseModel):
    run_id: str
    simulation_id: int
    user_input: str | None = None

    simulation: Simulation | None = None
    state: SimulationState | None = None
    connection_profiles: ConnectionProfileCache = Field(default_factory=ConnectionProfileCache)

    director_output: DirectorOutput | None = None
    generated_proposals: list[PendingGeneratedProposal] | None = None
    briefing_output: BriefingOutput | None = None
    character_action_outputs: Annotated[
        list[CharacterActionOutput],
        operator.add,
    ] = Field(default_factory=list)
    resolver_output: ResolverOutput | None = None


class CharacterActionState(BaseModel):
    user_input: str | None
    simulation: Simulation | None
    state: SimulationState | None
    connection_profiles: ConnectionProfileCache
    generated_proposals: list[PendingGeneratedProposal] | None = None
    briefing: CharacterBriefing


@dataclass
class WorkflowRunHandle:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


class TurnGenerator:
    def __init__(self,
                 database_service: DatabaseService,
                 ):
        self._db = database_service

    async def load_simulation(self, state: TurnGeneratorState) -> dict:
        simulation = await self._db.simulation.get(state.simulation_id)
        simulation_state = await self._db.state.get(state.simulation_id)

        if simulation is None or simulation_state is None:
            raise ValueError(f"Simulation {state.simulation_id} not found")

        connection_ids = {
            simulation.agent_preset.director.backend_configuration.connection,
            simulation.agent_preset.memory.backend_configuration.connection,
            simulation.agent_preset.character.backend_configuration.connection,
            simulation.agent_preset.world_generator.backend_configuration.connection,
            simulation.embedding_profile.connection,
        }

        connections = {}
        for connection_id in connection_ids:
            if connection_id is None:
                raise ValueError("Not all connections are configured")

            connection = await self._db.connection.llm.get(connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")

            connections[connection_id] = connection

        return {
            "simulation": simulation,
            "state": simulation_state,
            "connection_profiles": ConnectionProfileCache(
                director=connections[simulation.agent_preset.director.backend_configuration.connection],
                memory=connections[simulation.agent_preset.memory.backend_configuration.connection],
                character=connections[simulation.agent_preset.character.backend_configuration.connection],
                world_generator=connections[simulation.agent_preset.world_generator.backend_configuration.connection],
                embedding=connections[simulation.embedding_profile.connection],
            ),
        }

    async def director_planning(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.director is None:
            raise RuntimeError("Director connection profile not loaded")
        director_agent = DirectorAgent(
            profile=state.simulation.agent_preset.director,
            connection=state.connection_profiles.director,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")
        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )
        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        if state.connection_profiles.world_generator is None:
            raise RuntimeError("World generator connection profile not loaded")
        generator = WorldGeneratorAgent(
            profile=state.simulation.agent_preset.world_generator,
            connection=state.connection_profiles.world_generator,
        )

        present_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            location=state.state.scene,
        )
        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError("Current location does not exist")
        all_locations = await self._db.location.list(simulation_id=state.simulation_id)
        existing_items = await self._db.item.list(simulation_id=state.simulation_id)
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation_id)
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [c.id for c in present_characters],
        )
        tasks = await self._db.task.list(
            character_ids=[c.id for c in present_characters],
        )

        generator_tools = generator.get_tools(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=all_locations,
            existing_entities=current_location.entities,
            existing_items=existing_items,
            entity_types=state.simulation.data_preset.entity_types.keys(),
        )

        if state.user_input:
            recalled_entries = await recaller.recall(
                query=state.user_input,
                entries=world_entries,
                language=state.simulation.language,
            )
        elif last_record:
            recalled_entries = await recaller.recall(
                query=last_record.narration,
                entries=world_entries,
                language=state.simulation.language
            )
        else:
            recalled_entries = await recaller.recall(
                query=None,
                entries=world_entries,
                language=state.simulation.language
            )

        output, proposals = await director_agent.plan_turn(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            relevant_tasks=tasks,
            recalled_world_entries=recalled_entries,
            generation_tools=generator_tools,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
        )

        return {
            "director_output": output,
            "generated_proposals": proposals,
        }

    async def memory_briefing(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.memory is None:
            raise RuntimeError("Memory connection profile not loaded")
        memory_agent = MemoryAgent(
            profile=state.simulation.agent_preset.memory,
            connection=state.connection_profiles.memory,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")
        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )
        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        if state.director_output is None:
            raise RuntimeError("Director output not generated")

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError("Current location does not exist")
        active_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            character_ids=[a.character_id for a in state.director_output.activations]
        )
        tasks = await self._db.task.list(
            character_ids=[c.id for c in active_characters],
            private=False,
        )
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation_id)
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [c.id for c in active_characters],
        )
        if state.user_input:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus + " " + state.user_input,
                entries=world_entries,
                language=state.simulation.language,
            )
        elif last_record:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus + " " + last_record.narration,
                entries=world_entries,
                language=state.simulation.language
            )
        else:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus,
                entries=world_entries,
                language=state.simulation.language
            )

        result = await memory_agent.build_briefings(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=active_characters,
            tasks=tasks,
            world_entries=recalled_entries,
            pending_generated_proposals=state.generated_proposals,
            user_input=state.user_input,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
        )

        return {
            "briefing_output": result,
        }

    async def character_action(self, state: CharacterActionState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.character is None:
            raise RuntimeError("Memory connection profile not loaded")
        character_agent = CharacterAgent(
            profile=state.simulation.agent_preset.character,
            connection=state.connection_profiles.character,
        )

        character = await self._db.character.get(state.briefing.character_id)
        if not character:
            raise ValueError(f"Character {state.briefing.character_id} not found")
        current_location = await self._db.location.get(character.location)
        if not current_location:
            raise ValueError(f"Current location {character.location} does not exist")
        present_characters = await self._db.character.list(location=character.location)
        present_characters = [c for c in present_characters if c.id != character.id]
        tasks = await self._db.task.list(
            task_ids=state.briefing.relevant_task_ids,
        )
        world_entries = await self._db.entry.list(
            entry_ids=state.briefing.relevant_world_entry_ids,
        )
        items = await self._db.item.list(character_id=character.id)
        equipments = await self._db.equipment.list(character_id=character.id)
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)

        result = await character_agent.generate_action(
            character=character,
            briefing=state.briefing,
            current_location=current_location,
            visible_characters=present_characters,
            tasks=tasks,
            world_entries=world_entries,
            inventory=items,
            equipments=equipments,
            proposals=state.generated_proposals or [],
            user_input=state.user_input,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
        )

        return {
            "character_action_outputs": [result]
        }

    async def resolve_character_actions(self, state: TurnGeneratorState):
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if not state.briefing_output:
            raise RuntimeError("Briefing output is not generated")
        if not state.character_action_outputs:
            raise RuntimeError("Character action outputs is not generated")

        if state.connection_profiles.resolver is None:
            raise RuntimeError("Memory connection profile not loaded")
        resolver_agent = ResolverAgent(
            profile=state.simulation.agent_preset.resolver,
            connection=state.connection_profiles.resolver,
        )
        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")
        characters = await self._db.character.list(
            character_ids=[a.character_id for a in state.character_action_outputs]
        )
        inventory = {}
        for character in characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)
            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )
        world_entry_ids = set()
        for b in state.briefing_output.briefings:
            world_entry_ids |= set(b.relevant_world_entry_ids)
        world_entries = await self._db.entry.list(entry_ids=list(world_entry_ids))
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)

        result = await resolver_agent.resolve_character_actions(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=characters,
            character_actions=state.character_action_outputs,
            proposals=state.generated_proposals or [],
            inventory=inventory,
            world_entries=world_entries,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
        )
        return {
            "resolver_output": result,
        }

    def route_after_director(self, state: TurnGeneratorState) -> Literal["memory"]:
        if not state.director_output:
            raise RuntimeError("Director output not generated")

        if not state.director_output.wait_for_user:
            return "memory"

    def route_after_briefing(self, state: TurnGeneratorState):
        if not state.briefing_output:
            raise RuntimeError("Briefing output not generated")

        return [
            Send(
                "character_action",
                CharacterActionState(
                    simulation=state.simulation,
                    state=state.state,
                    connection_profiles=state.connection_profiles,
                    user_input=state.user_input,
                    briefing=briefing
                ),
            )
            for briefing in state.briefing_output.briefings
        ]

    def build_graph(self):
        graph = StateGraph(TurnGeneratorState)

        graph.add_node("load_simulation", self.load_simulation)
        graph.add_node("director_planning", self.director_planning)
        graph.add_node("memory_briefing", self.memory_briefing)
        graph.add_node("character_action", self.character_action)
        graph.add_node("resolve_character_actions", self.resolve_character_actions)

        graph.add_edge(START, "load_simulation")
        graph.add_edge("load_simulation", "director_planning")
        graph.add_conditional_edges(
            "director_planning",
            self.route_after_director,
            {
                "memory": "memory_briefing",
            }
        )
        graph.add_conditional_edges(
            "memory_briefing",
            self.route_after_briefing,
        )
        graph.add_edge("character_action", "resolve_character_actions")

        return graph.compile()


class WorkflowRunner:
    def __init__(self, graph):
        self._graph = graph
        self._runs: dict[str, WorkflowRunHandle] = {}

    @staticmethod
    def _format_sse(event: str, data: Any):
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def _run_graph(self,
                         run_id: str,
                         input_data: dict[str, Any],
                         handle: WorkflowRunHandle
                         ):
        try:
            async for mode, chunk in self._graph.astream(
                input_data,
                config={
                    "configurable": {
                        "thread_id": run_id,
                    },
                },
                stream_mode=["updates", "messages"],
            ):
                if mode == "updates":
                    await handle.queue.put({
                        "event": "stage_update",
                        "data": "chunk",
                    })

                elif mode == "messages":
                    await handle.queue.put({
                        "event": "token",
                        "data": chunk,
                    })

            await handle.queue.put({
                "event": "done",
                "data": {"run_id": run_id},
            })
        except asyncio.CancelledError:
            await handle.queue.put({
                "event": "cancelled",
                "data": {"run_id": run_id},
            })
        except Exception as e:
            await handle.queue.put({
                "event": "error",
                "data": {"message": str(e)},
            })
        finally:
            handle.done.set()

    async def start(self,
                    input_data: dict[str, Any],
                    ) -> str:
        run_id = str(uuid4())
        handle = WorkflowRunHandle()
        self._runs[run_id] = handle

        handle.task = asyncio.create_task(
            self._run_graph(
                run_id=run_id,
                input_data=input_data,
                handle=handle,
            )
        )

        return run_id

    async def events(self, run_id: str) -> AsyncIterator[str]:
        handle = self._runs[run_id]

        while True:
            try:
                event = await asyncio.wait_for(handle.queue.get(), timeout=55),
                yield self._format_sse(
                    event=event["event"],
                    data=event["data"],
                )

                if event["event"] in {"done", "error"}:
                    break
            except asyncio.TimeoutError:
                yield self._format_sse(
                    event="ping",
                    data={"message": "ping"},
                )
