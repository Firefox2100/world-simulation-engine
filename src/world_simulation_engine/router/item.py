from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.model import Item, ItemStack
from .utils import db_dep


item_router = APIRouter(
    tags=["Item"],
)


class ItemCreate(BaseModel):
    """
    DTO model for creating an item
    """

    name: str = Field(
        ...,
        description="Name of the item",
    )
    description: str = Field(
        ...,
        description="Description of the item",
    )
    unique: bool = Field(
        False,
        description="Whether or not the item is unique",
    )


class ItemUpdate(BaseModel):
    """
    DTO model for updating an item
    """
    name: Optional[str] = Field(
        None,
        description="Name of the item",
    )
    description: Optional[str] = Field(
        None,
        description="Description of the item",
    )
    unique: Optional[bool] = Field(
        None,
        description="Whether or not the item is unique",
    )


class ItemStackCreate(BaseModel):
    """
    DTO model for creating an item stack
    """

    quantity: int = Field(
        1,
        description="The quantity of the item in this stack",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the item in this stack",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the stack is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position of the stack in the location",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Optional holder of the stack",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Optional owner of the stack",
    )


class ItemStackUpdate(BaseModel):
    """
    DTO model for updating an item stack
    """

    quantity: Optional[int] = Field(
        None,
        description="The quantity of the item in this stack",
    )
    quality: Optional[str] = Field(
        None,
        description="Optional quality modifier of the item in this stack",
    )
    location_id: Optional[str] = Field(
        None,
        description="Optional location where the stack is present",
    )
    position: Optional[str] = Field(
        None,
        description="Optional position of the stack in the location",
    )
    holder_id: Optional[str] = Field(
        None,
        description="Optional holder of the stack",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Optional owner of the stack",
    )


def validate_stack_relationship_request(stack_data: ItemStackCreate | ItemStackUpdate):
    if stack_data.location_id and stack_data.holder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stack cannot be placed in a location and held at the same time",
        )

    if isinstance(stack_data, ItemStackCreate) and not stack_data.location_id and not stack_data.holder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stack must be placed in a location or held by another entity",
        )


async def validate_stack_relationships(stack_data: ItemStackCreate | ItemStackUpdate, db: db_dep):
    validate_stack_relationship_request(stack_data)

    if stack_data.location_id:
        location = await db.location.get_location(stack_data.location_id)
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {stack_data.location_id} not found",
            )

    if stack_data.holder_id and not await db.item.entity_exists(stack_data.holder_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holder {stack_data.holder_id} not found",
        )

    if stack_data.owner_id and not await db.item.entity_exists(stack_data.owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Owner {stack_data.owner_id} not found",
        )


async def apply_stack_relationships(stack_id: str,
                                    stack_data: ItemStackCreate | ItemStackUpdate,
                                    db: db_dep,
                                    ) -> ItemStack:
    stack = await db.item.get_stack(stack_id)

    if stack_data.location_id:
        stack = await db.item.place_stack_in_location(
            stack_id,
            stack_data.location_id,
            stack_data.position,
        )
    if stack_data.holder_id or stack_data.owner_id:
        stack = await db.item.assign_stack(
            stack_id,
            holder_id=stack_data.holder_id,
            owner_id=stack_data.owner_id,
        )

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} not found",
        )

    return stack


@item_router.get("/items", response_model=list[Item])
async def list_items(db: db_dep,
                     world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                     simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
                     ):
    return await db.item.list_items(
        world_id=world_id,
        simulation_id=simulation_id,
    )


@item_router.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: str, db: db_dep):
    item = await db.item.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )

    return item


@item_router.patch("/items/{item_id}", response_model=Item)
async def update_item(item_id: str, item_update: ItemUpdate, db: db_dep):
    item = await db.item.update_item(
        item_id,
        item_update.model_dump(exclude_unset=True),
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )

    return item


