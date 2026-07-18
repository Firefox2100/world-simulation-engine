from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import MediaType
from world_simulation_engine.model import MediaFile
from .utils import db_dep, storage_dep


media_router = APIRouter(
    tags=["Media"],
)


class CoverImageUpdate(BaseModel):
    media_id: str = Field(..., description="Media file to use as the cover image")


async def _get_source(source_type: str, source_id: str, db: db_dep):
    if source_type == "World":
        return await db.world.get_world(source_id)
    if source_type == "Simulation":
        return await db.simulation.get_simulation(source_id)
    if source_type == "Character":
        return await db.character.get_character(source_id)
    if source_type == "BackgroundCharacter":
        return await db.character.get_background_character(source_id)
    if source_type == "Location":
        return await db.location.get_location(source_id)
    if source_type == "Landmark":
        return await db.location.get_landmark(source_id)
    if source_type == "Item":
        return await db.item.get_item(source_id)
    if source_type == "ItemStack":
        return await db.item.get_stack(source_id)
    if source_type == "Equipment":
        return await db.equipment.get_equipment(source_id)
    if source_type == "Container":
        return await db.container.get_container(source_id)

    raise ValueError(f"Unsupported cover image source type {source_type}")


def _source_detail_name(source_type: str) -> str:
    if source_type == "ItemStack":
        return "stack"
    if source_type == "BackgroundCharacter":
        return "background character"

    return source_type.lower()


async def _upload_chunks(file: UploadFile):
    while chunk := await file.read(1024 * 1024):
        yield chunk


def _filename_without_suffix(upload: UploadFile, filename: str | None) -> str:
    if filename:
        return filename

    if upload.filename:
        return Path(upload.filename).stem

    return "media"


def _download_filename(media: MediaFile) -> str:
    if media.type == MediaType.PNG:
        return f"{media.filename}.png"

    return media.filename


async def _get_media_file_response(media_id: str,
                                   db: db_dep,
                                   storage: storage_dep,
                                   ) -> FileResponse:
    media = await db.media.get_media(media_id)
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    if not await storage.exists(media.hash):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File for media {media_id} not found",
        )

    return FileResponse(
        path=storage.path_for(media.hash),
        media_type=media.type,
        filename=_download_filename(media),
    )


async def _set_cover_image(source_type: str,
                           source_id: str,
                           cover_image: CoverImageUpdate,
                           db: db_dep,
                           ):
    source = await _get_source(source_type, source_id, db)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{source_type} {source_id} not found",
        )

    media = await db.media.get_media(cover_image.media_id)
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {cover_image.media_id} not found",
        )

    linked = await db.media.set_cover_image(source_id, cover_image.media_id)
    if not linked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{source_type} {source_id} or media {cover_image.media_id} not found",
        )

    return linked


async def _get_cover_image(source_type: str,
                           source_id: str,
                           db: db_dep,
                           storage: storage_dep,
                           ) -> FileResponse:
    source = await _get_source(source_type, source_id, db)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{source_type} {source_id} not found",
        )

    media = await db.media.get_cover_image(source_id)
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cover image for {_source_detail_name(source_type)} {source_id} not found",
        )

    return await _get_media_file_response(media.id, db, storage)


async def _delete_cover_image(source_type: str,
                              source_id: str,
                              db: db_dep,
                              ):
    source = await _get_source(source_type, source_id, db)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{source_type} {source_id} not found",
        )

    await db.media.remove_cover_image(source_id)


@media_router.post("/media", response_model=MediaFile)
async def create_media(
        db: db_dep,
        storage: storage_dep,
        file: UploadFile = File(...),
        type: MediaType = Form(...),
        title: Optional[str] = Form(None),
        filename: Optional[str] = Form(None),
):
    try:
        stored = await storage.save(_upload_chunks(file))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    finally:
        await file.close()

    media = MediaFile(
        type=type,
        title=title,
        hash=stored.digest,
        filename=_filename_without_suffix(file, filename),
    )

    return await db.media.create_media(media)


@media_router.get("/media", response_model=list[MediaFile])
async def list_media(
        db: db_dep,
        world_id: Optional[str] = Query(None, description="Optionally filter by world"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
        type: Optional[MediaType] = Query(None, description="Optionally filter by media type"),
        limit: Optional[int] = Query(None, ge=1, description="Maximum number of media records to return"),
        skip: int = Query(0, ge=0, description="Number of media records to skip"),
):
    return await db.media.list_media(
        world_id=world_id,
        simulation_id=simulation_id,
        media_type=type,
        limit=limit,
        skip=skip,
    )


@media_router.get("/media/{media_id}")
async def get_media(media_id: str, db: db_dep, storage: storage_dep):
    return await _get_media_file_response(media_id, db, storage)


@media_router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(media_id: str, db: db_dep, storage: storage_dep):
    deleted = await db.media.delete_media(media_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    media, remaining_hash_references = deleted
    if remaining_hash_references == 0:
        await storage.delete(media.hash, missing_ok=True)


@media_router.post("/worlds/{world_id}/cover-image", response_model=MediaFile)
async def set_world_cover_image(world_id: str,
                                cover_image: CoverImageUpdate,
                                db: db_dep,
                                ):
    return await _set_cover_image("World", world_id, cover_image, db)


@media_router.get("/worlds/{world_id}/cover-image")
async def get_world_cover_image(world_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("World", world_id, db, storage)


@media_router.delete("/worlds/{world_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_cover_image(world_id: str, db: db_dep):
    await _delete_cover_image("World", world_id, db)


@media_router.post("/simulations/{simulation_id}/cover-image", response_model=MediaFile)
async def set_simulation_cover_image(simulation_id: str,
                                     cover_image: CoverImageUpdate,
                                     db: db_dep,
                                     ):
    return await _set_cover_image("Simulation", simulation_id, cover_image, db)


@media_router.get("/simulations/{simulation_id}/cover-image")
async def get_simulation_cover_image(simulation_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Simulation", simulation_id, db, storage)


@media_router.delete("/simulations/{simulation_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation_cover_image(simulation_id: str, db: db_dep):
    await _delete_cover_image("Simulation", simulation_id, db)


@media_router.post("/characters/{character_id}/cover-image", response_model=MediaFile)
async def set_character_cover_image(character_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("Character", character_id, cover_image, db)


@media_router.get("/characters/{character_id}/cover-image")
async def get_character_cover_image(character_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Character", character_id, db, storage)


@media_router.delete("/characters/{character_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_cover_image(character_id: str, db: db_dep):
    await _delete_cover_image("Character", character_id, db)


@media_router.post("/background-characters/{character_id}/cover-image", response_model=MediaFile)
async def set_background_character_cover_image(character_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("BackgroundCharacter", character_id, cover_image, db)


@media_router.get("/background-characters/{character_id}/cover-image")
async def get_background_character_cover_image(character_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("BackgroundCharacter", character_id, db, storage)


@media_router.delete("/background-characters/{character_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_background_character_cover_image(character_id: str, db: db_dep):
    await _delete_cover_image("BackgroundCharacter", character_id, db)


@media_router.post("/locations/{location_id}/cover-image", response_model=MediaFile)
async def set_location_cover_image(location_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("Location", location_id, cover_image, db)


@media_router.get("/locations/{location_id}/cover-image")
async def get_location_cover_image(location_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Location", location_id, db, storage)


@media_router.delete("/locations/{location_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location_cover_image(location_id: str, db: db_dep):
    await _delete_cover_image("Location", location_id, db)


@media_router.post("/landmarks/{landmark_id}/cover-image", response_model=MediaFile)
async def set_landmark_cover_image(landmark_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("Landmark", landmark_id, cover_image, db)


@media_router.get("/landmarks/{landmark_id}/cover-image")
async def get_landmark_cover_image(landmark_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Landmark", landmark_id, db, storage)


@media_router.delete("/landmarks/{landmark_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_landmark_cover_image(landmark_id: str, db: db_dep):
    await _delete_cover_image("Landmark", landmark_id, db)


@media_router.post("/items/{item_id}/cover-image", response_model=MediaFile)
async def set_item_cover_image(item_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("Item", item_id, cover_image, db)


@media_router.get("/items/{item_id}/cover-image")
async def get_item_cover_image(item_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Item", item_id, db, storage)


@media_router.delete("/items/{item_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item_cover_image(item_id: str, db: db_dep):
    await _delete_cover_image("Item", item_id, db)


@media_router.post("/stacks/{stack_id}/cover-image", response_model=MediaFile)
async def set_stack_cover_image(stack_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("ItemStack", stack_id, cover_image, db)


@media_router.get("/stacks/{stack_id}/cover-image")
async def get_stack_cover_image(stack_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("ItemStack", stack_id, db, storage)


@media_router.delete("/stacks/{stack_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stack_cover_image(stack_id: str, db: db_dep):
    await _delete_cover_image("ItemStack", stack_id, db)


@media_router.post("/equipment/{equipment_id}/cover-image", response_model=MediaFile)
async def set_equipment_cover_image(equipment_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("Equipment", equipment_id, cover_image, db)


@media_router.get("/equipment/{equipment_id}/cover-image")
async def get_equipment_cover_image(equipment_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Equipment", equipment_id, db, storage)


@media_router.delete("/equipment/{equipment_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment_cover_image(equipment_id: str, db: db_dep):
    await _delete_cover_image("Equipment", equipment_id, db)


@media_router.post("/containers/{container_id}/cover-image", response_model=MediaFile)
async def set_container_cover_image(container_id: str, cover_image: CoverImageUpdate, db: db_dep):
    return await _set_cover_image("Container", container_id, cover_image, db)


@media_router.get("/containers/{container_id}/cover-image")
async def get_container_cover_image(container_id: str, db: db_dep, storage: storage_dep):
    return await _get_cover_image("Container", container_id, db, storage)


@media_router.delete("/containers/{container_id}/cover-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container_cover_image(container_id: str, db: db_dep):
    await _delete_cover_image("Container", container_id, db)
