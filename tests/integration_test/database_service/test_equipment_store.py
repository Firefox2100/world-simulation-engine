from uuid import uuid4
from datetime import UTC, datetime

from world_simulation_engine.model import Equipment, Location
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.equipment_store import EquipmentStore, InventoryEquipment
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.model import Simulation
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

    assert await store.create_equipment(equipment, source_id=world.id) == equipment

    assert await store.get_equipment(equipment.id) == equipment

    result = await clean_neo4j.execute_query(
        """
        MATCH (:World {id: $source_id})-[:CONTAINS]->(:Equipment {id: $equipment_id})
        RETURN count(*) AS link_count
        """,
        parameters_={"source_id": world.id, "equipment_id": equipment.id},
    )
    assert result.records[0]["link_count"] == 1


async def test_list_update_and_delete_equipment(clean_neo4j):
    world = await create_world(clean_neo4j)
    store = EquipmentStore(clean_neo4j)
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )

    await store.create_equipment(equipment, source_id=world.id)

    assert await store.list_equipment() == [equipment]
    assert await store.list_equipment(world_id=world.id) == [equipment]

    updated_equipment = await store.update_equipment(
        equipment.id,
        {
            "name": "Updated Lantern",
            "quality": "polished",
        },
    )

    assert updated_equipment == Equipment(
        id=equipment.id,
        name="Updated Lantern",
        description=equipment.description,
        quality="polished",
    )
    assert await store.delete_equipment(equipment.id) is True
    assert await store.get_equipment(equipment.id) is None
    assert await store.delete_equipment(equipment.id) is False


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

    assert await equipment_store.list_equipment(owner_id=holder.id) == [equipment]
    assert await equipment_store.list_equipment(holder_id=holder.id) == [equipment]

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
    assert await equipment_store.list_equipment(location_id=location.id) == [equipment]


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


async def test_copy_equipment_preserves_location_owner_and_equipped_relationships(clean_neo4j):
    world = await create_world(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)
    equipment_store = EquipmentStore(clean_neo4j)
    location_store = LocationStore(clean_neo4j)
    simulation_store = SimulationStore(clean_neo4j)
    location = Location(id=str(uuid4()), name="Cave", description="A dark cave")
    carried_equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    placed_equipment = Equipment(
        id=str(uuid4()),
        name="Helmet",
        description="A dented helmet",
        quality="dented",
    )
    holder = await create_character(clean_neo4j, world.id, name="Explorer")
    simulation = await simulation_store.create_simulation(
        simulation=Simulation(
            id=str(uuid4()),
            name="Test Simulation",
            description="A test simulation",
            current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        ),
        world_id=world.id,
    )

    await location_store.create_location(location, source_id=world.id)
    _, location_pairs, _ = await location_store.copy_locations(world.id, simulation.id)
    _, character_pairs = await character_store.copy_characters(
        world.id,
        simulation.id,
        return_pairs=True,
    )
    await equipment_store.create_equipment(carried_equipment, source_id=world.id)
    await equipment_store.create_equipment(
        placed_equipment,
        source_id=world.id,
        location_id=location.id,
        position="near the entrance",
    )
    await equipment_store.change_owner(carried_equipment.id, holder.id)
    await equipment_store.change_hold_state(
        carried_equipment.id,
        holder.id,
        equipped=True,
        equipped_position="left hand",
    )
    copied_equipment, equipment_pairs = await equipment_store.copy_equipment(
        world.id,
        simulation.id,
        location_pairs=location_pairs,
        entity_pairs=character_pairs,
    )

    assert {
        equipment.name
        for equipment in copied_equipment
    } == {
        carried_equipment.name,
        placed_equipment.name,
    }
    assert all(
        pair["source_id"] != pair["copy_id"]
        for pair in equipment_pairs
    )

    copied_holder_id = character_pairs[0]["copy_id"]
    inventory = await equipment_store.get_equipment_inventory(copied_holder_id)
    copied_carried_equipment = next(
        equipment
        for equipment in copied_equipment
        if equipment.name == carried_equipment.name
    )
    copied_placed_equipment = next(
        equipment
        for equipment in copied_equipment
        if equipment.name == placed_equipment.name
    )

    assert InventoryEquipment(
        **copied_carried_equipment.model_dump(),
        equipped=True,
        equipped_position="left hand",
    ) in inventory
    assert await equipment_store.get_equipment_by_location(location_pairs[0]["copy_id"]) == [
        (copied_placed_equipment, await location_store.get_location(location_pairs[0]["copy_id"]), "near the entrance", None)
    ]
