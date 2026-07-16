from uuid import uuid4

from world_simulation_engine.model import Item, ItemStack, Location, Simulation
from world_simulation_engine.service.database.item_store import ItemStore
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_missing_item_returns_none(clean_neo4j):
    store = ItemStore(clean_neo4j)

    assert await store.get_item(str(uuid4())) is None


async def test_create_item(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)

    assert await store.create_item(item, source_id=world.id) == item

    assert await store.get_item(item.id) == item

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:Item {id: $item_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "item_id": item.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_list_update_and_delete_item(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)

    await item_store.create_item(item, source_id=world.id)

    assert await item_store.list_items() == [item]
    assert await item_store.list_items(world_id=world.id) == [item]

    updated_item = await item_store.update_item(
        item.id,
        {
            "name": "Updated Apple",
            "unique": True,
        },
    )

    assert updated_item == Item(
        id=item.id,
        name="Updated Apple",
        description=item.description,
        unique=True,
    )
    assert await item_store.delete_item(item.id) is True
    assert await item_store.get_item(item.id) is None
    assert await item_store.delete_item(item.id) is False


async def test_stack_inventory_holder_and_owner(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    owner = await create_character(clean_neo4j, world.id, name="Owner")

    await item_store.create_item(item, source_id=world.id)
    assert await item_store.create_stack(
        item.id,
        stack,
        holder_id=holder.id,
        owner_id=owner.id,
    ) == stack

    inventory = await item_store.get_inventory(holder.id)

    assert len(inventory) == 1
    assert inventory[0].item_id == item.id
    assert inventory[0].stack_id == stack.id
    assert inventory[0].quantity == stack.quantity
    assert inventory[0].quality == stack.quality
    assert inventory[0].owner_id == owner.id

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:ItemStack {id: $stack_id})-[:OF_TYPE]->(:Item {id: $item_id})
        RETURN count(*) AS link_count
        """,
        parameters_={
            "source_id": world.id,
            "stack_id": stack.id,
            "item_id": item.id,
        },
    )

    assert result.records[0]["link_count"] == 1


async def test_list_update_and_delete_stack_with_relationship_filters(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    location = Location(id=str(uuid4()), name="Market", description="A busy market")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    owner = await create_character(clean_neo4j, world.id, name="Owner")

    await location_store.create_location(location, source_id=world.id)
    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack, location_id=location.id, source_id=world.id)
    await item_store.assign_stack(stack.id, owner_id=owner.id)

    assert await item_store.get_stack(stack.id) == stack
    assert await item_store.list_stacks() == [stack]
    assert await item_store.list_stacks(world_id=world.id) == [stack]
    assert await item_store.list_stacks(item_id=item.id) == [stack]
    assert await item_store.list_stacks(owner_id=owner.id) == [stack]
    assert await item_store.list_stacks(location_id=location.id) == [stack]

    updated_stack = await item_store.update_stack(
        stack.id,
        {
            "quantity": 2,
            "quality": "bruised",
        },
    )

    assert updated_stack == ItemStack(id=stack.id, quantity=2, quality="bruised")
    assert await item_store.assign_stack(stack.id, holder_id=holder.id) == updated_stack
    assert await item_store.list_stacks(holder_id=holder.id) == [updated_stack]
    assert await item_store.list_stacks(location_id=location.id) == []
    assert await item_store.delete_stack(stack.id) is True
    assert await item_store.get_stack(stack.id) is None
    assert await item_store.delete_stack(stack.id) is False


async def test_create_stack_can_assign_physical_stack_to_simulation(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=world.starting_time,
    )

    await item_store.create_item(item, source_id=world.id)
    await simulation_store.create_simulation(simulation, world.id)
    holder = await create_character(clean_neo4j, simulation.id, name="Holder")

    assert await item_store.create_stack(
        item.id,
        stack,
        source_id=simulation.id,
        holder_id=holder.id,
    ) == stack

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $world_id})-[:CONTAINS]->(:Item {id: $item_id})
        MATCH (:Simulation {id: $simulation_id})-[:CONTAINS]->(:ItemStack {id: $stack_id})-[:OF_TYPE]->(:Item {id: $item_id})
        RETURN count(*) AS link_count
        """,
        parameters_={
            "world_id": world.id,
            "simulation_id": simulation.id,
            "item_id": item.id,
            "stack_id": stack.id,
        },
    )

    assert result.records[0]["link_count"] == 1


async def test_create_stack_returns_none_for_missing_source_or_item(clean_neo4j):
    world = await create_world(clean_neo4j)
    other_world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    other_item = Item(id=str(uuid4()), name="Pear", description="A green fruit", unique=False)
    simulation = Simulation(
        id=str(uuid4()),
        name="Test Simulation",
        description="A test simulation",
        current_time=world.starting_time,
    )

    await item_store.create_item(item, source_id=world.id)
    await item_store.create_item(other_item, source_id=other_world.id)
    await simulation_store.create_simulation(simulation, world.id)

    assert await item_store.create_stack(
        str(uuid4()),
        ItemStack(id=str(uuid4())),
        location_id=str(uuid4()),
    ) is None
    assert await item_store.create_stack(
        item.id,
        ItemStack(id=str(uuid4())),
        source_id=str(uuid4()),
        location_id=str(uuid4()),
    ) is None
    assert await item_store.create_stack(
        other_item.id,
        ItemStack(id=str(uuid4())),
        source_id=simulation.id,
        location_id=str(uuid4()),
    ) is None


async def test_create_stack_returns_none_without_location_or_holder(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)

    await item_store.create_item(item, source_id=world.id)

    assert await item_store.create_stack(
        item.id,
        ItemStack(id=str(uuid4())),
        source_id=world.id,
    ) is None


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
