from world_simulation_engine.model.world import World


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


async def test_list_worlds_with_pagination(db,
                                           mock_world_create,
                                           ):
    first = await db.world.create(world=mock_world_create.model_copy(update={"name": "First World"}))
    second = await db.world.create(world=mock_world_create.model_copy(update={"name": "Second World"}))
    third = await db.world.create(world=mock_world_create.model_copy(update={"name": "Third World"}))

    fetched = await db.world.list(limit=2, offset=1)

    assert [world.id for world in fetched] == [second.id, third.id]
    assert first.id not in [world.id for world in fetched]


async def test_update_world(db,
                           mock_world_create,
                           ):
    result = await db.world.create(world=mock_world_create)
    assert isinstance(result, World)

    await db.world.update(
        world_id=result.id,
        patched_data={
            "name": "An updated name",
        }
    )

    fetched = await db.world.get(result.id)
    assert isinstance(fetched, World)
    assert fetched.name == "An updated name"
