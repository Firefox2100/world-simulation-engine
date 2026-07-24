from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import (
    NarrationProposal,
    PresentedTurn,
    PresentationBlockType,
    PresentationCompletion,
    SpeechBlock,
    Turn,
    TurnPresentationBlock,
    TurnPresentationRendering,
)
from .utils import db_dep


turn_router = APIRouter(
    tags=["Turn"],
)


class TurnCreate(BaseModel):
    sequence: int = Field(..., ge=1, description="The sequence number of the turn, starting at 1")
    type: TurnType = Field(..., description="The type of the turn")
    content: str = Field(..., min_length=1, description="The final, visible content of this turn")
    start_time: datetime = Field(..., description="The start time of the turn")


class PresentationBlockWrite(BaseModel):
    sequence: int = Field(ge=0)
    type: PresentationBlockType
    text: str | None = None
    speaker_id: str | None = None
    speaker_name: str | None = None
    media_id: str | None = None
    completion: PresentationCompletion = PresentationCompletion.COMPLETE


class PresentationRenderingWrite(BaseModel):
    locale: str | None = None
    blocks: list[PresentationBlockWrite] = Field(default_factory=list, max_length=200)


def _legacy_presentation(turn: Turn) -> list[TurnPresentationBlock]:
    """Adapt old canonical content on the server; clients never parse it."""
    now = turn.start_time
    if turn.type == TurnType.USER_INPUT:
        return [TurnPresentationBlock(
            turn_id=turn.id,
            sequence=0,
            type=PresentationBlockType.ACTION,
            text=turn.content,
            completion=PresentationCompletion.COMPLETE,
            created_at=now,
            updated_at=now,
        )]
    try:
        narration = NarrationProposal.model_validate_json(turn.content)
    except (ValueError, TypeError):
        narration = None
    if narration is not None:
        return [
            TurnPresentationBlock(
                turn_id=turn.id,
                sequence=sequence,
                type=(
                    PresentationBlockType.SPEECH
                    if isinstance(block, SpeechBlock)
                    else PresentationBlockType.NARRATION
                ),
                text=block.text,
                speaker_id=block.character_id if isinstance(block, SpeechBlock) else None,
                speaker_name=block.character_name if isinstance(block, SpeechBlock) else None,
                completion=PresentationCompletion.COMPLETE,
                created_at=now,
                updated_at=now,
            )
            for sequence, block in enumerate(narration.blocks)
        ]
    return [TurnPresentationBlock(
        turn_id=turn.id,
        sequence=0,
        type=PresentationBlockType.NARRATION,
        text=turn.content,
        completion=PresentationCompletion.COMPLETE,
        created_at=now,
        updated_at=now,
    )]


async def _present_turns(
        turns: list[Turn],
        db,
        *,
        rendering_id: str,
        locale: str | None,
        include_incomplete: bool = False,
) -> list[PresentedTurn]:
    stored = await db.turn_presentation.list_blocks(
        turn_ids=[turn.id for turn in turns],
        rendering_id=rendering_id,
        locale=locale,
        include_incomplete=True,
    )
    by_turn: dict[str, list[TurnPresentationBlock]] = {}
    for block in stored:
        by_turn.setdefault(block.turn_id, []).append(block)
    return [
        PresentedTurn(
            turn=turn,
            rendering_id=rendering_id,
            locale=locale,
            presentation_blocks=(
                by_turn.get(turn.id, [])
                if include_incomplete or all(
                    block.completion == PresentationCompletion.COMPLETE
                    for block in by_turn.get(turn.id, [])
                )
                else []
            ) or _legacy_presentation(turn),
        )
        for turn in turns
    ]


@turn_router.get("/turns", response_model=list[Turn])
async def list_turns(db: db_dep,
                     simulation_id: str = Query(
                         ...,
                         description="The simulation id of the simulation to get turns from",
                     ),
                     limit: int = Query(
                         10,
                         description="Maximum turns to return, default to 10",
                         ge=1,
                     ),
                     skip: int = Query(
                         0,
                         description="How many turns to skip, default to 0",
                         ge=0,
                     )
                     ):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return await db.turn.list_turns(
        source_id=simulation_id,
        limit=limit,
        skip=skip,
    )


@turn_router.get("/turn-presentations", response_model=list[PresentedTurn])
async def list_turn_presentations(
        db: db_dep,
        simulation_id: str,
        rendering_id: str = "default",
        locale: str | None = None,
        include_incomplete: bool = False,
        limit: int = Query(10, ge=1),
        skip: int = Query(0, ge=0),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    turns = await db.turn.list_turns(source_id=simulation_id, limit=limit, skip=skip)
    return await _present_turns(
        turns,
        db,
        rendering_id=rendering_id,
        locale=locale,
        include_incomplete=include_incomplete,
    )


@turn_router.get("/turns/{turn_id}/presentation", response_model=PresentedTurn)
async def get_turn_presentation(
        turn_id: str,
        db: db_dep,
        rendering_id: str = "default",
        locale: str | None = None,
        include_incomplete: bool = False,
):
    turn = await db.turn.get_turn(turn_id)
    if not turn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Turn {turn_id} not found")
    return (await _present_turns(
        [turn],
        db,
        rendering_id=rendering_id,
        locale=locale,
        include_incomplete=include_incomplete,
    ))[0]


@turn_router.put(
    "/turns/{turn_id}/presentation/{rendering_id}",
    response_model=TurnPresentationRendering,
)
async def replace_turn_presentation(
        turn_id: str,
        rendering_id: str,
        payload: PresentationRenderingWrite,
        db: db_dep,
):
    turn = await db.turn.get_turn(turn_id)
    if not turn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Turn {turn_id} not found")
    now = datetime.now(tz=turn.start_time.tzinfo)
    rendering = TurnPresentationRendering(
        turn_id=turn_id,
        rendering_id=rendering_id,
        locale=payload.locale,
        blocks=[
            TurnPresentationBlock(
                turn_id=turn_id,
                rendering_id=rendering_id,
                locale=payload.locale,
                created_at=now,
                updated_at=now,
                **block.model_dump(),
            )
            for block in payload.blocks
        ],
    )
    stored = await db.turn_presentation.replace_rendering(rendering)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not replace presentation")
    return stored


@turn_router.post("/worlds/{world_id}/turns", response_model=Turn)
async def create_world_turn(world_id: str, turn_data: TurnCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    latest_turns = await db.turn.list_turns(source_id=world_id, limit=1)
    previous_turn = latest_turns[0] if latest_turns else None
    expected_sequence = previous_turn.sequence + 1 if previous_turn else 1
    if turn_data.sequence != expected_sequence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Turn sequence must be {expected_sequence}",
        )

    try:
        return await db.turn.create_turn(
            Turn(**turn_data.model_dump()),
            world_id,
            previous_turn_id=previous_turn.id if previous_turn else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@turn_router.get("/turns/{turn_id}", response_model=Turn)
async def get_turn(turn_id: str, db: db_dep):
    turn = await db.turn.get_turn(turn_id)
    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turn {turn_id} not found",
        )

    return turn


@turn_router.get("/simulations/{simulation_id}/turns/{sequence}", response_model=Turn)
async def get_turn_by_sequence(simulation_id: str, sequence: int, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    turn = await db.turn.get_turn_by_sequence(simulation_id, sequence)
    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turn {sequence} not found in simulation {simulation_id}",
        )

    return turn
