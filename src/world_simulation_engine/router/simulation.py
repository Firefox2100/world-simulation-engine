import json
from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType, GraphStateSnapshotType, SimulationAuditCategory, \
    SimulationGenerationRequestType
from world_simulation_engine.model import GenerationJob, GraphStateSnapshot, Simulation, SimulationAuditEvent
from world_simulation_engine.component.simulator.world_simulator import WorldSimulatorState
from world_simulation_engine.component.simulator.input_interpreter import InputInterpreter
from .utils import db_dep, simulator_dep


simulation_router = APIRouter(
    tags=["Simulation"],
)


class SimulationUpdate(BaseModel):
    """
    DTO model for updating a simulation
    """
    name: Optional[str] = Field(
        None,
        description="Name of the simulation",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the simulation",
    )
    current_time: Optional[datetime] = Field(
        None,
        description="Current time of the simulation",
    )
    emotion_enabled: Optional[bool] = Field(
        None,
        description="Enable or disable quantitative emotion updates and prompt context.",
    )


class SimulationInput(BaseModel):
    """
    DTO model for starting a simulation generation
    """

    request_type: SimulationGenerationRequestType = Field(
        SimulationGenerationRequestType.USER_INPUT_GENERATION,
        description="What kind of simulator graph run to start.",
    )
    user_input: Optional[str] = Field(
        None,
        description="Required for user_input_generation. Must be empty for continue_generation and regeneration.",
    )
    regenerate_turn_sequence: Optional[int] = Field(
        None,
        ge=0,
        description="For regeneration, the character-round turn sequence to regenerate.",
    )
    client_request_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Optional client-generated idempotency key scoped to this simulation.",
    )


class SimulationRun(BaseModel):
    thread_id: str = Field(..., description="The simulator graph thread id")


def _sse_event(*, data: Any, event: str | None = None, event_id: str | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    if event is not None:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, default=_json_default)}")
    return "\n".join(lines) + "\n\n"


def _json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@simulation_router.get("/simulations", response_model=list[Simulation])
async def list_simulations(db: db_dep,
                           author_id: Optional[str] = Query(None, description="Optionally filter by author"),
                           world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                           limit: Optional[int] = Query(None, ge=1, description="Maximum number of simulations to return"),
                           skip: int = Query(0, ge=0, description="Number of simulations to skip"),
                           ):
    return await db.simulation.list_simulations(
        author_id=author_id,
        world_id=world_id,
        limit=limit,
        skip=skip,
    )


