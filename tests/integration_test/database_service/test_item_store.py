from uuid import uuid4

from world_simulation_engine.model import Item, ItemStack
from world_simulation_engine.service.database.item_store import ItemStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_missing_item_returns_none(clean_neo4j):
    store = ItemStore(clean_neo4j)

    assert await store.get_item(str(uuid4())) is None


async def test_create_item(clean_neo4j):
    store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)

    await store.create_item(item)

    assert await store.get_item(item.id) == item


async def test_stack_inventory_holder_and_owner(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    owner = await create_character(clean_neo4j, world.id, name="Owner")

    await item_store.create_item(item)
    await item_store.create_stack(item.id, stack)
    await item_store.assign_stack(stack.id, holder_id=holder.id, owner_id=owner.id)

    inventory = await item_store.get_inventory(holder.id)

    assert inventory.holder_id == holder.id
    assert len(inventory.stacks) == 1
    assert inventory.stacks[0].item_id == item.id
    assert inventory.stacks[0].stack_id == stack.id
    assert inventory.stacks[0].quantity == stack.quantity
    assert inventory.stacks[0].quality == stack.quality
    assert inventory.stacks[0].owner_id == owner.id
