import pytest

from world_simulation_engine.model import Item, Equipment


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                mock_locations,
                mock_characters,
                ):
    await db.simulation.create(mock_simulation)

    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    for character in mock_characters:
        await db.character.create(character=character, simulation_id=1)


async def test_create_item(db,
                           mock_items_0,
                           ):
    result = await db.item.create(
        item=mock_items_0[0],
        simulation_id=1,
    )

    assert isinstance(result, Item)


async def test_get_item(db,
                        mock_items_0,
                        ):
    result = await db.item.create(
        item=mock_items_0[0],
        simulation_id=1,
    )

    fetched = await db.item.get(result.id)

    assert isinstance(fetched, Item)
    assert fetched.id == result.id
    assert fetched.name == mock_items_0[0].name


async def test_list_items(db,
                          mock_items_0,
                          mock_items_1,
                          ):
    for item in mock_items_0:
        await db.item.create(
            item=item,
            simulation_id=1,
        )

    for item in mock_items_1:
        await db.item.create(
            item=item,
            simulation_id=1,
            character_id=1,
        )

    fetched = await db.item.list(
        simulation_id=1,
    )

    assert isinstance(fetched, list)
    assert len(fetched) == len(mock_items_0)

    fetched = await db.item.list(
        simulation_id=1,
        character_id=1,
    )

    assert isinstance(fetched, list)
    assert len(fetched) == len(mock_items_1)


async def test_create_equipment(db,
                                mock_equipments_4,
                                ):
    result = await db.equipment.create(
        equipment=mock_equipments_4[0],
        simulation_id=1,
    )

    assert isinstance(result, Equipment)


async def test_get_equipment(db,
                            mock_equipments_4,
                            ):
    result = await db.equipment.create(
        equipment=mock_equipments_4[0],
        simulation_id=1,
    )

    fetched = await db.equipment.get(result.id)

    assert isinstance(fetched, Equipment)
    assert fetched.id == result.id
    assert fetched.name == mock_equipments_4[0].name


async def test_list_equipment(db,
                              mock_equipments_4,
                              ):
    for equipment in mock_equipments_4:
        await db.equipment.create(
            equipment=equipment,
            simulation_id=1,
        )

    fetched = await db.equipment.list(simulation_id=1)

    assert isinstance(fetched, list)
    assert len(fetched) == len(mock_equipments_4)
