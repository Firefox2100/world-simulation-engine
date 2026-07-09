from uuid import uuid4

from world_simulation_engine.model import Equipment, Location
from world_simulation_engine.service.database.equipment_store import EquipmentStore, InventoryEquipment
from world_simulation_engine.service.database.location_store import LocationStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_missing_equipment_returns_none(clean_neo4j):
    store = EquipmentStore(clean_neo4j)

    assert await store.get_equipment(str(uuid4())) is None


async def test_create_equipment(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = EquipmentStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )

    await store.create_equipment(equipment, source_id=world.id)

    assert await store.get_equipment(equipment.id) == equipment

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:Equipment {id: $equipment_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "equipment_id": equipment.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_equipment_inventory_hold_and_equip_states(clean_neo4j):
    world = await create_world(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    holder = await create_character(clean_neo4j, world.id, name="Explorer")

    await equipment_store.create_equipment(equipment, source_id=world.id)
    await equipment_store.change_owner(equipment.id, holder.id)
    await equipment_store.change_hold_state(equipment.id, holder.id, equipped=False)

    held_inventory = await equipment_store.get_equipment_inventory(holder.id)
    assert held_inventory == [InventoryEquipment(**equipment.model_dump(), equipped=False)]

    await equipment_store.change_hold_state(
        equipment.id,
        holder.id,
        equipped=True,
        equipped_position="left hand",
    )

    equipped_inventory = await equipment_store.get_equipment_inventory(holder.id)
    assert equipped_inventory == [
        InventoryEquipment(**equipment.model_dump(), equipped=True, equipped_position="left hand")
    ]


async def test_equipment_location_assignment(clean_neo4j):
    world = await create_world(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    location = Location(id=str(uuid4()), name="Cave", description="A dark cave")

    await location_store.create_location(location, source_id=world.id)
    await equipment_store.create_equipment(
        equipment,
        source_id=world.id,
        location_id=location.id,
        position="near the entrance",
    )

    assert await equipment_store.get_equipment_by_location(location.id) == [
        (equipment, location, "near the entrance", None)
    ]


async def test_hold_equipment_removes_location_presence(clean_neo4j):
    world = await create_world(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    location = Location(id=str(uuid4()), name="Cave", description="A dark cave")
    holder = await create_character(clean_neo4j, world.id, name="Explorer")

    await location_store.create_location(location, source_id=world.id)
    await equipment_store.create_equipment(
        equipment,
        source_id=world.id,
        location_id=location.id,
        position="near the entrance",
    )
    await equipment_store.change_hold_state(equipment.id, holder.id)

    assert await equipment_store.get_equipment_by_location(location.id) == []


async def test_location_equipment_query_ignores_equipped_equipment(clean_neo4j):
    world = await create_world(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    location = Location(id=str(uuid4()), name="Cave", description="A dark cave")
    holder = await create_character(clean_neo4j, world.id, name="Explorer")

    await location_store.create_location(location, source_id=world.id)
    await equipment_store.create_equipment(
        equipment,
        source_id=world.id,
        location_id=location.id,
        position="near the entrance",
    )
    await clean_neo4j.execute_query(
        """
        MATCH (holder:Character {id: $holder_id})
        MATCH (equipment:Equipment {id: $equipment_id})
        MERGE (holder)-[:EQUIPS {position: 'left hand'}]->(equipment)
        """,
        parameters_={
            "holder_id": holder.id,
            "equipment_id": equipment.id,
        },
    )

    assert await equipment_store.get_equipment_by_location(location.id) == []
