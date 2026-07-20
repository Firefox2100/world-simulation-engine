import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import PROMPT_NAMES, PROMPTS
from world_simulation_engine.misc.enums import ComponentType, SupportedLanguage
from world_simulation_engine.model import PromptMediaFile, PromptMessage
from .utils import db_dep, storage_dep


prompt_router = APIRouter(
    tags=["Prompt"],
)


class PromptWrite(BaseModel):
    messages: list[PromptMessage] = Field(
        ...,
        description="Prompt messages using the package prompt JSON structure",
    )
    prompt_name: str = Field(
        ...,
        description="Name of the prompt in package prompt data",
    )
    language: SupportedLanguage = Field(
        ...,
        description="Language of the prompt",
    )
    title: Optional[str] = Field(
        None,
        description="Title of the prompt media file",
    )
    component: Optional[ComponentType] = Field(
        None,
        description="Simulator component this prompt is intended for",
    )
    filename: Optional[str] = Field(
        None,
        description="Filename of the prompt media file, no format suffix",
    )


class PromptUpdate(BaseModel):
    messages: Optional[list[PromptMessage]] = Field(
        None,
        description="Prompt messages using the package prompt JSON structure",
    )
    prompt_name: Optional[str] = Field(
        None,
        description="Name of the prompt in package prompt data",
    )
    language: Optional[SupportedLanguage] = Field(
        None,
        description="Language of the prompt",
    )
    title: Optional[str] = Field(
        None,
        description="Title of the prompt media file",
    )
    component: Optional[ComponentType] = Field(
        None,
        description="Simulator component this prompt is intended for",
    )
    filename: Optional[str] = Field(
        None,
        description="Filename of the prompt media file, no format suffix",
    )


class PromptAssignmentUpdate(BaseModel):
    prompt_name: str = Field(..., description="Prompt usage to assign")
    language: SupportedLanguage = Field(..., description="Prompt language")
    component: Optional[ComponentType] = Field(None, description="Component the assignment is intended for")
    media_id: Optional[str] = Field(None, description="Prompt media id, or null to clear the assignment")


class PromptAssignmentBatchUpdate(BaseModel):
    assignments: list[PromptAssignmentUpdate] = Field(
        default_factory=list,
        description="Prompt assignments to apply",
    )


class ComponentPromptAssignment(BaseModel):
    prompt_name: str
    language: SupportedLanguage
    component: Optional[ComponentType] = None
    prompt: Optional[PromptMediaFile] = None


def _validate_prompt_name(prompt_name: str) -> None:
    if prompt_name not in PROMPT_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported prompt name {prompt_name}",
        )


async def _validate_world(world_id: str, db: db_dep) -> None:
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


async def _validate_simulation(simulation_id: str, db: db_dep) -> None:
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


def _prompt_content(messages: list[PromptMessage]) -> bytes:
    data = [
        message.model_dump(mode="json")
        for message in messages
    ]
    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


async def _delete_file_if_unreferenced(media: PromptMediaFile,
                                       db: db_dep,
                                       storage: storage_dep,
                                       ) -> None:
    deleted = await db.media.delete_media(media.id)
    if not deleted:
        return

    deleted_media, remaining_hash_references = deleted
    if remaining_hash_references == 0:
        await storage.delete(deleted_media.hash, missing_ok=True)


async def _list_prompt_assignments(source_id: str, db: db_dep) -> list[ComponentPromptAssignment]:
    prompts = await db.media.list_prompt_media(simulation_id=source_id)
    if not prompts:
        prompts = await db.media.list_prompt_media(world_id=source_id)

    return [
        ComponentPromptAssignment(
            prompt_name=prompt.prompt_name,
            language=prompt.language,
            component=prompt.component,
            prompt=prompt,
        )
        for prompt in prompts
    ]


async def _apply_prompt_assignments(source_id: str,
                                    assignments: list[PromptAssignmentUpdate],
                                    db: db_dep,
                                    ) -> None:
    for assignment in assignments:
        _validate_prompt_name(assignment.prompt_name)

        if assignment.media_id:
            media = await db.media.get_media(assignment.media_id)
            if not isinstance(media, PromptMediaFile):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prompt media {assignment.media_id} not found",
                )
            if (
                media.prompt_name != assignment.prompt_name
                or media.language != assignment.language
                or media.component != assignment.component
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Prompt media {assignment.media_id} does not match requested assignment",
                )

            linked = await db.media.set_prompt_media(source_id, assignment.media_id)
            if not linked:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prompt source {source_id} or media {assignment.media_id} not found",
                )
        else:
            await db.media.remove_prompt_media(
                source_id=source_id,
                language=assignment.language,
                prompt_name=assignment.prompt_name,
                component=assignment.component,
                delete_media=False,
            )


@prompt_router.get("/prompts", response_model=list[PromptMediaFile])
async def list_prompts(
        db: db_dep,
        language: Optional[SupportedLanguage] = Query(None, description="Optionally filter by language"),
        component: Optional[ComponentType] = Query(None, description="Optionally filter by component"),
        prompt_name: Optional[str] = Query(None, description="Optionally filter by prompt name"),
):
    if prompt_name is not None:
        _validate_prompt_name(prompt_name)

    return await db.media.list_prompt_media(
        language=language,
        component=component,
        prompt_name=prompt_name,
    )


