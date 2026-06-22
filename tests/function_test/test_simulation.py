import pytest
from langchain_core.messages import AIMessage

from world_simulation_engine.model.simulation import Simulation


@pytest.fixture
def injected_simulation(mock_client, mock_world_create) -> Simulation:
    connection_response = mock_client.post(
        "/connections/llm",
        json={
            "provider": "ollama",
            "name": "Test LLM Connection",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
    )
    assert connection_response.status_code == 200

    world_payload = mock_world_create.model_dump(mode="json")
    post_response = mock_client.post("/worlds", json=world_payload)
    assert post_response.status_code == 200

    create_simulation_response = mock_client.post("/worlds/1/new-simulation")
    assert create_simulation_response.status_code == 200
    simulation_json = create_simulation_response.json()

    return Simulation.model_validate(simulation_json)


def test_list_simulations(mock_client, injected_simulation):
    list_response = mock_client.get("/simulations")
    assert list_response.status_code == 200
    list_json = list_response.json()

    assert isinstance(list_json, list)
    assert len(list_json) == 1


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


def test_run_simulation(mock_client, injected_simulation, fake_model):
    user_input = "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied before Harlan vanished."

    fake_model.responses = [
        # User input resolver
        AIMessage(
            content='{"user_input_resolution":{"accepted":true,"input_kind":"player_dialogue","legality":"legal",'
                    '"rejection_reason":null,"user_retry_instruction":null,"resolved_actions":[{"actor_id":'
                    '4,"actor_name":"Arthur Moore","original_intent":"ask Clara whether Room 7 was occupied '
                    'before Harlan vanished","final_status":"succeeded","resolved_order":null,"visible_result":'
                    '"Arthur remains at the bar and asks Clara whether Room 7 was occupied before Director '
                    'Harlan disappeared.","private_result_for_actor":null,"failure_reason":null,'
                    '"blocking_actor_id":null,"blocking_entity_id":null,"state_change_hints":[],'
                    '"world_entry_hints":[],"requires_actor_retry":false,"retry_instruction":null}],"conflicts":'
                    '[],"scene_result_summary":"","next_round_note":"","narrator_context": [],'
                    '"state_update_suggestions":["Task 4 (Discover identity of unknown visitor who stayed in '
                    'Room 7) has received a direct inquiry attempt","Clara Whitlock is now aware Arthur is '
                    'specifically investigating Room 7"],"pending_world_entry_suggestions":[],'
                    '"requires_director_rerun":false,"director_rerun_reason":null,"notes":"Question posed to '
                    'Clara. Her answer (truthful, evasive, or partial) will be determined in NPC stage based '
                    'on her private knowledge and willingness to reveal information."}}'
        ),
    ]

    run_response = mock_client.post(
        f"/simulations/{injected_simulation.id}/input",
        json={
            "user_input": user_input
        }
    )
    assert run_response.status_code == 200
    run_json = run_response.json()

    with mock_client.stream("GET", f"/simulations/runs/{run_json['run_id']}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)

        assert len(lines) > 0
