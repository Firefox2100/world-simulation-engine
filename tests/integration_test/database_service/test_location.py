import pytest

from world_simulation_engine.model import Location


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                ):
    await db.simulation.create(simulation=mock_simulation)


async def test_create_location(db,
                               mock_locations,
                               ):
    result = await db.location.create(
        location=mock_locations[0],
        simulation_id=1,
    )

    assert isinstance(result, Location)


async def test_get_location(db,
                            mock_locations,
                            ):
    result = await db.location.create(
        location=mock_locations[0],
        simulation_id=1,
    )

    fetched = await db.location.get(location_id=result.id)

    assert isinstance(fetched, Location)
    assert fetched.id == result.id
    assert fetched.primary_location == mock_locations[0].primary_location
    assert fetched.detailed_location == mock_locations[0].detailed_location
    assert fetched.scene == mock_locations[0].scene


async def test_list_locations(db,
                              mock_locations,
                              ):
    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    fetched = await db.location.list(simulation_id=1)

    assert len(fetched) == len(mock_locations)
