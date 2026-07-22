from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import AsyncGraphDatabase

from world_simulation_engine.misc.enums import ContainerState, EventInvolvement, IntentHorizon, IntentStatus, \
    IntentType, SimulationGenerationRequestType, SupportedLanguage, TurnType
from world_simulation_engine.model import Author, BackgroundCharacter, Character, Container, CurrentActivity, \
    Equipment, Event, GenerationJob, Intent, Item, ItemStack, Landmark, Location, Turn, World
from world_simulation_engine.router import background_character_router, character_router, container_router, \
    equipment_router, event_router, intent_router, item_router, location_router, simulation_router
from world_simulation_engine.service import DatabaseService


class FakeWorldSimulator:
    def __init__(self, database):
        self.database = database
        self.started_states = []
        self.running_threads = set()
        self.streams = {}
        self.error_threads = set()

    async def start_generation(
            self,
            state,
            request_type=None,
            regenerate_turn_sequence=None,
            client_request_id=None,
    ):
        thread_id = f"thread_{len(self.started_states) + 1}"
        self.started_states.append(state)
        self.streams[thread_id] = [
            {
                "narration": {
                    "blocks": [
                        {
                            "type": "narration",
                            "text": "The room settles.",
                        }
                    ]
                }
            },
            {"committed_turn": {"id": "turn_1"}},
        ]
        await self.database.generation_job.create_job(
            GenerationJob(
                id=thread_id,
                simulation_id=state.simulation.id,
                client_request_id=client_request_id,
                request_type=request_type or SimulationGenerationRequestType.USER_INPUT_GENERATION,
                regenerate_turn_sequence=regenerate_turn_sequence,
            )
        )
        return thread_id

    def is_generation_running(self, thread_id: str) -> bool:
        return thread_id in self.running_threads

    async def stream_generation(self, thread_id: str):
        if thread_id in self.error_threads:
            raise RuntimeError("Generation failed")
        if thread_id not in self.streams:
            raise KeyError(thread_id)

        for chunk in self.streams[thread_id]:
            yield chunk


@dataclass(frozen=True)
class SimulationRouterTestClient:
    client: TestClient
    author: Author
    other_author: Author
    world: World
    other_world: World
    world_character: Character
    background_character: BackgroundCharacter
    item: Item
    stack: ItemStack
    contained_stack: ItemStack
    equipment: Equipment
    container: Container
    event: Event
    intent: Intent
    city: Location
    market: Location
    landmark: Landmark
    simulator: FakeWorldSimulator