@prompt_router.get("/prompts/builtin/{language}/{prompt_name}", response_model=list[PromptMessage])
async def get_builtin_prompt(language: SupportedLanguage, prompt_name: str):
    _validate_prompt_name(prompt_name)
    return [
        PromptMessage.model_validate(message)
        for message in PROMPTS[language][prompt_name]
    ]


@prompt_router.get("/prompts/{media_id}", response_model=PromptMediaFile)
async def get_prompt(media_id: str, db: db_dep):
    media = await db.media.get_media(media_id)
    if not isinstance(media, PromptMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt media {media_id} not found",
        )

    return media


@prompt_router.get("/prompts/{media_id}/messages", response_model=list[PromptMessage])
async def get_prompt_messages(media_id: str, db: db_dep, storage: storage_dep):
    media = await db.media.get_media(media_id)
    if not isinstance(media, PromptMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt media {media_id} not found",
        )

    content = await storage.get_bytes(media.hash)
    return [
        PromptMessage.model_validate(message)
        for message in json.loads(content.decode("utf-8"))
    ]


@prompt_router.post("/prompts", response_model=PromptMediaFile, status_code=status.HTTP_201_CREATED)
async def create_prompt(prompt: PromptWrite, db: db_dep, storage: storage_dep):
    _validate_prompt_name(prompt.prompt_name)
    stored = await storage.save_bytes(_prompt_content(prompt.messages))
    media = PromptMediaFile(
        title=prompt.title,
        hash=stored.digest,
        filename=prompt.filename or prompt.prompt_name,
        prompt_name=prompt.prompt_name,
        language=prompt.language,
        component=prompt.component,
    )
    return await db.media.create_media(media)


@prompt_router.patch("/prompts/{media_id}", response_model=PromptMediaFile)
async def update_prompt(media_id: str, prompt: PromptUpdate, db: db_dep, storage: storage_dep):
    existing = await db.media.get_media(media_id)
    if not isinstance(existing, PromptMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt media {media_id} not found",
        )

    properties = prompt.model_dump(
        exclude_unset=True,
        exclude={"messages"},
    )
    if "prompt_name" in properties:
        _validate_prompt_name(properties["prompt_name"])

    previous_hash = existing.hash
    if prompt.messages is not None:
        stored = await storage.save_bytes(_prompt_content(prompt.messages))
        properties["hash"] = stored.digest

    updated = await db.media.update_media(media_id, properties)
    if not isinstance(updated, PromptMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt media {media_id} not found",
        )

    if prompt.messages is not None and previous_hash != updated.hash:
        still_used = await db.media.list_media(media_type=None)
        if not any(media.hash == previous_hash for media in still_used):
            await storage.delete(previous_hash, missing_ok=True)

    return updated


@prompt_router.delete("/prompts/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(media_id: str, db: db_dep, storage: storage_dep):
    media = await db.media.get_media(media_id)
    if not isinstance(media, PromptMediaFile):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt media {media_id} not found",
        )

    await _delete_file_if_unreferenced(media, db, storage)


@prompt_router.get("/worlds/{world_id}/prompt-connections", response_model=list[ComponentPromptAssignment])
async def list_world_prompt_connections(world_id: str, db: db_dep):
    await _validate_world(world_id, db)
    return await _list_prompt_assignments(world_id, db)


@prompt_router.put("/worlds/{world_id}/prompt-connections", response_model=list[ComponentPromptAssignment])
async def set_world_prompt_connections(
        world_id: str,
        prompt_update: PromptAssignmentBatchUpdate,
        db: db_dep,
):
    await _validate_world(world_id, db)
    await _apply_prompt_assignments(world_id, prompt_update.assignments, db)
    return await _list_prompt_assignments(world_id, db)


@prompt_router.get("/simulations/{simulation_id}/prompt-connections", response_model=list[ComponentPromptAssignment])
async def list_simulation_prompt_connections(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)
    return await _list_prompt_assignments(simulation_id, db)


@prompt_router.put("/simulations/{simulation_id}/prompt-connections", response_model=list[ComponentPromptAssignment])
async def set_simulation_prompt_connections(
        simulation_id: str,
        prompt_update: PromptAssignmentBatchUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)
    await _apply_prompt_assignments(simulation_id, prompt_update.assignments, db)
    return await _list_prompt_assignments(simulation_id, db)


@prompt_router.get("/simulations/{simulation_id}/prompts/{language}/{prompt_name}", response_model=list[PromptMessage])
async def get_simulation_prompt(
        simulation_id: str,
        language: SupportedLanguage,
        prompt_name: str,
        db: db_dep,
        storage: storage_dep,
):
    await _validate_simulation(simulation_id, db)
    _validate_prompt_name(prompt_name)

    media = await db.media.get_prompt_media(
        simulation_id=simulation_id,
        language=language,
        prompt_name=prompt_name,
    )
    if media:
        content = await storage.get_bytes(media.hash)
        return [
            PromptMessage.model_validate(message)
            for message in json.loads(content.decode("utf-8"))
        ]

    return [
        PromptMessage.model_validate(message)
        for message in PROMPTS[language][prompt_name]
    ]
