from uuid import uuid4

from world_simulation_engine.misc.enums import ContainerState
from world_simulation_engine.model import BackgroundCharacter, Container, Equipment, Item, ItemStack, Location
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.container_store import ContainerStore
from world_simulation_engine.service.database.equipment_store import EquipmentStore
from world_simulation_engine.service.database.item_store import ItemStore
from world_simulation_engine.service.database.location_store import LocationStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_missing_container_returns_none(clean_neo4j):
    store = ContainerStore(clean_neo4j)

    assert await store.get_container(str(uuid4())) is None


async def test_create_container(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ContainerStore(clean_neo4j)
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.LOCKED,
    )

    assert await store.create_container(container, source_id=world.id) == container

    assert await store.get_container(container.id) == container

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:Container {id: $container_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "container_id": container.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_create_container_returns_none_when_location_is_missing(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ContainerStore(clean_neo4j)
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.LOCKED,
    )

    assert await store.create_container(container, source_id=world.id, location_id=str(uuid4())) is None
    assert await store.get_container(container.id) is None


async def test_list_update_and_delete_container(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ContainerStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Vault", description="A quiet vault")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    owner = await create_character(clean_neo4j, world.id, name="Owner")
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.LOCKED,
    )

    await location_store.create_location(location, source_id=world.id)
    await store.create_container(
        container,
        source_id=world.id,
        location_id=location.id,
        position="against the wall",
    )

    assert await store.list_containers() == [container]
    assert await store.list_containers(world_id=world.id) == [container]
    assert await store.list_containers(location_id=location.id) == [container]

    updated_container = await store.update_container(
        container.id,
        {
            "name": "Updated Chest",
            "state": ContainerState.UNLOCKED,
        },
    )

    assert updated_container == Container(
        id=container.id,
        name="Updated Chest",
        description=container.description,
        state=ContainerState.UNLOCKED,
    )
    assert await store.assign_container(container.id, holder_id=holder.id, owner_id=owner.id) == updated_container
    assert await store.list_containers(holder_id=holder.id) == [updated_container]
    assert await store.list_containers(owner_id=owner.id) == [updated_container]
    assert await store.list_containers(location_id=location.id) == []
    assert await store.delete_container(container.id) is True
    assert await store.get_container(container.id) is None
    assert await store.delete_container(container.id) is False


async def test_container_location_assignment(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ContainerStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Vault", description="A quiet vault")
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.LOCKED,
    )

    await location_store.create_location(location, source_id=world.id)
    await store.create_container(
        container,
        source_id=world.id,
        location_id=location.id,
        position="against the wall",
    )

    assert await store.get_containers_by_location(location.id) == [
        (container, location, "against the wall", None)
    ]


async def test_assign_container_holder_and_owner(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ContainerStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Vault", description="A quiet vault")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    owner = await create_character(clean_neo4j, world.id, name="Owner")
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.UNLOCKED,
    )

    await location_store.create_location(location, source_id=world.id)
    await store.create_container(
        container,
        source_id=world.id,
        location_id=location.id,
        position="against the wall",
    )
    await store.assign_container(container.id, holder_id=holder.id, owner_id=owner.id)

    assert await store.get_containers_by_location(location.id) == []

    result = await clean_neo4j.execute_query(
        """
        MATCH (holder:Character {id: $holder_id})-[:HOLDS]->(container:Container {id: $container_id})
        MATCH (owner:Character {id: $owner_id})-[:OWNS]->(container)
        RETURN count(*) AS link_count
        """,
        parameters_={
            "holder_id": holder.id,
            "owner_id": owner.id,
            "container_id": container.id,
        },
    )
    assert result.records[0]["link_count"] == 1


async def test_location_container_query_ignores_held_container(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = ContainerStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Vault", description="A quiet vault")
    holder = await create_character(clean_neo4j, world.id, name="Holder")
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.UNLOCKED,
    )

    await location_store.create_location(location, source_id=world.id)
    await store.create_container(
        container,
        source_id=world.id,
        location_id=location.id,
        position="against the wall",
    )
    await clean_neo4j.execute_query(
        """
        MATCH (holder:Character {id: $holder_id})
        MATCH (container:Container {id: $container_id})
        MERGE (holder)-[:HOLDS]->(container)
        """,
        parameters_={
            "holder_id": holder.id,
            "container_id": container.id,
        },
    )

    assert await store.get_containers_by_location(location.id) == []


async def test_container_can_hold_items_equipment_and_containers(clean_neo4j):
    world = await create_world(clean_neo4j)
    container_store = ContainerStore(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    parent = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.OPEN,
    )
    child = Container(
        id=str(uuid4()),
        name="Pouch",
        description="A leather pouch",
        state=ContainerState.UNLOCKED,
    )
    item = Item(id=str(uuid4()), name="Coin", description="A copper coin", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=5, quality="tarnished")
    equipment = Equipment(id=str(uuid4()), name="Dagger", description="A short blade", quality="sharp")

    await container_store.create_container(parent, source_id=world.id)
    await container_store.create_container(child, source_id=world.id)
    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack, holder_id=parent.id)
    await equipment_store.create_equipment(equipment, source_id=world.id)

    await container_store.put_stack_in_container(stack.id, parent.id)
    await container_store.put_equipment_in_container(equipment.id, parent.id)
    assert await container_store.put_container_in_container(child.id, parent.id) == parent

    assert await container_store.get_held_stacks(parent.id) == [(item, stack)]
    assert await container_store.get_held_equipment(parent.id) == [equipment]
    assert await container_store.get_held_containers(parent.id) == [child]