@pytest.fixture
def simulation_api(neo4j_container):
    author = Author(
        id=str(uuid4()),
        name="Simulation API Author",
        url="https://example.com/authors/simulation-api",
    )
    other_author = Author(
        id=str(uuid4()),
        name="Other Simulation API Author",
        url="https://example.com/authors/other-simulation-api",
    )
    world = World(
        id=str(uuid4()),
        name="Simulation World",
        description="A world used to create simulations",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/simulation",
        language=SupportedLanguage.ENGLISH,
    )
    other_world = World(
        id=str(uuid4()),
        name="Other Simulation World",
        description="Another world used to create simulations",
        starting_time=datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
        version=1,
        url="https://example.com/worlds/other-simulation",
        language=SupportedLanguage.CHINESE,
    )
    world_character = Character(
        id=str(uuid4()),
        user_controlled=True,
        name="Alex",
        age=30,
        gender="non-binary",
        appearance="Short hair and a practical coat",
        description="A test character",
        public_state="Waiting",
        private_state="Planning",
        current_activity=CurrentActivity(name="observing"),
    )
    background_character = BackgroundCharacter(
        id=str(uuid4()),
        name="Shopkeeper",
        description="A busy shopkeeper",
    )
    item = Item(
        id=str(uuid4()),
        name="Market apple",
        description="A crisp apple",
        unique=False,
    )
    stack = ItemStack(
        id=str(uuid4()),
        quantity=3,
        quality="fresh",
    )
    contained_stack = ItemStack(
        id=str(uuid4()),
        quantity=1,
        quality="boxed",
    )
    equipment = Equipment(
        id=str(uuid4()),
        name="Lantern",
        description="A brass lantern",
        quality="worn",
    )
    container = Container(
        id=str(uuid4()),
        name="Supply crate",
        description="A crate for market supplies",
        state=ContainerState.UNLOCKED,
    )
    turn = Turn(
        id=str(uuid4()),
        sequence=0,
        type=TurnType.USER_INPUT,
        content="Alex greets the shopkeeper",
        start_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    event = Event(
        id=str(uuid4()),
        name="Greeting",
        summary="Alex greets the shopkeeper.",
    )
    intent = Intent(
        id=str(uuid4()),
        type=IntentType.QUEST,
        name="Buy supplies",
        description="Alex wants to buy supplies.",
        keywords=["buy", "supplies"],
        embedding=[0.1, 0.2],
        priority=0.8,
        urgency=0.7,
        status=IntentStatus.ACTIVE,
        desired_state="Supplies purchased",
        success_conditions=["Alex has supplies"],
        failure_conditions=["Shop closes"],
        maintenance_conditions=[],
        deadline=datetime(2026, 1, 1, 18, 0, tzinfo=UTC),
        horizon=IntentHorizon.SHORT,
        constraints=["Stay polite"],
        current_plan=["Ask the shopkeeper"],
        next_action_biases=["Inspect shelves"],
        blockers=[],
        open_threads=["What is available"],
    )
    city = Location(
        id=str(uuid4()),
        name="City",
        description="A city",
    )
    market = Location(
        id=str(uuid4()),
        name="Market",
        description="A market",
    )
    landmark = Landmark(
        id=str(uuid4()),
        name="Fountain",
        description="A fountain",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        driver = AsyncGraphDatabase.driver(
            neo4j_container.get_connection_url(),
            auth=("neo4j", "testpassword"),
        )
        await driver.verify_connectivity()
        await driver.execute_query("MATCH (n) DETACH DELETE n")

        database = DatabaseService(driver)
        await database.world.create_author(author)
        await database.world.create_author(other_author)
        await database.world.create_world(world, author.id)
        await database.world.create_world(other_world, other_author.id)
        await database.location.create_location(city, source_id=world.id)
        await database.location.create_location(market, source_id=world.id, contained_in=city.id)
        await database.location.create_landmark(landmark, market.id)
        await database.character.create_character(world_character, world.id)
        await database.character.move_to_location(world_character.id, market.id, position="near the stalls")
        await database.character.anchor_to_landmark(world_character.id, landmark.id)
        await database.character.create_background_character(
            background_character,
            world.id,
            location_id=market.id,
            position="behind the counter",
            landmark_id=landmark.id,
        )
        await database.item.create_item(item, world.id)
        await database.item.create_stack(
            item.id,
            stack,
            source_id=world.id,
            holder_id=world_character.id,
            owner_id=world_character.id,
        )
        await database.item.create_stack(
            item.id,
            contained_stack,
            source_id=world.id,
            location_id=market.id,
            position="inside the crate",
        )
        await database.equipment.create_equipment(equipment, world.id)
        await database.equipment.change_owner(equipment.id, world_character.id)
        await database.equipment.change_hold_state(
            equipment.id,
            world_character.id,
            equipped=True,
            equipped_position="left hand",
        )
        await database.container.create_container(
            container,
            world.id,
            location_id=market.id,
            position="beside the stall",
        )
        await database.container.put_stack_in_container(contained_stack.id, container.id)
        await database.container.put_equipment_in_container(equipment.id, container.id)
        await database.container.add_unlocking_item(item.id, container.id)
        await database.turn.create_turn(turn, world.id)
        await database.event.create_event(event, [turn.id])
        await database.event.add_character_involvement(
            event.id,
            world_character.id,
            EventInvolvement.PARTICIPATE,
        )
        await database.intent.create_intent(intent, world_character.id)
        await database.intent.add_event_creation(event.id, intent.id)
        await database.intent.add_event_contribution(event.id, intent.id)
        app.state.database = database
        app.state.world_simulator = FakeWorldSimulator(database)

        try:
            yield
        finally:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
            await driver.close()

    app = FastAPI(lifespan=lifespan)
    app.include_router(background_character_router)
    app.include_router(simulation_router)
    app.include_router(character_router)
    app.include_router(container_router)
    app.include_router(equipment_router)
    app.include_router(event_router)
    app.include_router(intent_router)
    app.include_router(item_router)
    app.include_router(location_router)

    with TestClient(app) as client:
        yield SimulationRouterTestClient(
            client=client,
            author=author,
            other_author=other_author,
            world=world,
            other_world=other_world,
            world_character=world_character,
            background_character=background_character,
            item=item,
            stack=stack,
            contained_stack=contained_stack,
            equipment=equipment,
            container=container,
            event=event,
            intent=intent,
            city=city,
            market=market,
            landmark=landmark,
            simulator=app.state.world_simulator,
        )


def test_create_list_get_update_and_delete_simulation(simulation_api):
    client = simulation_api.client

    create_response = client.post(f"/worlds/{simulation_api.world.id}/simulations")

    assert create_response.status_code == 200
    created_simulation = create_response.json()
    assert created_simulation["id"]
    assert created_simulation["name"] == simulation_api.world.name
    assert created_simulation["description"] == simulation_api.world.description
    assert created_simulation["current_time"] == "2026-01-01T12:00:00Z"

    copied_characters_response = client.get(
        "/characters",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_locations_response = client.get(
        "/locations",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_background_characters_response = client.get(
        "/background-characters",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_equipment_response = client.get(
        "/equipment",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_stacks_response = client.get(
        "/stacks",
        params={"simulation_id": created_simulation["id"]},
    )
    copied_containers_response = client.get(
        "/containers",
        params={"simulation_id": created_simulation["id"]},
    )
    assert copied_characters_response.status_code == 200
    assert len(copied_characters_response.json()) == 1
    copied_character = copied_characters_response.json()[0]
    assert copied_character["id"] != simulation_api.world_character.id
    assert copied_character == {
        **simulation_api.world_character.model_dump(mode="json"),
        "id": copied_character["id"],
    }
    assert copied_locations_response.status_code == 200
    assert {
        location["name"]
        for location in copied_locations_response.json()
    } == {
        simulation_api.city.name,
        simulation_api.market.name,
    }
    assert all(
        location["id"] not in {simulation_api.city.id, simulation_api.market.id}
        for location in copied_locations_response.json()
    )
    copied_market = next(
        location
        for location in copied_locations_response.json()
        if location["name"] == simulation_api.market.name
    )
    assert client.get(
        "/characters",
        params={"location_id": copied_market["id"]},
    ).json() == [copied_character]
    assert copied_background_characters_response.status_code == 200
    assert len(copied_background_characters_response.json()) == 1
    copied_background_character = copied_background_characters_response.json()[0]
    assert copied_background_character["id"] != simulation_api.background_character.id
    assert copied_background_character == {
        **simulation_api.background_character.model_dump(mode="json"),
        "id": copied_background_character["id"],
    }
    assert client.get(
        "/background-characters",
        params={"location_id": copied_market["id"]},
    ).json() == [copied_background_character]
    assert copied_equipment_response.status_code == 200
    assert len(copied_equipment_response.json()) == 1
    copied_equipment = copied_equipment_response.json()[0]
    assert copied_equipment["id"] != simulation_api.equipment.id
    assert copied_equipment == {
        **simulation_api.equipment.model_dump(mode="json"),
        "id": copied_equipment["id"],
    }
    assert client.get(
        "/equipment",
        params={"holder_id": copied_character["id"]},
    ).json() == []
    assert copied_stacks_response.status_code == 200
    assert len(copied_stacks_response.json()) == 2
    copied_held_stacks = client.get(
        "/stacks",
        params={"holder_id": copied_character["id"]},
    ).json()
    assert len(copied_held_stacks) == 1
    copied_held_stack = copied_held_stacks[0]
    assert copied_held_stack["id"] != simulation_api.stack.id
    assert copied_held_stack == {
        **simulation_api.stack.model_dump(mode="json"),
        "id": copied_held_stack["id"],
    }
    assert client.get(
        "/stacks",
        params={"owner_id": copied_character["id"]},
    ).json() == [copied_held_stack]
    assert copied_containers_response.status_code == 200
    assert len(copied_containers_response.json()) == 1
    copied_container = copied_containers_response.json()[0]
    assert copied_container["id"] != simulation_api.container.id
    assert copied_container == {
        **simulation_api.container.model_dump(mode="json"),
        "id": copied_container["id"],
    }
    held_stack_entries = client.get(f"/containers/{copied_container['id']}/stacks").json()
    assert len(held_stack_entries) == 1
    held_item, copied_contained_stack = held_stack_entries[0]
    assert held_item == simulation_api.item.model_dump(mode="json")
    assert copied_contained_stack["id"] != simulation_api.contained_stack.id
    assert copied_contained_stack == {
        **simulation_api.contained_stack.model_dump(mode="json"),
        "id": copied_contained_stack["id"],
    }
    assert client.get(f"/containers/{copied_container['id']}/equipment").json() == [copied_equipment]
    assert client.get(f"/containers/{copied_container['id']}/unlocking-items").json() == [
        simulation_api.item.model_dump(mode="json")
    ]
    copied_events_response = client.get(
        "/events",
        params={"character_id": copied_character["id"]},
    )
    copied_intents_response = client.get(
        "/intents",
        params={"character_id": copied_character["id"]},
    )
    assert copied_events_response.status_code == 200
    assert len(copied_events_response.json()) == 1
    copied_event = copied_events_response.json()[0]
    assert copied_event["id"] != simulation_api.event.id
    assert copied_event == {
        **simulation_api.event.model_dump(mode="json"),
        "id": copied_event["id"],
    }
    assert copied_intents_response.status_code == 200
    assert len(copied_intents_response.json()) == 1
    copied_intent = copied_intents_response.json()[0]
    assert copied_intent["id"] != simulation_api.intent.id
    assert copied_intent == {
        **simulation_api.intent.model_dump(mode="json"),
        "id": copied_intent["id"],
    }
    assert client.get(
        "/intents",
        params={"event_id": copied_event["id"]},
    ).json() == [copied_intent]

    other_create_response = client.post(f"/worlds/{simulation_api.other_world.id}/simulations")
    other_simulation = other_create_response.json()

    assert other_create_response.status_code == 200

    list_response = client.get("/simulations")

    assert list_response.status_code == 200
    assert {
        simulation["id"]
        for simulation in list_response.json()
    } == {
        created_simulation["id"],
        other_simulation["id"],
    }
    paginated_response = client.get("/simulations", params={"limit": 1, "skip": 1})
    assert paginated_response.status_code == 200
    assert [
        simulation["id"]
        for simulation in paginated_response.json()
    ] == [created_simulation["id"]]

    author_filter_response = client.get("/simulations", params={"author_id": simulation_api.author.id})
    world_filter_response = client.get("/simulations", params={"world_id": simulation_api.world.id})
    world_paginated_response = client.get(
        "/simulations",
        params={
            "world_id": simulation_api.world.id,
            "limit": 1,
            "skip": 0,
        },
    )
    combined_filter_response = client.get(
        "/simulations",
        params={
            "author_id": simulation_api.author.id,
            "world_id": simulation_api.other_world.id,
        },
    )

    assert author_filter_response.status_code == 200
    assert author_filter_response.json() == [created_simulation]
    assert world_filter_response.status_code == 200
    assert world_filter_response.json() == [created_simulation]
    assert world_paginated_response.status_code == 200
    assert world_paginated_response.json() == [created_simulation]
    assert combined_filter_response.status_code == 200
    assert combined_filter_response.json() == []

    get_response = client.get(f"/simulations/{created_simulation['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_simulation

    update_response = client.patch(
        f"/simulations/{created_simulation['id']}",
        json={
            "name": "Updated Simulation",
                "description": "Updated through the simulation API",
                "current_time": "2026-03-01T12:00:00Z",
                "emotion_enabled": False,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": created_simulation["id"],
        "name": "Updated Simulation",
        "description": "Updated through the simulation API",
        "current_time": "2026-03-01T12:00:00Z",
        "emotion_enabled": False,
    }

    delete_response = client.delete(f"/simulations/{created_simulation['id']}")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert client.get(f"/simulations/{created_simulation['id']}").status_code == 404


def test_simulation_endpoints_return_404_for_missing_resources(simulation_api):
    client = simulation_api.client
    missing_world_id = str(uuid4())
    missing_simulation_id = str(uuid4())

    create_response = client.post(f"/worlds/{missing_world_id}/simulations")
    get_response = client.get(f"/simulations/{missing_simulation_id}")
    update_response = client.patch(
        f"/simulations/{missing_simulation_id}",
        json={"name": "Missing Simulation"},
    )
    delete_response = client.delete(f"/simulations/{missing_simulation_id}")

    assert create_response.status_code == 404
    assert create_response.json()["detail"] == f"World {missing_world_id} not found"
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == f"Simulation {missing_simulation_id} not found"


def test_start_simulation_input_schedules_generation(simulation_api):
    missing_response = simulation_api.client.post(
        f"/simulations/{str(uuid4())}/input",
        json={"user_input": "I look around."},
    )

    assert missing_response.status_code == 404

    create_response = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations")
    simulation = create_response.json()
    response = simulation_api.client.post(
        f"/simulations/{simulation['id']}/input",
        json={"user_input": "I look around."},
    )

    assert response.status_code == 200
    assert response.json() == {"thread_id": "thread_1"}
    started_state = simulation_api.simulator.started_states[0]
    assert started_state.world.id == simulation_api.world.id
    assert started_state.simulation.id == simulation["id"]
    assert started_state.user_input == "I look around."


def test_generation_run_status_is_persisted_and_scoped_to_simulation(simulation_api):
    first = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations").json()
    second = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations").json()
    thread_id = simulation_api.client.post(
        f"/simulations/{first['id']}/input",
        json={
            "user_input": "I look around.",
            "client_request_id": "client-request-1",
        },
    ).json()["thread_id"]

    response = simulation_api.client.get(
        f"/simulations/{first['id']}/runs/{thread_id}/status",
    )
    wrong_simulation_response = simulation_api.client.get(
        f"/simulations/{second['id']}/runs/{thread_id}/status",
    )

    assert response.status_code == 200
    assert response.json()["id"] == thread_id
    assert response.json()["client_request_id"] == "client-request-1"
    assert response.json()["status"] == "queued"
    assert wrong_simulation_response.status_code == 404


def test_start_simulation_input_accepts_null_user_input(simulation_api):
    create_response = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations")
    simulation = create_response.json()

    response = simulation_api.client.post(
        f"/simulations/{simulation['id']}/input",
        json={"user_input": None},
    )

    assert response.status_code == 200
    assert simulation_api.simulator.started_states[0].user_input is None


def test_start_simulation_input_rejects_malformed_user_markup(simulation_api):
    create_response = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations")
    simulation = create_response.json()

    response = simulation_api.client.post(
        f"/simulations/{simulation['id']}/input",
        json={"user_input": 'I ask "Room 7?'},
    )

    assert response.status_code == 400
    assert simulation_api.simulator.started_states == []


def test_stream_simulation_run_streams_sse_chunks(simulation_api):
    create_response = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations")
    simulation = create_response.json()
    thread_id = simulation_api.client.post(
        f"/simulations/{simulation['id']}/input",
        json={"user_input": "I look around."},
    ).json()["thread_id"]

    with simulation_api.client.stream("GET", f"/simulations/{simulation['id']}/runs/{thread_id}") as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: chunk" in body
    assert '"narration": {"blocks": [{"type": "narration", "text": "The room settles."}]}' in body
    assert 'data: {"committed_turn": {"id": "turn_1"}}' in body
    assert "event: done" in body
    assert '"code": "done"' in body


def test_stream_simulation_run_tells_reconnecting_client_to_wait(simulation_api):
    create_response = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations")
    simulation = create_response.json()
    thread_id = simulation_api.client.post(
        f"/simulations/{simulation['id']}/input",
        json={"user_input": "I look around."},
    ).json()["thread_id"]
    simulation_api.simulator.running_threads.add(thread_id)

    response = simulation_api.client.get(
        f"/simulations/{simulation['id']}/runs/{thread_id}",
        headers={"Last-Event-ID": "0"},
    )

    assert response.status_code == 200
    assert "event: status" in response.text
    assert '"code": "still_generating"' in response.text


def test_stream_simulation_run_reports_missing_or_failed_thread(simulation_api):
    create_response = simulation_api.client.post(f"/worlds/{simulation_api.world.id}/simulations")
    simulation = create_response.json()
    missing_response = simulation_api.client.get(f"/simulations/{simulation['id']}/runs/missing")

    thread_id = simulation_api.client.post(
        f"/simulations/{simulation['id']}/input",
        json={"user_input": "I look around."},
    ).json()["thread_id"]
    simulation_api.simulator.error_threads.add(thread_id)
    failed_response = simulation_api.client.get(f"/simulations/{simulation['id']}/runs/{thread_id}")

    assert missing_response.status_code == 200
    assert '"code": "not_found"' in missing_response.text
    assert failed_response.status_code == 200
    assert "event: error" in failed_response.text
    assert '"code": "generation_failed"' in failed_response.text


def test_simulation_list_rejects_invalid_pagination(simulation_api):
    client = simulation_api.client

    zero_limit_response = client.get("/simulations", params={"limit": 0})
    negative_skip_response = client.get("/simulations", params={"skip": -1})

    assert zero_limit_response.status_code == 422
    assert negative_skip_response.status_code == 422
