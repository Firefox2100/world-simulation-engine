import asyncio
import json
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from langgraph.constants import START
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field

from world_simulation_engine.model import Simulation, SimulationState, LlmConnectionProfile, DirectorOutput, \
    PendingGeneratedProposal
from world_simulation_engine.service import DatabaseService, EmbeddingService, DirectorAgent, WorldGeneratorAgent
from .world_entry_recaller import WorldEntryRecaller


class ConnectionProfileCache(BaseModel):
    director: LlmConnectionProfile | None = None
    memory: LlmConnectionProfile | None = None
    character: LlmConnectionProfile | None = None
    world_generator: LlmConnectionProfile | None = None


class TurnGeneratorState(BaseModel):
    run_id: str
    simulation_id: int
    user_input: str | None = None

    simulation: Simulation | None = None
    state: SimulationState | None = None
    connection_profiles: ConnectionProfileCache = Field(default_factory=ConnectionProfileCache)

    director_output: DirectorOutput | None = None
    generated_proposals: PendingGeneratedProposal | None = None


@dataclass
class WorkflowRunHandle:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


class TurnGenerator:
    def __init__(self,
                 database_service: DatabaseService,
                 embedding_service: EmbeddingService,
                 ):
        self._db = database_service
        self._embedding = embedding_service

    async def load_simulation(self, state: TurnGeneratorState) -> dict:
        simulation = await self._db.simulation.get(state.simulation_id)
        simulation_state = await self._db.state.get(state.simulation_id)

        return {
            "simulation": simulation,
            "state": simulation_state,
        }

    async def director_planning(self, state: TurnGeneratorState) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.director is None:
            if state.simulation.agent_preset.director.backend_configuration.connection is None:
                raise ValueError("Director connection is not configured.")
            state.connection_profiles.director = await self._db.connection.llm.get(
                state.simulation.agent_preset.director.backend_configuration.connection
            )
            if state.connection_profiles.director is None:
                raise ValueError("Director connection configuration not found")
        director_agent = DirectorAgent(
            profile=state.simulation.agent_preset.director,
            connection=state.connection_profiles.director,
        )

        if state.connection_profiles.world_generator is None:
            if state.simulation.agent_preset.world_generator.backend_configuration.connection is None:
                raise ValueError("World generator connection is not configured.")
            state.connection_profiles.world_generator = await self._db.connection.llm.get(
                state.simulation.agent_preset.world_generator.backend_configuration.connection
            )
            if state.connection_profiles.world_generator is None:
                raise ValueError("World generator connection configuration not found")
        generator = WorldGeneratorAgent(
            profile=state.simulation.agent_preset.world_generator,
            connection=state.connection_profiles.world_generator,
        )
        recaller = WorldEntryRecaller(
            embedding_service=self._embedding,
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

        recalled_entries = await recaller.recall(
            query=state.user_input,
            entries=filtered_entries,
            language=example_simulation.language,
        )

        output, proposals = await director_agent.plan_turn(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            relevant_tasks=filtered_tasks,
            recalled_world_entries=recalled_entries,
            generation_tools=generator_tools,
            last_narration="",
            previous_resolver_notes="",
        )

        return {
            "director_output": output,
            "generated_proposals": proposals,
        }

    def build_graph(self):
        graph = StateGraph(TurnGeneratorState)

        graph.add_node("load_simulation", self.load_simulation)
        graph.add_node("director_planning", self.director_planning)

        graph.add_edge(START, "load_simulation")
        graph.add_edge("load_simulation", "director_planning")

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
