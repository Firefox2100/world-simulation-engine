from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ContainerState
from world_simulation_engine.model import Container, Equipment, Item
from .utils import db_dep


container_router = APIRouter(
    tags=["Container"],
)


class ContainerCreate(BaseModel):
    """
    DTO model for creating a container
    """

    name: str = Field(..., description="The name of the container")
    description: str = Field(..., description="The description of the container")
    state: ContainerState = Field(..., description="The current state of the container")
    location_id: Optional[str] = Field(None, description="Optional location where the container is present")
    position: Optional[str] = Field(None, description="Optional position in the location")
    owner_id: Optional[str] = Field(None, description="Optional owner of the container")
    holder_id: Optional[str] = Field(None, description="Optional holder of the container")
    held_stack_ids: list[str] = Field(default_factory=list, description="Optional item stacks held by the container")
    held_equipment_ids: list[str] = Field(default_factory=list, description="Optional equipment held by the container")
    held_container_ids: list[str] = Field(default_factory=list, description="Optional containers held by the container")
    unlocking_item_ids: list[str] = Field(default_factory=list, description="Optional items that unlock the container")


class ContainerUpdate(BaseModel):
    """
    DTO model for updating a container
    """

    name: Optional[str] = Field(None, description="The name of the container")
    description: Optional[str] = Field(None, description="The description of the container")
    state: Optional[ContainerState] = Field(None, description="The current state of the container")
    location_id: Optional[str] = Field(None, description="Optional location where the container is present")
    position: Optional[str] = Field(None, description="Optional position in the location")
    owner_id: Optional[str] = Field(None, description="Optional owner of the container")
    holder_id: Optional[str] = Field(None, description="Optional holder of the container")
    held_stack_ids: Optional[list[str]] = Field(None, description="Optional item stacks held by the container")
    held_equipment_ids: Optional[list[str]] = Field(None, description="Optional equipment held by the container")
    held_container_ids: Optional[list[str]] = Field(None, description="Optional containers held by the container")
    unlocking_item_ids: Optional[list[str]] = Field(None, description="Optional items that unlock the container")


class ContainerLocationUpdate(BaseModel):
    location_id: str = Field(..., description="Location where the container is present")
    position: Optional[str] = Field(None, description="Optional position in the location")


class ContainerOwnerUpdate(BaseModel):
    owner_id: str = Field(..., description="Entity that owns the container")


class ContainerHolderUpdate(BaseModel):
    holder_id: str = Field(..., description="Entity that holds the container")


class StackRelationshipUpdate(BaseModel):
    stack_ids: list[str] = Field(..., description="Item stack ids held by the container")


class EquipmentRelationshipUpdate(BaseModel):
    equipment_ids: list[str] = Field(..., description="Equipment ids held by the container")


class ContainerRelationshipUpdate(BaseModel):
    container_ids: list[str] = Field(..., description="Container ids held by the container")


class UnlockingItemRelationshipUpdate(BaseModel):
    item_ids: list[str] = Field(..., description="Item ids that unlock the container")


def validate_container_relationship_request(container_data: ContainerCreate | ContainerUpdate):
    if container_data.location_id and container_data.holder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Container cannot be placed in a location and held at the same time",
        )


async def validate_container_relationships(container_data: ContainerCreate | ContainerUpdate, db: db_dep):
    validate_container_relationship_request(container_data)

    if container_data.location_id:
        location = await db.location.get_location(container_data.location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {container_data.location_id} not found",
            )

    if container_data.owner_id and not await db.item.entity_exists(container_data.owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Owner {container_data.owner_id} not found",
        )

    if container_data.holder_id and not await db.item.entity_exists(container_data.holder_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holder {container_data.holder_id} not found",
        )

    for stack_id in container_data.held_stack_ids or []:
        stack = await db.item.get_stack(stack_id)
        if not stack:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_id} not found",
            )

    for equipment_id in container_data.held_equipment_ids or []:
        equipment = await db.equipment.get_equipment(equipment_id)
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Equipment {equipment_id} not found",
            )

    for held_container_id in container_data.held_container_ids or []:
        container = await db.container.get_container(held_container_id)
        if not container:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {held_container_id} not found",
            )

    for item_id in container_data.unlocking_item_ids or []:
        item = await db.item.get_item(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {item_id} not found",
            )


