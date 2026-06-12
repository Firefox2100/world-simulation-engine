import pytest

from world_simulation_engine.model.world import World, WorldCreate, CharacterInventory


@pytest.fixture
def mock_world_create(mock_simulation,
                      mock_simulation_state_1,
                      mock_characters,
                      mock_locations,
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
                      mock_tasks,
                      mock_world_entries,
                      ) -> WorldCreate:
    return WorldCreate(
        name=mock_simulation.name,
        description=mock_simulation.description,
        agent_preset=mock_simulation.agent_preset,
        data_preset=mock_simulation.data_preset,
        embedding_profile=mock_simulation.embedding_profile,
        language=mock_simulation.language,
        state=mock_simulation_state_1,
        characters=mock_characters,
        locations=mock_locations,
        factions=mock_factions,
        faction_relationships=mock_faction_relationships,
        inventory={
            0: CharacterInventory(
                items=mock_items_0,
                equipments=mock_equipments_0,
            ),
            1: CharacterInventory(
                items=mock_items_1,
                equipments=mock_equipments_1,
            ),
            2: CharacterInventory(
                items=mock_items_2,
                equipments=mock_equipments_2,
            ),
            3: CharacterInventory(
                items=mock_items_3,
                equipments=mock_equipments_3,
            ),
            4: CharacterInventory(
                items=mock_items_4,
                equipments=mock_equipments_4,
            ),
        },
        tasks=mock_tasks,
        world_entries=mock_world_entries,
        turn_records=[],
    )


async def test_create_world(db,
                            mock_world_create,
                            ):
    result = await db.world.create(world=mock_world_create)

    assert isinstance(result, World)


async def test_get_world(db,
                         mock_world_create,
                         ):
    result = await db.world.create(world=mock_world_create)
    fetched = await db.world.get(result.id)

    assert isinstance(fetched, World)
    assert fetched.id == result.id
    assert fetched.name == mock_world_create.name


async def test_list_worlds(db,
                           mock_world_create,
                           ):
    await db.world.create(world=mock_world_create)
    fetched = await db.world.list()

    assert isinstance(fetched, list)
    assert len(fetched) == 1
