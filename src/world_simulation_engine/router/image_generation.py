from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from world_simulation_engine.component.image_generator import CharacterImageGenerator, \
    CharacterPortraitImageGenerator, ItemImageGenerator, LocationImageGenerator, SceneImageGenerator
from world_simulation_engine.model import GeneratedImageMediaFile
from .utils import db_dep, prompt_loader_dep, storage_dep, workflow_loader_dep


image_generation_router = APIRouter(
    tags=["Image Generation"],
)


class GenerateStateImageRequest(BaseModel):
    source_id: str = Field(
        ...,
        description="World or Simulation id used to resolve image model, chat model, and workflow configuration",
    )


class GenerateTurnGroundedImageRequest(BaseModel):
    turn_id: Optional[str] = Field(
        None,
        description="Optional turn to use for pose/relationship context and to link via GENERATES_IMAGE",
    )


async def _validate_source(source_id: str, db: db_dep) -> None:
    if await db.world.get_world(source_id):
        return
    if await db.simulation.get_simulation(source_id):
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"World or simulation {source_id} not found",
    )


async def _validate_simulation(simulation_id: str, db: db_dep) -> None:
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@image_generation_router.post("/characters/{character_id}/generate-image/state", response_model=GeneratedImageMediaFile)
async def generate_character_state_image(
        character_id: str,
        request: GenerateStateImageRequest,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
):
    await _validate_source(request.source_id, db)
    if not await db.character.get_character(character_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )

    generator = CharacterImageGenerator(
        database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
    )
    try:
        return await generator.generate_as_cover_image(source_id=request.source_id, entity_id=character_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@image_generation_router.post("/locations/{location_id}/generate-image/state", response_model=GeneratedImageMediaFile)
async def generate_location_state_image(
        location_id: str,
        request: GenerateStateImageRequest,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
):
    await _validate_source(request.source_id, db)
    if not await db.location.get_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )

    generator = LocationImageGenerator(
        database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
    )
    try:
        return await generator.generate_as_cover_image(source_id=request.source_id, entity_id=location_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@image_generation_router.post("/items/{item_id}/generate-image/state", response_model=GeneratedImageMediaFile)
async def generate_item_state_image(
        item_id: str,
        request: GenerateStateImageRequest,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
):
    await _validate_source(request.source_id, db)
    if not await db.item.get_item(item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )

    generator = ItemImageGenerator(
        database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
    )
    try:
        return await generator.generate_as_cover_image(source_id=request.source_id, entity_id=item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@image_generation_router.post(
    "/simulations/{simulation_id}/characters/{character_id}/generate-image/portrait",
    response_model=GeneratedImageMediaFile,
)
async def generate_character_portrait_image(
        simulation_id: str,
        character_id: str,
        request: GenerateTurnGroundedImageRequest,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
):
    await _validate_simulation(simulation_id, db)
    if not await db.character.get_character(character_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )
    if request.turn_id and not await db.turn.get_turn(request.turn_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turn {request.turn_id} not found",
        )

    generator = CharacterPortraitImageGenerator(
        database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
    )
    try:
        return await generator.generate_portrait(
            simulation_id=simulation_id,
            character_id=character_id,
            turn_id=request.turn_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@image_generation_router.post(
    "/simulations/{simulation_id}/locations/{location_id}/generate-image/scene",
    response_model=GeneratedImageMediaFile,
)
async def generate_scene_image(
        simulation_id: str,
        location_id: str,
        request: GenerateTurnGroundedImageRequest,
        db: db_dep,
        storage: storage_dep,
        workflow_loader: workflow_loader_dep,
        prompt_loader: prompt_loader_dep,
):
    await _validate_simulation(simulation_id, db)
    if not await db.location.get_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found",
        )
    if request.turn_id and not await db.turn.get_turn(request.turn_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turn {request.turn_id} not found",
        )

    generator = SceneImageGenerator(
        database=db, storage=storage, workflow_loader=workflow_loader, prompt_loader=prompt_loader,
    )
    try:
        return await generator.generate_scene(
            simulation_id=simulation_id,
            location_id=location_id,
            turn_id=request.turn_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