async def apply_container_relationships(
        container_id: str,
        container_data: ContainerCreate | ContainerUpdate,
        db: db_dep,
) -> Container:
    container = await db.container.get_container(container_id)

    if container_data.location_id:
        container = await db.container.place_container_in_location(
            container_id,
            container_data.location_id,
            container_data.position,
        )

    if container_data.holder_id or container_data.owner_id:
        container = await db.container.assign_container(
            container_id,
            holder_id=container_data.holder_id,
            owner_id=container_data.owner_id,
        )

    for stack_id in container_data.held_stack_ids or []:
        container = await db.container.put_stack_in_container(stack_id, container_id)

    for equipment_id in container_data.held_equipment_ids or []:
        container = await db.container.put_equipment_in_container(equipment_id, container_id)

    for held_container_id in container_data.held_container_ids or []:
        container = await db.container.put_container_in_container(held_container_id, container_id)

    for item_id in container_data.unlocking_item_ids or []:
        container = await db.container.add_unlocking_item(item_id, container_id)

    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


async def validate_stack_ids(stack_ids: list[str], db: db_dep):
    for stack_id in stack_ids:
        if not await db.item.get_stack(stack_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_id} not found",
            )


async def validate_equipment_ids(equipment_ids: list[str], db: db_dep):
    for equipment_id in equipment_ids:
        if not await db.equipment.get_equipment(equipment_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Equipment {equipment_id} not found",
            )


async def validate_container_ids(container_ids: list[str], db: db_dep):
    for container_id in container_ids:
        if not await db.container.get_container(container_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} not found",
            )


async def validate_item_ids(item_ids: list[str], db: db_dep):
    for item_id in item_ids:
        if not await db.item.get_item(item_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {item_id} not found",
            )


@container_router.get("/containers", response_model=list[Container])
async def list_containers(
        db: db_dep,
        world_id: Optional[str] = Query(None, description="Optionally filter by world"),
        simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
        location_id: Optional[str] = Query(None, description="Optionally filter by location"),
        owner_id: Optional[str] = Query(None, description="Optionally filter by owner"),
        holder_id: Optional[str] = Query(None, description="Optionally filter by holder"),
):
    return await db.container.list_containers(
        world_id=world_id,
        simulation_id=simulation_id,
        location_id=location_id,
        owner_id=owner_id,
        holder_id=holder_id,
    )


