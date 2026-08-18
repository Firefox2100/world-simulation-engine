import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model import World, WorldMetadata
from world_simulation_engine.service import AuthorNotFoundError, WorldExportService, WorldImportError, \
    WorldImportService
from .utils import db_dep, storage_dep


def _export_filename(world_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", world_name).strip("-")
    return f"{slug or 'world'}.zip"


world_router = APIRouter(
    tags=["World"],
)


class WorldMetadataInput(BaseModel):
    """
    DTO model for the human-facing provenance/notes metadata of a world. All fields are optional -
    none are auto-filled, missing fields simply mean the information wasn't provided.
    """
    author: Optional[str] = Field(
        None,
        description="The original author/creator of the world's content",
    )
    author_url: Optional[str] = Field(
        None,
        description="A URL for the original author, e.g. their profile page",
    )
    resource_url: Optional[str] = Field(
        None,
        description="Where the world's content was originally downloaded from",
    )
    comment: Optional[str] = Field(
        None,
        description="Freeform human-readable notes about the world. Never included in LLM prompts.",
    )
    version: Optional[str] = Field(
        None,
        description="The content's own version string, as set by its original author",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags describing the world's content, similar to a SillyTavern "
                    "character card's tags",
    )


class WorldCreate(BaseModel):
    name: str = Field(
        ...,
        description="The name of the world",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the world",
    )
    starting_time: datetime = Field(
        ...,
        description="The starting time for simulations created from the world",
    )

    author_id: str = Field(
        ...,
        description="The author of the world",
    )
    version: int = Field(
        1,
        description="The version of the world, starting at 1",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the world",
    )
    language: SupportedLanguage = Field(
        ...,
        description="The language of the world",
    )
    metadata: Optional[WorldMetadataInput] = Field(
        None,
        description="Optional human-facing provenance/notes metadata for the world",
    )


class WorldUpdate(BaseModel):
    """
    DTO model for updating a world data
    """

    name: Optional[str] = Field(
        None,
        description="The name of the world",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the world",
    )
    starting_time: Optional[datetime] = Field(
        None,
        description="The starting time for simulations created from the world",
    )
    version: Optional[int] = Field(
        None,
        description="The version of the world, starting at 1",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the world",
    )
    language: Optional[SupportedLanguage] = Field(
        None,
        description="The language of the world",
    )
    metadata: Optional[WorldMetadataInput] = Field(
        None,
        description="Optional human-facing provenance/notes metadata for the world. Replaces the "
                    "world's whole metadata object when provided.",
    )


@world_router.get("/worlds", response_model=list[World])
async def list_worlds(db: db_dep,
                      author_id: Optional[str] = Query(None, description="Optional filter by author"),
                      limit: Optional[int] = Query(None, ge=1, description="Maximum number of worlds to return"),
                      skip: int = Query(0, ge=0, description="Number of worlds to skip"),
                      ):
    return await db.world.list_worlds(
        author_id=author_id,
        limit=limit,
        skip=skip,
    )


@world_router.post("/worlds", response_model=World)
async def create_world(world_create: WorldCreate, db: db_dep):
    world = World(
        name=world_create.name,
        description=world_create.description,
        starting_time=world_create.starting_time,
        version=world_create.version,
        url=world_create.url,
        language=world_create.language,
        metadata=WorldMetadata(**world_create.metadata.model_dump()) if world_create.metadata else WorldMetadata(),
    )
    created_world = await db.world.create_world(world, world_create.author_id)
    if not created_world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {world_create.author_id} not found",
        )

    return created_world


@world_router.post("/worlds/import", response_model=World)
async def import_world(db: db_dep,
                       storage: storage_dep,
                       file: UploadFile = File(...),
                       author_id: str = Form(...),
                       ):
    content = await file.read()
    await file.close()

    try:
        return await WorldImportService(database=db, storage=storage).import_world(content, author_id)
    except AuthorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {exc} not found",
        ) from exc
    except WorldImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@world_router.get("/worlds/{world_id}", response_model=World)
async def get_world(world_id: str, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return world


@world_router.get("/worlds/{world_id}/export")
async def export_world(world_id: str, db: db_dep, storage: storage_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    archive = await WorldExportService(database=db, storage=storage).export_world(world_id)

    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(world.name)}"'},
    )


@world_router.patch("/worlds/{world_id}", response_model=World)
async def update_world(world_id: str, world_update: WorldUpdate, db: db_dep):
    world = await db.world.update_world(
        world_id,
        world_update.model_dump(exclude_unset=True),
    )
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return world


@world_router.delete("/worlds/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world(world_id: str, db: db_dep):
    world = await db.world.delete_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