@item_router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: str, db: db_dep):
    deleted = await db.item.delete_item(item_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )


@item_router.post("/worlds/{world_id}/items", response_model=Item)
async def create_item_in_world(world_id: str, item_data: ItemCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    item = Item(**item_data.model_dump())
    created_item = await db.item.create_item(item, world_id)
    if not created_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    return created_item


@item_router.post("/simulations/{simulation_id}/items", response_model=Item)
async def create_item_in_simulation(simulation_id: str, item_data: ItemCreate, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    item = Item(**item_data.model_dump())
    created_item = await db.item.create_item(item, simulation_id)
    if not created_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    return created_item


@item_router.get("/stacks", response_model=list[ItemStack])
async def list_stacks(db: db_dep,
                      world_id: Optional[str] = Query(None, description="Optionally filter by world"),
                      simulation_id: Optional[str] = Query(None, description="Optionally filter by simulation"),
                      item_id: Optional[str] = Query(None, description="Optionally filter by item"),
                      owner_id: Optional[str] = Query(None, description="Optionally filter by owner"),
                      holder_id: Optional[str] = Query(None, description="Optionally filter by holder"),
                      location_id: Optional[str] = Query(None, description="Optionally filter by location"),
                      ):
    return await db.item.list_stacks(
        world_id=world_id,
        simulation_id=simulation_id,
        item_id=item_id,
        owner_id=owner_id,
        holder_id=holder_id,
        location_id=location_id,
    )


@item_router.get("/stacks/{stack_id}", response_model=ItemStack)
async def get_stack(stack_id: str, db: db_dep):
    stack = await db.item.get_stack(stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} not found",
        )

    return stack


@item_router.patch("/stacks/{stack_id}", response_model=ItemStack)
async def update_stack(stack_id: str, stack_data: ItemStackUpdate, db: db_dep):
    await validate_stack_relationships(stack_data, db)

    stack = await db.item.update_stack(
        stack_id,
        stack_data.model_dump(
            exclude_unset=True,
            exclude={"location_id", "position", "holder_id", "owner_id"},
        ),
    )
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} not found",
        )

    return await apply_stack_relationships(stack_id, stack_data, db)


@item_router.delete("/stacks/{stack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stack(stack_id: str, db: db_dep):
    deleted = await db.item.delete_stack(stack_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} not found",
        )


@item_router.post("/worlds/{world_id}/items/{item_id}/stacks", response_model=ItemStack)
async def create_stack_in_world(world_id: str, item_id: str, stack_data: ItemStackCreate, db: db_dep):
    world = await db.world.get_world(world_id)
    if not world:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    item = await db.item.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )

    await validate_stack_relationships(stack_data, db)

    stack = ItemStack(
        quantity=stack_data.quantity,
        quality=stack_data.quality,
    )
    created_stack = await db.item.create_stack(
        item_id,
        stack,
        location_id=stack_data.location_id,
        position=stack_data.position,
        source_id=world_id,
        holder_id=stack_data.holder_id,
        owner_id=stack_data.owner_id,
    )
    if not created_stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found in world {world_id}",
        )

    return created_stack


@item_router.post("/simulations/{simulation_id}/items/{item_id}/stacks", response_model=ItemStack)
async def create_stack_in_simulation(simulation_id: str, item_id: str, stack_data: ItemStackCreate, db: db_dep):
    simulation = await db.simulation.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    item = await db.item.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found",
        )

    await validate_stack_relationships(stack_data, db)

    stack = ItemStack(
        quantity=stack_data.quantity,
        quality=stack_data.quality,
    )
    created_stack = await db.item.create_stack(
        item_id,
        stack,
        location_id=stack_data.location_id,
        position=stack_data.position,
        source_id=simulation_id,
        holder_id=stack_data.holder_id,
        owner_id=stack_data.owner_id,
    )
    if not created_stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found in simulation {simulation_id} or its world",
        )

    return created_stack
