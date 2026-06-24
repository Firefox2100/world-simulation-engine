import pytest

from world_simulation_engine.model.world import World


@pytest.fixture(autouse=True)
def setup(mock_client, mock_llm_connection_create):
    post_response = mock_client.post(
        "/connections/llm",
        json=mock_llm_connection_create.model_dump(mode="json"),
    )

    assert post_response.status_code == 200


@pytest.fixture
def injected_world(mock_client, mock_world_create) -> World:
    post_response = mock_client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json"),
    )
    assert post_response.status_code == 200
    world_json = post_response.json()

    return World.model_validate(world_json)


def test_create_world(mock_client, mock_world_create):
    response = mock_client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json"),
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["id"] == 1
    assert response_json["name"] == mock_world_create.name
    assert response_json["description"] == mock_world_create.description
    assert response_json["language"] == mock_world_create.language
    assert response_json["enable_tts"] is True
    assert response_json["enable_image_generation"] is True


def test_list_worlds(mock_client,
                     injected_world,
                     ):
    list_response = mock_client.get("/worlds")
    assert list_response.status_code == 200
    response_json = list_response.json()

    assert isinstance(response_json, list)
    assert len(response_json) == 1
    assert response_json[0]["id"] == injected_world.id
    assert response_json[0]["name"] == injected_world.name
    assert response_json[0]["description"] == injected_world.description
    assert response_json[0]["language"] == injected_world.language
    assert response_json[0]["enable_tts"] is True
    assert response_json[0]["enable_image_generation"] is True


def test_get_world(mock_client, injected_world):
    get_response = mock_client.get(f"/worlds/{injected_world.id}")
    assert get_response.status_code == 200
    response_json = get_response.json()

    assert response_json["id"] == 1
    assert response_json["name"] == injected_world.name
    assert response_json["description"] == injected_world.description
    assert response_json["language"] == injected_world.language
    assert response_json["enable_tts"] is True
    assert response_json["enable_image_generation"] is True


def test_update_world(mock_client, injected_world):
    patch_response = mock_client.patch(
        f"/worlds/{injected_world.id}",
        json={
            "name": "Updated World Name",
            "description": "Updated world description",
            "enable_tts": False,
        },
    )
    assert patch_response.status_code == 200
    response_json = patch_response.json()

    assert response_json["id"] == 1
    assert response_json["name"] == "Updated World Name"
    assert response_json["description"] == "Updated world description"
    assert response_json["language"] == injected_world.language
    assert response_json["enable_tts"] is False
    assert response_json["enable_image_generation"] is True


def test_delete_world(mock_client, injected_world):
    delete_response = mock_client.delete(f"/worlds/{injected_world.id}")
    assert delete_response.status_code == 204

    get_response = mock_client.get(f"/worlds/{injected_world.id}")
    assert get_response.status_code == 404


def test_create_new_simulation(mock_client, injected_world):
    create_simulation_response = mock_client.post(f"/worlds/{injected_world.id}/new-simulation")
    assert create_simulation_response.status_code == 200
    simulation_json = create_simulation_response.json()

    assert simulation_json["id"] == 1
    assert simulation_json["name"] == injected_world.name
    assert simulation_json["description"] == injected_world.description
    assert simulation_json["language"] == injected_world.language
    assert simulation_json["enable_tts"] is True
    assert simulation_json["enable_image_generation"] is True

    simulation_list_response = mock_client.get("/simulations")
    assert simulation_list_response.status_code == 200
    simulation_list_json = simulation_list_response.json()

    assert isinstance(simulation_list_json, list)
    assert len(simulation_list_json) == 1
    assert simulation_list_json[0]["id"] == 1
    assert simulation_list_json[0]["name"] == injected_world.name
