from world_simulation_engine.model import Simulation, SimulationState


async def test_create_simulation(db,
                                 mock_simulation,
                                 ):
    result = await db.simulation.create(simulation=mock_simulation)

    assert isinstance(result, Simulation)


async def test_get_simulation(db,
                              mock_simulation,
                              ):
    result = await db.simulation.create(simulation=mock_simulation)

    fetched = await db.simulation.get(result.id)

    assert isinstance(fetched, Simulation)
    assert fetched.id == result.id
    assert fetched.name == mock_simulation.name
    assert fetched.description == mock_simulation.description


async def test_list_simulations(db,
                                mock_simulation,
                                ):
    await db.simulation.create(simulation=mock_simulation)

    fetched = await db.simulation.list()

    assert isinstance(fetched, list)
    assert len(fetched) == 1


async def test_list_simulations_with_pagination(db,
                                                mock_simulation,
                                                ):
    first = await db.simulation.create(simulation=mock_simulation.model_copy(update={"name": "First Simulation"}))
    second = await db.simulation.create(simulation=mock_simulation.model_copy(update={"name": "Second Simulation"}))
    third = await db.simulation.create(simulation=mock_simulation.model_copy(update={"name": "Third Simulation"}))

    fetched = await db.simulation.list(limit=2, offset=1)

    assert [simulation.id for simulation in fetched] == [second.id, third.id]
    assert first.id not in [simulation.id for simulation in fetched]


async def test_create_simulation_state(db,
                                       mock_simulation,
                                       mock_simulation_state_1,
                                       mock_locations,
                                       ):
    await db.simulation.create(simulation=mock_simulation)
    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    result = await db.state.create(state=mock_simulation_state_1)

    assert isinstance(result, SimulationState)


async def test_get_simulation_state(db,
                                    mock_simulation,
                                    mock_simulation_state_1,
                                    mock_locations,
                                    ):
    await db.simulation.create(simulation=mock_simulation)
    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    result = await db.state.create(state=mock_simulation_state_1)

    fetched = await db.state.get(result.id)

    assert isinstance(fetched, SimulationState)
    assert fetched.id == result.id
    assert fetched.scene == mock_simulation_state_1.scene