@container_router.get("/containers/{container_id}", response_model=Container)
async def get_container(container_id: str, db: db_dep):
    container = await db.container.get_container(container_id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.put("/containers/{container_id}/location", response_model=Container)
async def set_container_location(
        container_id: str,
        location_data: ContainerLocationUpdate,
        db: db_dep,
):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    if not await db.location.get_location(location_data.location_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_data.location_id} not found",
        )

    container = await db.container.place_container_in_location(
        container_id,
        location_data.location_id,
        location_data.position,
    )
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/location", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container_location(container_id: str, db: db_dep):
    deleted = await db.container.remove_location(container_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.put("/containers/{container_id}/owner", response_model=Container)
async def set_container_owner(container_id: str, owner_data: ContainerOwnerUpdate, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    if not await db.item.entity_exists(owner_data.owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Owner {owner_data.owner_id} not found",
        )

    container = await db.container.assign_container(container_id, owner_id=owner_data.owner_id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/owner", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container_owner(container_id: str, db: db_dep):
    deleted = await db.container.remove_owner(container_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.put("/containers/{container_id}/holder", response_model=Container)
async def set_container_holder(container_id: str, holder_data: ContainerHolderUpdate, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    if not await db.item.entity_exists(holder_data.holder_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holder {holder_data.holder_id} not found",
        )

    container = await db.container.assign_container(container_id, holder_id=holder_data.holder_id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/holder", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container_holder(container_id: str, db: db_dep):
    deleted = await db.container.remove_holder(container_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.patch("/containers/{container_id}", response_model=Container)
async def update_container(container_id: str, container_data: ContainerUpdate, db: db_dep):
    await validate_container_relationships(container_data, db)

    properties = container_data.model_dump(
        exclude_unset=True,
        exclude={
            "location_id",
            "position",
            "owner_id",
            "holder_id",
            "held_stack_ids",
            "held_equipment_ids",
            "held_container_ids",
            "unlocking_item_ids",
        },
    )
    if properties:
        container = await db.container.update_container(container_id, properties)
    else:
        container = await db.container.get_container(container_id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return await apply_container_relationships(container_id, container_data, db)


@container_router.delete("/containers/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container(container_id: str, db: db_dep):
    deleted = await db.container.delete_container(container_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.post("/worlds/{world_id}/containers", response_model=Container)
async def create_container_in_world(world_id: str, container_data: ContainerCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    await validate_container_relationships(container_data, db)

    container = Container(
        name=container_data.name,
        description=container_data.description,
        state=container_data.state,
    )
    created_container = await db.container.create_container(
        container,
        world_id,
        location_id=container_data.location_id,
        position=container_data.position,
    )
    if not created_container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return await apply_container_relationships(created_container.id, container_data, db)


@container_router.post("/simulations/{simulation_id}/containers", response_model=Container)
async def create_container_in_simulation(simulation_id: str, container_data: ContainerCreate, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    await validate_container_relationships(container_data, db)

    container = Container(
        name=container_data.name,
        description=container_data.description,
        state=container_data.state,
    )
    created_container = await db.container.create_container(
        container,
        simulation_id,
        location_id=container_data.location_id,
        position=container_data.position,
    )
    if not created_container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return await apply_container_relationships(created_container.id, container_data, db)


@container_router.get("/containers/{container_id}/stacks")
async def get_held_stacks(container_id: str, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return await db.container.get_held_stacks(container_id)


@container_router.put("/containers/{container_id}/stacks", response_model=Container)
async def set_held_stacks(container_id: str, stack_data: StackRelationshipUpdate, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_stack_ids(stack_data.stack_ids, db)

    container = await db.container.replace_held_stacks(container_id, stack_data.stack_ids)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/stacks", status_code=status.HTTP_204_NO_CONTENT)
async def delete_held_stacks(container_id: str, stack_data: StackRelationshipUpdate, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_stack_ids(stack_data.stack_ids, db)

    deleted = await db.container.remove_held_stacks(container_id, stack_data.stack_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.get("/containers/{container_id}/equipment", response_model=list[Equipment])
async def get_held_equipment(container_id: str, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return await db.container.get_held_equipment(container_id)


@container_router.put("/containers/{container_id}/equipment", response_model=Container)
async def set_held_equipment(
        container_id: str,
        equipment_data: EquipmentRelationshipUpdate,
        db: db_dep,
):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_equipment_ids(equipment_data.equipment_ids, db)

    container = await db.container.replace_held_equipment(container_id, equipment_data.equipment_ids)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/equipment", status_code=status.HTTP_204_NO_CONTENT)
async def delete_held_equipment(
        container_id: str,
        equipment_data: EquipmentRelationshipUpdate,
        db: db_dep,
):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_equipment_ids(equipment_data.equipment_ids, db)

    deleted = await db.container.remove_held_equipment(container_id, equipment_data.equipment_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.get("/containers/{container_id}/containers", response_model=list[Container])
async def get_held_containers(container_id: str, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return await db.container.get_held_containers(container_id)


@container_router.put("/containers/{container_id}/containers", response_model=Container)
async def set_held_containers(
        container_id: str,
        container_data: ContainerRelationshipUpdate,
        db: db_dep,
):
    if container_id in container_data.container_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Container cannot hold itself",
        )
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_container_ids(container_data.container_ids, db)

    container = await db.container.replace_held_containers(container_id, container_data.container_ids)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/containers", status_code=status.HTTP_204_NO_CONTENT)
async def delete_held_containers(
        container_id: str,
        container_data: ContainerRelationshipUpdate,
        db: db_dep,
):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_container_ids(container_data.container_ids, db)

    deleted = await db.container.remove_held_containers(container_id, container_data.container_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )


@container_router.get("/containers/{container_id}/unlocking-items", response_model=list[Item])
async def get_unlocking_items(container_id: str, db: db_dep):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return await db.container.get_unlocking_items(container_id)


@container_router.put("/containers/{container_id}/unlocking-items", response_model=Container)
async def set_unlocking_items(
        container_id: str,
        item_data: UnlockingItemRelationshipUpdate,
        db: db_dep,
):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_item_ids(item_data.item_ids, db)

    container = await db.container.replace_unlocking_items(container_id, item_data.item_ids)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return container


@container_router.delete("/containers/{container_id}/unlocking-items", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unlocking_items(
        container_id: str,
        item_data: UnlockingItemRelationshipUpdate,
        db: db_dep,
):
    if not await db.container.get_container(container_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
    await validate_item_ids(item_data.item_ids, db)

    deleted = await db.container.remove_unlocking_items(container_id, item_data.item_ids)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )
