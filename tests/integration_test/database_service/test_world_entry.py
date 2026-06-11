import pytest

from world_simulation_engine.model import WorldEntry


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


async def test_create_world_entry(db,
                                  mock_world_entries,
                                  ):
    result = await db.entry.create(
        world_entry=mock_world_entries[0],
        simulation_id=1,
    )

    assert isinstance(result, WorldEntry)


async def test_get_world_entry(db,
                               mock_world_entries,
                               ):
    result = await db.entry.create(
        world_entry=mock_world_entries[0],
        simulation_id=1,
    )

    fetched = await db.entry.get(result.id)

    assert isinstance(fetched, WorldEntry)
    assert fetched.id == result.id
    assert fetched.scope == mock_world_entries[0].scope


async def test_list_world_entries(db,
                                  mock_world_entries,
                                  ):
    for world_entry in mock_world_entries:
        await db.entry.create(
            world_entry=world_entry,
            simulation_id=1,
        )

    fetched = await db.entry.list(simulation_id=1)
    assert isinstance(fetched, list)
    assert len(fetched) == len(mock_world_entries)
