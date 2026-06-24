import pytest
from unittest.mock import patch, PropertyMock
from langchain_core.messages import AIMessage

from world_simulation_engine.model.simulation import Simulation
from world_simulation_engine.service import NarratorAgent, CommitterAgent
from .utils import FakeStructuredListChatModel


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
            content='{"accepted":true,"input_kind":"player_dialogue","legality":"legal",'
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
                    'on her private knowledge and willingness to reveal information."}'
        ),
        # Director generation tool-calling
        AIMessage(
            content="NO_TOOL_NEEDED",
        ),
        # Director planning
        AIMessage(
            content='{"scene_focus":"Arthur questions Clara about Room 7 occupancy prior to Director Harlan\'s '
                    'disappearance during the Founder\'s Festival at the Iron Stag Inn.","activations":[{"'
                    'character_id":3,"character_name":"Clara Whitlock","activate":true,"priority":85,"reason":'
                    '"Directly addressed by player\'s question about Room 7; possesses relevant inn records and '
                    'memory of the visitor; private task #12 aligns with this inquiry.","activation_sources":{'
                    '"public_state":false,"private_state":true,"public_task":false,"private_task":true,'
                    '"scene_opportunity":true,"user_input":true},"private_motive_used":true},{"character_id":1,'
                    '"character_name":"Eleanor Graves","activate":true,"priority":45,"reason":"Present at the '
                    'bar; has vested interest in monitoring Arthur\'s investigation (private task #6); may '
                    'observe or react to Clara\'s response.","activation_sources":{"public_state":false,'
                    '"private_state":true,"public_task":false,"private_task":true,"scene_opportunity":true,'
                    '"user_input":false},"private_motive_used":true}],"wait_for_user":false,"reason_to_wait":null,'
                    '"director_notes":"Clara is the primary responder to Arthur\'s question about Room 7. Eleanor '
                    'observes as secondary actor given her mayoral interest in Arthur\'s purpose. After Clara '
                    'responds, next pass should consider waiting for player follow-up."}'
        ),
        # Memory briefing
        AIMessage(
            content='{"briefings":[{"character_id":1,"character_name":"Eleanor Graves","scene_context":"Iron Stag '
                    'Inn, Blackwater Ridge. Founder\'s Festival evening, 1912. Busy bar environment with locals '
                    'and visitors.","recent_context":"Arthur Moore arrived during the festival. Eleanor greeted '
                    'him earlier, presenting the town as orderly while probing his purpose. He has not yet revealed '
                    'an anonymous letter.","known_relevant_facts":"Director Harlan disappeared three weeks ago '
                    '(Entry 3). Blackwater Ridge is isolated with an Observatory (Entry 1). Founder\'s Festival is '
                    'occurring (Entry 2). Arthur is an outside investigator (State Summary).","immediate_situation":'
                    '"Arthur is currently at the bar asking Clara Whitlock about Room 7 occupancy prior to '
                    'Harlan\'s disappearance. Eleanor is present in the inn but has not yet confronted him directly '
                    'regarding this specific query.","instruction":"Monitor the inquiry between Arthur and Clara '
                    'while maintaining the town\'s public image of orderliness.","available_interactions":["Listen '
                    'to bar conversation","Approach Arthur or Clara","Inspect Notice Board (Entity 6)"],'
                    '"relevant_task_ids":[],"relevant_world_entry_ids":[1,2,3],"constraints":["Location is noisy '
                    'and crowded","Mayor of Blackwater Ridge (Faction 2)","Skilled at omission; avoid direct '
                    'confrontation unless necessary"]},{"character_id":3,"character_name":"Clara Whitlock",'
                    '"scene_context":"Iron Stag Inn Bar, Blackwater Ridge. Founder\'s Festival evening, 1912. '
                    'Warm, noisy, crowded ground-floor bar.","recent_context":"Arthur Moore arrived earlier; '
                    'Clara noticed his controlled manner and suspected he was not merely a curious traveller.",'
                    '"known_relevant_facts":"Director Harlan disappeared three weeks ago (Entry 3). Blackwater '
                    'Ridge is isolated with an Observatory (Entry 1). Founder\'s Festival is occurring (Entry 2). '
                    'Inn acts as informal information hub (Faction 3).","immediate_situation":"Arthur is at the '
                    'bar asking whether Room 7 was occupied before Harlan vanished. Clara is behind the bar '
                    'managing guests while observing him.","instruction":"Respond to Arthur\'s inquiry about Room '
                    '7 occupancy while maintaining innkeeper persona and tracking information value.","'
                    'available_interactions":["Answer Arthur","Consult Visitor\'s Room Ledger (Entity 5)","Inspect '
                    'Notice Board (Entity 6)","Serve other guests"],"relevant_task_ids":[],"relevant_world_entry_ids'
                    '":[1,2,3],"constraints":["Behind the bar","Managing festival guests","Public state is merely '
                    'curious about Arthur\'s arrival"]}],"notes": ""}'
        ),
        # Character actions
        AIMessage(
            content='{"character_id":1,"character_name":"Eleanor Graves","intent":"Close distance to overhear '
                    'Clara\'s response about Room 7 without appearing intrusive.","action_type":"move","method":"'
                    'Moves casually toward the bar counter where Arthur and Clara are standing, maintaining a '
                    'relaxed posture suitable for checking on festival guests.","visible_behavior":"Walks with '
                    'composed confidence through the crowd, glancing briefly at the patrons before focusing '
                    'attention near the innkeeper\'s station.","urgency":75,"persistence":80,"expected_outcome":'
                    '"Eleanor will position herself within earshot of Arthur and Clara to hear the details of Room '
                    '7\'s occupancy history.","fallback_if_blocked":"If the crowd prevents getting close enough, '
                    'she pauses nearby and waits for a lull in conversation before stepping forward with a greeting.'
                    '","uses_private_knowledge":true,"private_reason_for_system":"Task 6 (Assess Arthur\'s threat) '
                    'and Task 7 (Protect land records/Harlan connection) drive her specific interest in this line '
                    'of questioning rather than general observation.","constraints_for_resolver":["The bar is '
                    'noisy; Eleanor needs to be close enough to hear clearly without shouting.","Clara is currently '
                    'engaged with Arthur and may not notice Eleanor immediately."],"notes":"Avoid targeting the '
                    'Ledger (Entity 5) yet; listen to verbal response first to gauge Clara\'s knowledge level '
                    'before deciding whether to check the book herself."}'
        ),
        AIMessage(
            content='{"character_id":3,"character_name":"Clara Whitlock","intent":"Verify Room 7 occupancy details '
                    'using the ledger before confirming to Arthur.","action_type":"manipulate_entity","method":"'
                    'Pauses current service task, offers a polite smile to Arthur, and reaches beneath the bar to '
                    'retrieve and open the Visitor\'s Room Ledger.","visible_behavior":"Clara sets down a tray '
                    'or glass she was holding, turns her attention fully to Arthur with a welcoming expression, '
                    'and slides out the heavy ledger from its shelf behind the counter. She flips through pages '
                    'deliberately while keeping him in view.","urgency":60,"persistence":75,"expected_outcome":"'
                    'Arthur waits for her verification, allowing Clara to control how much information she reveals '
                    'and maintaining her persona of a diligent innkeeper rather than someone who already knows the '
                    'answer.","fallback_if_blocked":"If the ledger is temporarily blocked by other items or guests, '
                    'she answers from memory but notes that it\'s recorded in the book.","uses_private_knowledge":'
                    'true,"private_reason_for_system":"Task 12 indicates Clara already identified the unknown '
                    'visitor for Room 7; consulting the ledger publicly masks her prior knowledge and creates a '
                    'professional pretext for the delay.","constraints_for_resolver":["The Visitor\'s Room Ledger '
                    'is kept behind the bar within Clara\'s reach","Arthur Moore is standing at the bar watching '
                    'her actions","The inn is noisy enough that private whispers are possible but attention is on '
                    'the counter"],"notes":"She will likely find the entry she already knows, but must act as if '
                    'discovering it now."}'
        ),
        # Resolve character actions
        AIMessage(
            content='{"accepted":true,"resolved_actions":[{"actor_id":1,"actor_name":"Eleanor Graves",'
                    '"original_intent":"Close distance to overhear Clara\'s response about Room 7 without appearing '
                    'intrusive.","final_status":"succeeded","visible_result":"Eleanor moves casually through the '
                    'crowd toward the bar counter. She positions herself within earshot of the interaction between '
                    'Arthur and Clara, maintaining a relaxed posture that suggests she is checking on other guests '
                    'rather than eavesdropping.","private_result_for_actor":"Eleanor confirms her position allows '
                    'her to hear clearly despite the background noise. She observes Arthur\'s patience while Clara '
                    'checks the ledger, noting his controlled demeanor does not suggest immediate agitation.",'
                    '"state_change_hints":["Character 1 (Eleanor) position updated: Near Bar Counter"],'
                    '"world_entry_hints":[],"requires_actor_retry":false,"retry_instruction":null},{"actor_id":3'
                    ',"actor_name":"Clara Whitlock","original_intent":"Verify Room 7 occupancy details using the '
                    'ledger before confirming to Arthur.","final_status":"succeeded","visible_result":"Clara sets '
                    'down her current task and retrieves the Visitor\'s Room Ledger from behind the bar. She opens '
                    'the heavy book and flips through pages deliberately while keeping eye contact with Arthur, '
                    'creating a brief pause in the conversation.","private_result_for_actor":"Clara notes that the '
                    'delay appears natural to an outsider. She feels confident maintaining her persona of diligent '
                    'record-keeping despite already knowing the details she intends to share.","state_change_hints"'
                    ':["Entity 5 (Visitor\'s Room Ledger) status changed: Closed -> Open","Entity 5 (Visitor\'s '
                    'Room Ledger) held_by: Character 3"],"world_entry_hints":[],"requires_actor_retry":false,"'
                    'retry_instruction":null}],"scene_result_summary":"Eleanor successfully positions herself to '
                    'monitor the conversation at the bar. Clara retrieves and opens the Visitor\'s Room Ledger, '
                    'initiating a search for Room 7 details in front of Arthur.","next_round_note":"Arthur is now '
                    'waiting for Clara to finish checking the ledger. Eleanor is within earshot."}'
        ),
        # Memory summary
        AIMessage(
            content='{"scene_summary": "At the Iron Stag Inn during the Founder’s Festival, you ask Clara about '
                    'Room 7\'s occupancy prior to Director Harlan’s disappearance. She retrieves the Visitor\'s '
                    'Room Ledger and flips through pages before pausing with the book open, looking at you as '
                    'if waiting for you to see what she found or deciding whether to show it. Eleanor Graves '
                    'moves within earshot of the interaction while you feel the weight of an anonymous letter '
                    'in your pocket.","short_term_memory":"Arthur arrived at the Iron Stag Inn during the '
                    'Founder\'s Festival where Clara noticed his controlled manner and suspected he was not '
                    'merely a curious traveller. Eleanor Graves greeted him, presenting the town as orderly '
                    'while probing his purpose, though Arthur has not yet revealed the anonymous letter. '
                    'Currently, Arthur asks Clara about Room 7’s occupancy before Director Harlan vanished; she '
                    'retrieves the Visitor’s Room Ledger and pauses with it open while Eleanor positions herself '
                    'within earshot.","long_term_memory":"Director Harlan disappeared three weeks ago; '
                    'officially he left without notice, but many residents doubt this. The observatory, the old '
                    'mine, altered property records, the unknown visitor, and Harlan\'s missing notebook remain '
                    'unresolved investigation threads. Arthur is currently investigating at the Iron Stag Inn '
                    'during the Founder’s Festival, carrying an anonymous letter of unknown sender. He has '
                    'requested Clara check the Visitor’s Room Ledger for occupancy records regarding Room 7 prior '
                    'to Harlan’s disappearance.","active_scene":"Iron Stag Inn bar during the Founder\'s Festival'
                    '","open_threads":["What entry does Clara’s ledger show regarding Room 7?","Who sent the '
                    'anonymous letter in Arthur\'s pocket?","Is Eleanor Graves listening for a specific reason '
                    'beyond checking guests?"],"continuity_notes":["Clara has stopped flipping pages and is '
                    'waiting for you to see what she found—or deciding whether to show it.","The anonymous '
                    'letter\'s sender remains unknown to the player.","Eleanor Graves is within earshot but '
                    'posture described as relaxed/checking guests."]}'
        ),
    ]

    committer_model = FakeStructuredListChatModel(
        responses=[
            AIMessage(
                content='{"plan_summary":"Update Visitor\'s Room Ledger entity state (now Open and held by Clara), '
                        'and advance recent_history_summary to reflect Arthur\'s question about Room 7 and current '
                        'positions.","mutations":[{"operation":"update_entity","reason":"Entity status changed '
                        'from Closed to Open, now held by Character 3 per resolver hints","args":{"location_id":3,"'
                        'entity_id":5,"patch":{"status":"Open and held by Clara Whitlock behind the bar"}}},{"'
                        'operation":"update_simulation_state","reason":"Scene progressed: Arthur asked about Room '
                        '7 occupancy, Clara opened ledger to check, Eleanor moved within earshot","args":{"patch":'
                        '{"recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder\'s '
                        'Festival. Clara noticed his controlled manner and suspected he was not merely a curious '
                        'traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive '
                        'while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur '
                        'asked whether Room 7 was occupied before Harlan vanished; Clara opened the Visitor\'s '
                        'Room Ledger to verify details while Eleanor positioned herself within earshot."}}}],'
                        '"no_changes_needed":false}'
            ),
            AIMessage(
                content='{"complete":true,"needs_more_changes":false,"questionable_changes":[],"next_instruction":null}'
            ),
        ]
    )
    narrator_model = FakeStructuredListChatModel(responses=[
        AIMessage(
            content="The Iron Stag Inn hums with the noise of the Founder’s Festival, warm air thick with the smell "
                    "of ale and woodsmoke. You ask Clara whether Room 7 was occupied before Director Harlan "
                    "vanished.\n\nShe sets down her current task and reaches beneath the counter, retrieving a "
                    "heavy Visitor’s Room Ledger. The leather cover is worn smooth. Clara opens the book and flips "
                    "through pages deliberately, the sound of turning paper cutting briefly against the bar's din. "
                    "Her eyes remain fixed on you during the search, creating a pause in the conversation that "
                    "feels heavier than the moment requires.\n\nFrom the corner of your eye, Eleanor Graves moves "
                    "casually through the crowd toward the bar counter. She positions herself within earshot of "
                    "your interaction, her posture relaxed as if checking on other guests rather than listening "
                    "to your specific inquiry. You feel the weight of the anonymous letter in your pocket; you "
                    "still do not know who sent it, only that finding evidence is what will bring payment home.\n\n"
                    "Clara stops flipping pages and looks up from the ledger, waiting for you to see what she has "
                    "found—or perhaps deciding whether to show it."
        )
    ])

    with patch.object(CommitterAgent, "model", new_callable=PropertyMock) as mock_committer_model:
        with patch.object(NarratorAgent, "model", new_callable=PropertyMock) as mock_narrator_model:
            mock_committer_model.return_value = committer_model
            mock_narrator_model.return_value = narrator_model

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

                for line in lines:
                    if line.startswith("event: "):
                        event_type = line[len("event: "):]
                        assert event_type != "error", lines[-1]
