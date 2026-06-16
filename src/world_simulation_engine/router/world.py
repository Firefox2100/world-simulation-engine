from fastapi import APIRouter, Query, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse

from world_simulation_engine.misc.enums import FactionRelationshipEntity
from world_simulation_engine.model import Simulation
from world_simulation_engine.model.world import World, WorldCreate
from world_simulation_engine.service import FormatNormaliser
from .utils import db_dep, storage_dep


world_router = APIRouter(
    prefix="/worlds",
    tags=["World"],
)


@world_router.get("", response_model=list[World])
async def list_worlds(db: db_dep,
                      limit: int | None = Query(None, ge=1),
                      offset: int = Query(0, ge=0),
                      ):
    worlds = await db.world.list(limit=limit, offset=offset)

    return worlds


@world_router.post("", response_model=World)
async def create_world(world_create: WorldCreate,
                       db: db_dep,
                       ):
    result = await db.world.create(world_create)

    return result


@world_router.get("/{world_id}", response_model=World)
async def get_world(world_id: int,
                    db: db_dep,
                    ):
    result = await db.world.get(world_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World with ID {world_id} not found",
        )

    return result


@world_router.patch("/{world_id}", response_model=World)
async def update_world(world_id: int,
                       body: dict,
                       db: db_dep,
                       ):
    await db.world.update(world_id, body)

    current_world = await db.world.get(world_id)

    return current_world


@world_router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world(world_id: int,
                       db: db_dep,
                       ):
    await db.world.delete(world_id)


@world_router.get("/{world_id}/images/cover")
async def get_world_cover_image(world_id: int,
                                db: db_dep,
                                storage: storage_dep,
                                ):
    world = await db.world.get(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World with ID {world_id} not found",
        )

    image_path = storage.world(world_id).image.get_path("cover.png")
    if not image_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} has no cover image",
        )

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=f"world-{world_id}-cover.png",
    )


@world_router.post("/{world_id}/images/cover", status_code=status.HTTP_201_CREATED)
async def upload_world_cover_image(world_id: int,
                                   db: db_dep,
                                   storage: storage_dep,
                                   file: UploadFile = File(...),
                                   ):
    world = await db.world.get(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World with ID {world_id} not found",
        )

    normaliser = FormatNormaliser()
    try:
        normalised_bytes = normaliser.normalise_image(await file.read())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Error while normalising image: {e}",
        ) from e

    await storage.world(world_id).image.save(
        file_name="cover.png",
        data=normalised_bytes,
    )

    return {
        "file_name": f"world-{world_id}-cover.png",
    }


@world_router.post("/{world_id}/new-simulation", response_model=Simulation)
async def create_new_simulation(world_id: int,
                                db: db_dep,
                                storage: storage_dep,
                                ):
    world = await db.world.get(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World with ID {world_id} not found",
        )

    if not world.description \
            or not world.agent_preset \
            or not world.data_preset \
            or not world.embedding_profile \
            or not world.language \
            or not world.state:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"The world template {world_id} is not completely configured, cannot create new simulation.",
        )

    simulation = Simulation(
        id=-1,
        name=world.name,
        description=world.description,
        agent_preset=world.agent_preset,
        data_preset=world.data_preset,
        embedding_profile=world.embedding_profile,
        language=world.language,
        act_for_user=world.act_for_user,
        enable_tts=world.enable_tts,
        enable_image_generation=world.enable_image_generation,
    )

    created_simulation = await db.simulation.create(simulation)
    world.state.id = created_simulation.id
    await db.state.create(world.state)

    id_mappings = {
        "characters": {},
        "locations": {},
        "factions": {},
    }

    if world.locations:
        for location in world.locations:
            result = await db.location.create(
                location=location,
                simulation_id=created_simulation.id,
            )
            id_mappings["locations"][location.id] = result.id
    if world.characters:
        for character in world.characters:
            character.location = id_mappings["locations"][character.location]
            result = await db.character.create(
                character=character,
                simulation_id=created_simulation.id,
            )
            id_mappings["characters"][character.id] = result.id
    if world.factions:
        for faction in world.factions:
            result = await db.faction.create(
                faction=faction,
                simulation_id=created_simulation.id,
            )
            id_mappings["factions"][faction.id] = result.id
    if world.faction_relationships:
        for relationship in world.faction_relationships:
            if relationship.from_type == FactionRelationshipEntity.FACTION:
                relationship.from_id = id_mappings["factions"][relationship.from_id]
            elif relationship.from_type == FactionRelationshipEntity.CHARACTER:
                relationship.from_id = id_mappings["characters"][relationship.from_id]
            elif relationship.from_type == FactionRelationshipEntity.ITEM:
                relationship.from_id = id_mappings["items"][relationship.from_id]

            if relationship.to_type == FactionRelationshipEntity.FACTION:
                relationship.to_id = id_mappings["factions"][relationship.to_id]
            elif relationship.to_type == FactionRelationshipEntity.CHARACTER:
                relationship.to_id = id_mappings["characters"][relationship.to_id]
            elif relationship.to_type == FactionRelationshipEntity.ITEM:
                relationship.to_id = id_mappings["items"][relationship.to_id]

            await db.faction_relationship.create(
                relationship=relationship,
            )
    if world.inventory:
        for original_id, inventory in world.inventory.items():
            for item in inventory.items:
                await db.item.create(
                    item=item,
                    simulation_id=created_simulation.id,
                    character_id=id_mappings["characters"][original_id] or None,
                )
            for equipment in inventory.equipments:
                await db.equipment.create(
                    equipment=equipment,
                    simulation_id=created_simulation.id,
                    character_id=id_mappings["characters"][original_id] or None,
                )
    if world.tasks:
        for task in world.tasks:
            for i in range(len(task.character_ids)):
                task.character_ids[i] = id_mappings["characters"][task.character_ids[i]]

            await db.task.create(task=task)
    if world.world_entries:
        for world_entry in world.world_entries:
            for i in range(len(world_entry.scope)):
                if world_entry.scope[i] > 0:
                    world_entry.scope[i] = id_mappings["characters"][world_entry.scope[i]]

            await db.entry.create(
                world_entry=world_entry,
                simulation_id=created_simulation.id,
            )
    if world.turn_records:
        for turn_record in world.turn_records:
            await db.record.create(record=turn_record)

    await storage.copy_world_to_simulation(
        world_id=world_id,
        simulation_id=created_simulation.id,
    )

    return simulation
