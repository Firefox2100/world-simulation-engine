def test_create_llm_connection(mock_client):
    response = mock_client.post(
        "/connections/llm",
        json={
            "provider": "ollama",
            "name": "Test LLM Connection",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["id"] == 1
    assert response_json["name"] == "Test LLM Connection"
    assert response_json["base_url"] == "http://localhost:11434"
    assert response_json["api_key"] is None


def test_list_llm_connections(mock_client):
    post_response = mock_client.post(
        "/connections/llm",
        json={
            "provider": "ollama",
            "name": "Test LLM Connection",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
    )
    assert post_response.status_code == 200

    list_response = mock_client.get("/connections/llm")
    assert list_response.status_code == 200
    response_json = list_response.json()

    assert isinstance(response_json, list)
    assert len(response_json) == 1
    assert response_json[0]["id"] == 1
    assert response_json[0]["name"] == "Test LLM Connection"
    assert response_json[0]["base_url"] == "http://localhost:11434"
    assert response_json[0]["api_key"] is None


def test_get_llm_connection(mock_client):
    post_response = mock_client.post(
        "/connections/llm",
        json={
            "provider": "ollama",
            "name": "Test LLM Connection",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
    )
    assert post_response.status_code == 200

    get_response = mock_client.get("/connections/llm/1")
    assert get_response.status_code == 200
    response_json = get_response.json()
    assert response_json["id"] == 1
    assert response_json["name"] == "Test LLM Connection"
    assert response_json["base_url"] == "http://localhost:11434"
    assert response_json["api_key"] is None


def test_get_llm_connection_not_found(mock_client):
    get_response = mock_client.get("/connections/llm/1")

    assert get_response.status_code == 404


def test_update_llm_connection(mock_client):
    post_response = mock_client.post(
        "/connections/llm",
        json={
            "provider": "ollama",
            "name": "Test LLM Connection",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
    )
    assert post_response.status_code == 200

    patch_response = mock_client.patch(
        "/connections/llm/1",
        json={
            "name": "Another LLM Connection",
            "api_key": "dummy-api-key",
        }
    )
    assert patch_response.status_code == 200
    response_json = patch_response.json()
    assert response_json["name"] == "Another LLM Connection"
    assert response_json["base_url"] == "http://localhost:11434"
    assert response_json["api_key"] == "dummy-api-key"


def test_delete_llm_connection(mock_client):
    post_response = mock_client.post(
        "/connections/llm",
        json={
            "provider": "ollama",
            "name": "Test LLM Connection",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
    )
    assert post_response.status_code == 200

    delete_response = mock_client.delete("/connections/llm/1")
    assert delete_response.status_code == 204

    list_response = mock_client.get("/connections/llm")
    assert list_response.status_code == 200
    response_json = list_response.json()
    assert isinstance(response_json, list)
    assert len(response_json) == 0
