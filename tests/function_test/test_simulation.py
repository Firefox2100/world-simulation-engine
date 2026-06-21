import pytest

from world_simulation_engine.model.simulation import Simulation


@pytest.fixture
def injected_simulation(mock_client, mock_world_create) -> Simulation:
    world_payload = mock_world_create.model_dump(mode="json")

    post_response = mock_client.post("/worlds", json=world_payload)
    assert post_response.status_code == 200

    create_simulation_response = mock_client.post("/worlds/1/new-simulation")
    assert create_simulation_response.status_code == 200
    simulation_json = create_simulation_response.json()

    return Simulation.model_validate(simulation_json)


def test_get_simulation(mock_client, injected_simulation):
    simulation_response = mock_client.get(f"/simulations/{injected_simulation.id}")
    assert simulation_response.status_code == 200
    simulation_json = simulation_response.json()

    simulation = Simulation.model_validate(simulation_json)
    assert simulation.id == injected_simulation.id
    assert simulation.name == injected_simulation.name


def test_delete_simulation(mock_client, injected_simulation):
    deletion_response = mock_client.delete(f"/simulations/{injected_simulation.id}")
    assert deletion_response.status_code == 204

    simulation_list_response = mock_client.get("/simulations")
    assert simulation_list_response.status_code == 200
    simulation_list_json = simulation_list_response.json()
    assert isinstance(simulation_list_json, list)
    assert len(simulation_list_json) == 0
