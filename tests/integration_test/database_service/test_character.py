import pytest

from world_simulation_engine.model import Character


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                mock_locations,
                ):
    await db.simulation.create(simulation=mock_simulation)

    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)


async def test_create_character(db,
                                mock_characters,
                                ):
    result = await db.character.create(
        character=mock_characters[0],
        simulation_id=1,
    )

    assert isinstance(result, Character)


async def test_get_character(db,
                             mock_characters,
                             ):
    result = await db.character.create(
        character=mock_characters[0],
        simulation_id=1,
    )

    fetched = await db.character.get(result.id)

    assert isinstance(fetched, Character)
    assert fetched.id == result.id
    assert fetched.name == mock_characters[0].name
    assert fetched.gender == mock_characters[0].gender
    assert fetched.age == mock_characters[0].age


async def test_list_characters(db,
                               mock_characters,
                               ):
    for character in mock_characters:
        await db.character.create(
            character=character,
            simulation_id=1,
        )

    fetched = await db.character.list(simulation_id=1)

    assert isinstance(fetched, list)
    assert len(fetched) == len(mock_characters)
