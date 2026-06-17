import pytest

from world_simulation_engine.component import TurnGenerator


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                mock_simulation_state_1,
                mock_locations,
                mock_characters,
                mock_tasks,
                mock_world_entries,
                mock_items_0,
                mock_items_1,
                mock_items_2,
                mock_items_3,
                mock_items_4,
                mock_equipments_0,
                mock_equipments_1,
                mock_equipments_2,
                mock_equipments_3,
                mock_equipments_4,
                mock_factions,
                mock_faction_relationships,
                mock_llm_connection_create,
                ):
    await db.connection.llm.create(mock_llm_connection_create)
    await db.simulation.create(mock_simulation)
    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    await db.state.create(mock_simulation_state_1)
    for character in mock_characters:
        await db.character.create(character=character, simulation_id=1)

    for task in mock_tasks:
        await db.task.create(task=task)
    for world_entry in mock_world_entries:
        await db.entry.create(world_entry=world_entry, simulation_id=1)
    for item in mock_items_0:
        await db.item.create(item=item, simulation_id=1)
    for item in mock_items_1:
        await db.item.create(item=item, simulation_id=1, character_id=1)
    for item in mock_items_2:
        await db.item.create(item=item, simulation_id=1, character_id=2)
    for item in mock_items_3:
        await db.item.create(item=item, simulation_id=1, character_id=3)
    for item in mock_items_4:
        await db.item.create(item=item, simulation_id=1, character_id=4)
    for equipment in mock_equipments_0:
        await db.equipment.create(equipment=equipment, simulation_id=1)
    for equipment in mock_equipments_1:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=1)
    for equipment in mock_equipments_2:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=2)
    for equipment in mock_equipments_3:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=3)
    for equipment in mock_equipments_4:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=4)

    for faction in mock_factions:
        await db.faction.create(faction=faction, simulation_id=1)
    for relationship in mock_faction_relationships:
        await db.faction_relationship.create(relationship=relationship)


async def test_write_to_database(db,
                                 mock_generator_output_payload,
                                 ):
    turn_generator = TurnGenerator(db)

    result = await turn_generator.persist_state_to_database(mock_generator_output_payload)
