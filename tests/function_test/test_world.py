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


def test_list_worlds(mock_client, mock_world_create):
    post_response = mock_client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json"),
    )
    assert post_response.status_code == 200

    list_response = mock_client.get("/worlds")
    assert list_response.status_code == 200
    response_json = list_response.json()

    assert isinstance(response_json, list)
    assert len(response_json) == 1
    assert response_json[0]["id"] == 1
    assert response_json[0]["name"] == mock_world_create.name
    assert response_json[0]["description"] == mock_world_create.description
    assert response_json[0]["language"] == mock_world_create.language
    assert response_json[0]["enable_tts"] is True
    assert response_json[0]["enable_image_generation"] is True


def test_get_world(mock_client, mock_world_create):
    post_response = mock_client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json"),
    )
    assert post_response.status_code == 200

    get_response = mock_client.get("/worlds/1")
    assert get_response.status_code == 200
    response_json = get_response.json()

    assert response_json["id"] == 1
    assert response_json["name"] == mock_world_create.name
    assert response_json["description"] == mock_world_create.description
    assert response_json["language"] == mock_world_create.language
    assert response_json["enable_tts"] is True
    assert response_json["enable_image_generation"] is True


def test_update_world(mock_client, mock_world_create):
    post_response = mock_client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json"),
    )
    assert post_response.status_code == 200

    patch_response = mock_client.patch(
        "/worlds/1",
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
    assert response_json["language"] == mock_world_create.language
    assert response_json["enable_tts"] is False
    assert response_json["enable_image_generation"] is True


def test_delete_world(mock_client, mock_world_create):
    post_response = mock_client.post(
        "/worlds",
        json=mock_world_create.model_dump(mode="json"),
    )
    assert post_response.status_code == 200

    delete_response = mock_client.delete("/worlds/1")
    assert delete_response.status_code == 204

    get_response = mock_client.get("/worlds/1")
    assert get_response.status_code == 404


def test_create_new_simulation(mock_client, mock_world_create):
    world_payload = mock_world_create.model_dump(mode="json")

    post_response = mock_client.post("/worlds", json=world_payload)
    assert post_response.status_code == 200

    create_simulation_response = mock_client.post("/worlds/1/new-simulation")
    assert create_simulation_response.status_code == 200
    simulation_json = create_simulation_response.json()

    assert simulation_json["id"] == 1
    assert simulation_json["name"] == world_payload["name"]
    assert simulation_json["description"] == world_payload["description"]
    assert simulation_json["language"] == world_payload["language"]
    assert simulation_json["enable_tts"] is True
    assert simulation_json["enable_image_generation"] is True

    simulation_list_response = mock_client.get("/simulations")
    assert simulation_list_response.status_code == 200
    simulation_list_json = simulation_list_response.json()

    assert isinstance(simulation_list_json, list)
    assert len(simulation_list_json) == 1
    assert simulation_list_json[0]["id"] == 1
    assert simulation_list_json[0]["name"] == world_payload["name"]
