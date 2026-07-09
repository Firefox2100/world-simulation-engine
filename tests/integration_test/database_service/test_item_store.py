from uuid import uuid4

from world_simulation_engine.model import Item, ItemStack, Location
from world_simulation_engine.service.database.item_store import ItemStore
from world_simulation_engine.service.database.location_store import LocationStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_missing_item_returns_none(clean_neo4j):
    store = ItemStore(clean_neo4j)

    assert await store.get_item(str(uuid4())) is None


async def test_create_item(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)

    await store.create_item(item, source_id=world.id)

    assert await store.get_item(item.id) == item

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:Item {id: $item_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "item_id": item.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_stack_inventory_holder_and_owner(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    owner = await create_character(clean_neo4j, world.id, name="Owner")

    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack)
    await item_store.assign_stack(stack.id, holder_id=holder.id, owner_id=owner.id)

    inventory = await item_store.get_inventory(holder.id)

    assert len(inventory) == 1
    assert inventory[0].item_id == item.id
    assert inventory[0].stack_id == stack.id
    assert inventory[0].quantity == stack.quantity
    assert inventory[0].quality == stack.quality
    assert inventory[0].owner_id == owner.id


async def test_stack_location_assignment(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    location = Location(id=str(uuid4()), name="Market", description="A busy market")

    await location_store.create_location(location, source_id=world.id)
    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack, location_id=location.id, position="on the stall")

    assert await item_store.get_stacks_by_location(location.id) == [
        (item, stack, location, "on the stall", None)
    ]


async def test_assign_stack_removes_location_presence(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    location = Location(id=str(uuid4()), name="Market", description="A busy market")
    holder = await create_character(clean_neo4j, world.id, name="Holder")

    await location_store.create_location(location, source_id=world.id)
    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack, location_id=location.id, position="on the stall")
    await item_store.assign_stack(stack.id, holder_id=holder.id)

    assert await item_store.get_stacks_by_location(location.id) == []


async def test_location_stack_query_ignores_held_stack(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    location = Location(id=str(uuid4()), name="Market", description="A busy market")
    holder = await create_character(clean_neo4j, world.id, name="Holder")

    await location_store.create_location(location, source_id=world.id)
    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack, location_id=location.id, position="on the stall")
    await clean_neo4j.execute_query(
        """
        MATCH (holder:Character {id: $holder_id})
        MATCH (stack:ItemStack {id: $stack_id})
        MERGE (holder)-[:HOLDS]->(stack)
        """,
        parameters_={
            "holder_id": holder.id,
            "stack_id": stack.id,
        },
    )

    assert await item_store.get_stacks_by_location(location.id) == []
