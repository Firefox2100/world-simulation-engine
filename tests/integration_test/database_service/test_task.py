import pytest

from world_simulation_engine.model import Task


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


async def test_create_task(db,
                           mock_tasks,
                           ):
    result = await db.task.create(mock_tasks[0])

    assert isinstance(result, Task)


async def test_get_task(db,
                        mock_tasks,
                        ):
    result = await db.task.create(mock_tasks[0])

    fetched = await db.task.get(result.id)

    assert isinstance(fetched, Task)
    assert fetched.id == result.id
    assert fetched.character_ids == mock_tasks[0].character_ids


async def test_list_tasks(db,
                          mock_tasks,
                          ):
    for task in mock_tasks:
        await db.task.create(task)

    fetched = await db.task.list()

    assert isinstance(fetched, list)
    assert len(fetched) == len(mock_tasks)
