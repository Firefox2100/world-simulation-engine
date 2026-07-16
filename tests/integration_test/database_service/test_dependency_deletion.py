from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import ContainerState, IntentHorizon, IntentStatus, IntentType
from world_simulation_engine.model import Container, Intent, Item, ItemStack, Landmark, Location, Simulation
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.container_store import ContainerStore
from world_simulation_engine.service.database.item_store import ItemStore
from world_simulation_engine.service.database.intent_store import IntentStore
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.world_store import WorldStore
from tests.integration_test.database_service.helpers import create_character, create_world


def make_intent() -> Intent:
    return Intent(
        id=str(uuid4()),
        type=IntentType.QUEST,
        name="Find supplies",
        description="Find enough supplies.",
        keywords=["supplies"],
        embedding=[0.1],
        priority=0.5,
        urgency=0.5,
        status=IntentStatus.ACTIVE,
        desired_state="Supplies found",
        success_conditions=[],
        failure_conditions=[],
        maintenance_conditions=[],
        deadline=None,
        horizon=IntentHorizon.SHORT,
        constraints=[],
        current_plan=[],
        next_action_biases=[],
        blockers=[],
        open_threads=[],
    )


async def count_nodes(clean_neo4j, *ids: str) -> int:
    result = await clean_neo4j.execute_query(
        """
        MATCH (node)
        WHERE node.id IN $ids
        RETURN count(node) AS node_count
        """,
        parameters_={"ids": list(ids)},
    )
    return result.records[0]["node_count"]


async def test_delete_item_deletes_dependent_stacks(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    item_store = ItemStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3)

    await item_store.create_item(item, world.id)
    await item_store.create_stack(item.id, stack, source_id=world.id, holder_id=character.id)

    assert await item_store.delete_item(item.id) is True
    assert await count_nodes(clean_neo4j, item.id, stack.id) == 0


async def test_delete_character_deletes_dependent_intents_and_held_stacks(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    item_store = ItemStore(clean_neo4j)
    intent_store = IntentStore(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3)
    intent = make_intent()

    await item_store.create_item(item, world.id)
    await item_store.create_stack(item.id, stack, source_id=world.id, holder_id=character.id)
    await intent_store.create_intent(intent, character.id)

    assert await character_store.delete_character(character.id) is True
    assert await count_nodes(clean_neo4j, character.id, stack.id, intent.id) == 0


async def test_delete_container_deletes_nested_contents(clean_neo4j):
    world = await create_world(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    container_store = ContainerStore(clean_neo4j)
    item = Item(id=str(uuid4()), name="Coin", description="A coin", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=5)
    parent = Container(id=str(uuid4()), name="Chest", description="A chest", state=ContainerState.OPEN)
    child = Container(id=str(uuid4()), name="Pouch", description="A pouch", state=ContainerState.UNLOCKED)

    await container_store.create_container(parent, world.id)
    await container_store.create_container(child, world.id)
    await item_store.create_item(item, world.id)
    await item_store.create_stack(item.id, stack, source_id=world.id, holder_id=parent.id)
    await container_store.put_container_in_container(child.id, parent.id)

    assert await container_store.delete_container(parent.id) is True
    assert await count_nodes(clean_neo4j, parent.id, child.id, stack.id) == 0


async def test_delete_location_deletes_sublocations_and_landmarks(clean_neo4j):
    world = await create_world(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    parent = Location(id=str(uuid4()), name="Town", description="A town")
    child = Location(id=str(uuid4()), name="Market", description="A market")
    landmark = Landmark(id=str(uuid4()), name="Fountain", description="A fountain")

    await location_store.create_location(parent, world.id)
    await location_store.create_sub_location(child, parent.id)
    await location_store.create_landmark(landmark, child.id)

    assert await location_store.delete_location(parent.id) is True
    assert await count_nodes(clean_neo4j, parent.id, child.id, landmark.id) == 0


async def test_delete_simulation_deletes_contained_graph(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    simulation_store = SimulationStore(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    intent_store = IntentStore(clean_neo4j)
    await simulation_store.create_simulation(simulation, world.id)
    character = await create_character(clean_neo4j, simulation.id)
    item = Item(id=str(uuid4()), name="Apple", description="Fresh fruit", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=3)
    intent = make_intent()

    await item_store.create_item(item, simulation.id)
    await item_store.create_stack(item.id, stack, source_id=simulation.id, holder_id=character.id)
    await intent_store.create_intent(intent, character.id)

    assert await simulation_store.delete_simulation(simulation.id) is True
    assert await count_nodes(clean_neo4j, simulation.id, character.id, item.id, stack.id, intent.id) == 0
    assert await WorldStore(clean_neo4j).get_world(world.id) == world


async def test_delete_world_deletes_simulations_and_contained_graph(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = Simulation(
        id=str(uuid4()),
        name="Simulation",
        description="A simulation",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    simulation_store = SimulationStore(clean_neo4j)
    await simulation_store.create_simulation(simulation, world.id)
    character = await create_character(clean_neo4j, simulation.id)

    assert await WorldStore(clean_neo4j).delete_world(world.id) == world
    assert await count_nodes(clean_neo4j, world.id, simulation.id, character.id) == 0