async def test_item_unlocks_container(clean_neo4j):
    world = await create_world(clean_neo4j)
    container_store = ContainerStore(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    container = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.LOCKED,
    )
    key = Item(id=str(uuid4()), name="Key", description="A brass key", unique=True)

    await container_store.create_container(container, source_id=world.id)
    await item_store.create_item(key, source_id=world.id)
    await container_store.add_unlocking_item(key.id, container.id)

    assert await container_store.get_unlocking_items(container.id) == [key]

    await container_store.remove_unlocking_item(key.id, container.id)

    assert await container_store.get_unlocking_items(container.id) == []


async def test_background_character_can_hold_items_equipment_and_containers(clean_neo4j):
    world = await create_world(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    container_store = ContainerStore(clean_neo4j)
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Porter",
        description="A background porter",
    )
    item = Item(id=str(uuid4()), name="Coin", description="A copper coin", unique=False)
    stack = ItemStack(id=str(uuid4()), quantity=5, quality="tarnished")
    equipment = Equipment(id=str(uuid4()), name="Dagger", description="A short blade", quality="sharp")
    container = Container(
        id=str(uuid4()),
        name="Satchel",
        description="A canvas satchel",
        state=ContainerState.UNLOCKED,
    )

    await character_store.create_background_character(background_character, source_id=world.id)
    await item_store.create_item(item, source_id=world.id)
    await item_store.create_stack(item.id, stack, holder_id=background_character.id)
    await equipment_store.create_equipment(equipment, source_id=world.id)
    await container_store.create_container(container, source_id=world.id)

    await item_store.assign_stack(stack.id, holder_id=background_character.id)
    await equipment_store.change_hold_state(equipment.id, background_character.id)
    await container_store.assign_container(container.id, holder_id=background_character.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:BackgroundCharacter {id: $character_id})-[:HOLDS]->(held)
        RETURN labels(held) AS labels, held.id AS id
        """,
        parameters_={"character_id": background_character.id},
    )
    assert {
        (tuple(record["labels"]), record["id"])
        for record in result.records
    } == {
        (("Container",), container.id),
        (("Equipment",), equipment.id),
        (("ItemStack",), stack.id),
    }


async def test_copy_containers_preserves_relationships(clean_neo4j):
    world = await create_world(clean_neo4j)
    target_world = await create_world(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    container_store = ContainerStore(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    item_store = ItemStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Vault", description="A quiet vault")
    owner = await create_character(clean_neo4j, world.id, name="Owner")
    copied_owner = await create_character(clean_neo4j, target_world.id, name="Copied Owner")
    parent = Container(
        id=str(uuid4()),
        name="Chest",
        description="A wooden chest",
        state=ContainerState.OPEN,
    )
    child = Container(
        id=str(uuid4()),
        name="Pouch",
        description="A leather pouch",
        state=ContainerState.UNLOCKED,
    )
    equipment = Equipment(id=str(uuid4()), name="Dagger", description="A short blade", quality="sharp")
    copied_equipment = Equipment(id=str(uuid4()), name="Copied Dagger", description="A short blade", quality="sharp")
    key = Item(id=str(uuid4()), name="Key", description="A brass key", unique=True)

    await location_store.create_location(location, source_id=world.id)
    _, location_pairs, _ = await location_store.copy_locations(world.id, target_world.id)
    await container_store.create_container(parent, source_id=world.id, location_id=location.id, position="against the wall")
    await container_store.create_container(child, source_id=world.id)
    await equipment_store.create_equipment(equipment, source_id=world.id)
    await equipment_store.create_equipment(copied_equipment, source_id=target_world.id)
    await item_store.create_item(key, source_id=world.id)
    await container_store.assign_container(parent.id, owner_id=owner.id)
    await container_store.put_equipment_in_container(equipment.id, parent.id)
    await container_store.put_container_in_container(child.id, parent.id)
    await container_store.add_unlocking_item(key.id, parent.id)

    copied_containers, container_pairs = await container_store.copy_containers(
        world.id,
        target_world.id,
        location_pairs=location_pairs,
        entity_pairs=[
            {
                "source_id": owner.id,
                "copy_id": copied_owner.id,
            }
        ],
        equipment_pairs=[
            {
                "source_id": equipment.id,
                "copy_id": copied_equipment.id,
            }
        ],
    )

    assert {
        container.name
        for container in copied_containers
    } == {
        parent.name,
        child.name,
    }
    assert all(
        pair["source_id"] != pair["copy_id"]
        for pair in container_pairs
    )
    copied_parent_id = next(pair["copy_id"] for pair in container_pairs if pair["source_id"] == parent.id)
    copied_child_id = next(pair["copy_id"] for pair in container_pairs if pair["source_id"] == child.id)

    result = await clean_neo4j.execute_query(
        """
        MATCH (:Character {id: $owner_id})-[:OWNS]->(:Container {id: $parent_id})
        MATCH (:Container {id: $parent_id})-[:HOLDS]->(:Equipment {id: $equipment_id})
        MATCH (:Container {id: $parent_id})-[:HOLDS]->(:Container {id: $child_id})
        MATCH (:Item {id: $item_id})-[:UNLOCKS]->(:Container {id: $parent_id})
        MATCH (:Container {id: $parent_id})-[:PRESENT_IN]->(:Location {id: $location_id})
        RETURN count(*) AS relationship_count
        """,
        parameters_={
            "owner_id": copied_owner.id,
            "parent_id": copied_parent_id,
            "child_id": copied_child_id,
            "equipment_id": copied_equipment.id,
            "item_id": key.id,
            "location_id": location_pairs[0]["copy_id"],
        },
    )

    assert result.records[0]["relationship_count"] == 1
