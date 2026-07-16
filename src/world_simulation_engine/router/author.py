from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Author
from .utils import db_dep


author_router = APIRouter(
    tags=["Author"],
)


class AuthorCreate(BaseModel):
    """
    DTO model for creating an author
    """

    name: str = Field(
        ...,
        description="The name of the author",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the author",
    )


class AuthorUpdate(BaseModel):
    """
    DTO model for updating an author
    """

    name: Optional[str] = Field(
        None,
        description="The name of the author",
    )
    url: Optional[str] = Field(
        None,
        description="The URL of the author",
    )


class WorldAuthorUpdate(BaseModel):
    """
    DTO model for updating an author of a world

    Only reassignment is allowed, chained creation/deletion must be performed via other CURD endpoints
    """

    id: str = Field(
        ...,
        description="The ID of the new author",
    )


@author_router.get("/authors", response_model=list[Author])
async def list_authors(db: db_dep):
    return await db.world.list_authors()


@author_router.post("/authors", response_model=Author)
async def create_author(author_data: AuthorCreate, db: db_dep):
    author = Author(
        name=author_data.name,
        url=author_data.url,
    )
    await db.world.create_author(author)
    return author


@author_router.get("/authors/{author_id}", response_model=Author)
async def get_author(author_id: str, db: db_dep):
    author = await db.world.get_author(author_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {author_id} not found",
        )

    return author


@author_router.patch("/authors/{author_id}", response_model=Author)
async def update_author(author_id: str, author_data: AuthorUpdate, db: db_dep):
    author = await db.world.update_author(
        author_id,
        author_data.model_dump(exclude_unset=True),
    )
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {author_id} not found",
        )

    return author


@author_router.delete("/authors/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_author(author_id: str, db: db_dep):
    deleted = await db.world.delete_author(author_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {author_id} not found",
        )


@author_router.get("/worlds/{world_id}/author", response_model=Author)
async def get_world_author(world_id: str, db: db_dep):
    author = await db.world.get_author_by_world(world_id)
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author for world {world_id} not found",
        )

    return author


@author_router.patch("/worlds/{world_id}/author", response_model=Author)
async def update_world_author(world_id: str, author: WorldAuthorUpdate, db: db_dep):
    updated_author = await db.world.update_world_author(world_id, author.id)
    if not updated_author:
        world_exists = await db.world.get_world(world_id)
        if not world_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"World {world_id} not found",
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Author {author.id} not found",
        )

    return updated_author
