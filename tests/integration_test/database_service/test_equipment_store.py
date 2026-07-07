from uuid import uuid4

from world_simulation_engine.model import Equipment
from world_simulation_engine.service.database.equipment_store import EquipmentStore, InventoryEquipment
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_missing_equipment_returns_none(clean_neo4j):
    store = EquipmentStore(clean_neo4j)

    assert await store.get_equipment(str(uuid4())) is None


async def test_create_equipment(clean_neo4j):
    store = EquipmentStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )

    await store.create_equipment(equipment)

    assert await store.get_equipment(equipment.id) == equipment


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

    await equipment_store.create_equipment(equipment)
    await equipment_store.change_owner(equipment.id, holder.id)
    await equipment_store.change_hold_state(equipment.id, holder.id, equipped=False)

    held_inventory = await equipment_store.get_equipment_inventory(holder.id)
    assert held_inventory == [InventoryEquipment(**equipment.model_dump(), equipped=False)]

    await equipment_store.change_hold_state(equipment.id, holder.id, equipped=True)

    equipped_inventory = await equipment_store.get_equipment_inventory(holder.id)
    assert equipped_inventory == [InventoryEquipment(**equipment.model_dump(), equipped=True)]