@simulation_router.get("/simulations/{simulation_id}", response_model=Simulation)
async def get_simulation(simulation_id: str, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return simulation


@simulation_router.get(
    "/simulations/{simulation_id}/audit-events",
    response_model=list[SimulationAuditEvent],
)
async def list_simulation_audit_events(
        simulation_id: str,
        db: db_dep,
        run_id: str | None = Query(None),
        turn_id: str | None = Query(None),
        category: SimulationAuditCategory | None = Query(None),
        actor_id: str | None = Query(None),
        limit: int = Query(200, ge=1, le=500),
        skip: int = Query(0, ge=0),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    return await db.simulation_audit.list_events(
        simulation_id,
        run_id=run_id,
        turn_id=turn_id,
        category=category,
        actor_id=actor_id,
        limit=limit,
        skip=skip,
    )


@simulation_router.get("/simulations/{simulation_id}/graph-snapshots", response_model=list[GraphStateSnapshot])
async def list_graph_state_snapshots(simulation_id: str, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return await db.graph_state_snapshot.list_snapshots(simulation_id)


@simulation_router.get(
    "/simulations/{simulation_id}/graph-snapshots/{snapshot_type}",
    response_model=GraphStateSnapshot,
)
async def get_graph_state_snapshot(
        simulation_id: str,
        snapshot_type: GraphStateSnapshotType,
        db: db_dep,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    snapshot = await db.graph_state_snapshot.get_snapshot(
        simulation_id=simulation_id,
        type=snapshot_type,
    )
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph state snapshot {snapshot_type} for simulation {simulation_id} not found",
        )

    return snapshot


@simulation_router.post("/simulations/{simulation_id}/input", response_model=SimulationRun)
async def start_simulation_input(
        simulation_id: str,
        simulation_input: SimulationInput,
        db: db_dep,
        simulator: simulator_dep,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    world = await db.world.get_world_by_simulation(simulation_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World for simulation {simulation_id} not found",
        )

    if (
            simulation_input.request_type == SimulationGenerationRequestType.USER_INPUT_GENERATION
            and simulation_input.user_input is not None
    ):
        try:
            InputInterpreter.validate_markup(simulation_input.user_input)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    try:
        thread_id = await simulator.start_generation(
            WorldSimulatorState(
                world=world,
                simulation=simulation,
                user_input=simulation_input.user_input,
                request_type=simulation_input.request_type,
            ),
            request_type=simulation_input.request_type,
            regenerate_turn_sequence=simulation_input.regenerate_turn_sequence,
            client_request_id=simulation_input.client_request_id,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SimulationRun(thread_id=thread_id)


@simulation_router.get(
    "/simulations/{simulation_id}/runs/{thread_id}/status",
    response_model=GenerationJob,
)
async def get_simulation_run_status(
        simulation_id: str,
        thread_id: str,
        db: db_dep,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    job = await db.generation_job.get_job(
        job_id=thread_id,
        simulation_id=simulation_id,
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation run {thread_id} not found",
        )
    return job


@simulation_router.get("/simulations/{simulation_id}/runs/{thread_id}")
async def stream_simulation_run(
        simulation_id: str,
        thread_id: str,
        request: Request,
        db: db_dep,
        simulator: simulator_dep,
):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    async def event_stream():
        last_event_id = request.headers.get("last-event-id")
        if last_event_id and simulator.is_generation_running(thread_id):
            yield _sse_event(
                event="status",
                data={
                    "code": "still_generating",
                    "message": "Generation is still running; wait for completion and fetch final state.",
                    "thread_id": thread_id,
                },
            )
            return

        try:
            event_index = 0
            async for chunk in simulator.stream_generation(thread_id):
                if await request.is_disconnected():
                    return

                yield _sse_event(
                    event="chunk",
                    event_id=str(event_index),
                    data=chunk,
                )
                event_index += 1
            yield _sse_event(
                event="done",
                data={
                    "code": "done",
                    "thread_id": thread_id,
                },
            )
        except KeyError:
            yield _sse_event(
                event="status",
                data={
                    "code": "not_found",
                    "message": f"Generation thread {thread_id} not found.",
                    "thread_id": thread_id,
                },
            )
        except Exception as exc:
            yield _sse_event(
                event="error",
                data={
                    "code": "generation_failed",
                    "message": str(exc),
                    "thread_id": thread_id,
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@simulation_router.patch("/simulations/{simulation_id}", response_model=Simulation)
async def update_simulation(simulation_id: str, simulation_update: SimulationUpdate, db: db_dep):
    simulation = await db.simulation.update_simulation(
        simulation_id,
        simulation_update.model_dump(exclude_unset=True),
    )
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return simulation


@simulation_router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation(simulation_id: str, db: db_dep):
    deleted = await db.simulation.delete_simulation(simulation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@simulation_router.post("/worlds/{world_id}/simulations", response_model=Simulation)
async def create_simulation(world_id: str, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    simulation = Simulation(
        name=world.name,
        description=world.description,
        current_time=world.starting_time,
    )
    created_simulation = await db.simulation.create_simulation(simulation, world_id)
    if not created_simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    for component in ComponentType:
        chat_config = await db.config.get_chat_by_source(world_id, component)
        if chat_config:
            await db.config.link_chat(created_simulation.id, chat_config.id, component)

        embed_config = await db.config.get_embed_by_source(world_id, component)
        if embed_config:
            await db.config.link_embed(created_simulation.id, embed_config.id, component)

    await db.media.copy_prompt_media_relationships(
        world_id=world_id,
        simulation_id=created_simulation.id,
    )
    await db.media.copy_workflow_media_relationships(
        world_id=world_id,
        simulation_id=created_simulation.id,
    )

    _, turn_pairs = await db.turn.copy_turns(
        world_id,
        created_simulation.id,
    )
    _, location_pairs, landmark_pairs = await db.location.copy_locations(
        world_id,
        created_simulation.id,
    )
    _, character_pairs = await db.character.copy_characters(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        landmark_pairs=landmark_pairs,
        return_pairs=True,
    )
    _, background_character_pairs = await db.character.copy_background_characters(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        landmark_pairs=landmark_pairs,
    )
    await db.turn_presentation.copy_presentations(
        turn_pairs=turn_pairs,
        entity_pairs=[*character_pairs, *background_character_pairs],
        copied_at=simulation.current_time,
    )
    _, stack_pairs = await db.item.copy_stacks(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        entity_pairs=character_pairs + background_character_pairs,
    )
    _, equipment_pairs = await db.equipment.copy_equipment(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        entity_pairs=character_pairs + background_character_pairs,
    )
    _, container_pairs = await db.container.copy_containers(
        world_id,
        created_simulation.id,
        location_pairs=location_pairs,
        entity_pairs=character_pairs + background_character_pairs,
        stack_pairs=stack_pairs,
        equipment_pairs=equipment_pairs,
    )
    _, event_pairs = await db.event.copy_events(
        turn_pairs=turn_pairs,
        character_pairs=character_pairs,
    )
    await db.intent.copy_intents(
        character_pairs=character_pairs,
        event_pairs=event_pairs,
    )
    await db.entity_relationship.copy_relationships(
        source_id=world_id,
        target_simulation_id=created_simulation.id,
        entity_pairs=(
            location_pairs
            + landmark_pairs
            + character_pairs
            + background_character_pairs
            + stack_pairs
            + equipment_pairs
            + container_pairs
        ),
        copied_at=created_simulation.current_time,
    )

    return created_simulation
