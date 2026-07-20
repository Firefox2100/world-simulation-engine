"""
Insert the evaluation sample world through the backend HTTP API.

Environment variables:
    WSE_API_BASE_URL, WORLD_SIMULATION_ENGINE_API_URL, or API_BASE_URL
        Base URL for the running backend. Defaults to http://localhost:8000.

Example:
    WSE_API_BASE_URL=http://localhost:8000 python scripts/insert_sample_world.py --replace
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.evaluation_test import conftest as evaluation_fixtures  # noqa: E402


def _fixture(name: str, *args):
    fixture = getattr(evaluation_fixtures, name)
    return fixture.__wrapped__(*args)


def build_sample_setup():
    author = _fixture("mock_author")
    world = _fixture("mock_world")
    simulation = _fixture("mock_simulation", world)
    initial_turn = _fixture("mock_initial_turn")
    locations = _fixture("mock_locations")
    location_parents = _fixture("mock_location_parents")
    landmarks_by_location = _fixture("mock_landmarks_by_location")
    containers = _fixture("mock_containers")
    container_placements = _fixture("mock_container_placements")
    characters = _fixture("mock_characters")
    background_characters = _fixture("mock_background_characters")
    character_placements = _fixture("mock_character_placements")
    background_character_placements = _fixture("mock_background_character_placements")
    items = _fixture("mock_items")
    item_stack_placements = _fixture("mock_item_stack_placements")
    equipment = _fixture("mock_equipment")
    equipment_placements = _fixture("mock_equipment_placements")
    events = _fixture("mock_events")
    event_involvements = _fixture("mock_event_involvements")
    memories = _fixture("mock_memories")
    intents = _fixture("mock_intents")
    intent_character_ids = _fixture("mock_intent_character_ids")
    return _fixture(
        "mock_graph_world_setup",
        author,
        world,
        simulation,
        initial_turn,
        locations,
        location_parents,
        landmarks_by_location,
        containers,
        container_placements,
        characters,
        background_characters,
        character_placements,
        background_character_placements,
        items,
        item_stack_placements,
        equipment,
        equipment_placements,
        events,
        event_involvements,
        memories,
        intents,
        intent_character_ids,
    )


class Api:
    def __init__(self, base_url: str):
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)

    def close(self):
        self._client.close()

    def get(self, path: str, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs):
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._request("DELETE", path, **kwargs)

    def _request(self, method: str, path: str, **kwargs):
        response = self._client.request(method, path, **kwargs)
        if response.is_error:
            raise RuntimeError(
                f"{method} {path} failed with {response.status_code}: {response.text}"
            )
        if response.status_code == 204:
            return None
        return response.json()


def model_payload(model, *, exclude_id: bool = True) -> dict[str, Any]:
    exclude = {"id"} if exclude_id else set()
    return model.model_dump(mode="json", exclude=exclude)


def create_author(api: Api, setup) -> dict[str, Any]:
    for author in api.get("/authors"):
        if author["name"] == setup.author.name and author.get("url") == setup.author.url:
            return author
    return api.post("/authors", json=model_payload(setup.author))


def delete_existing_worlds(api: Api, setup):
    for world in api.get("/worlds"):
        if world["name"] == setup.world.name:
            api.delete(f"/worlds/{world['id']}")


def create_locations(api: Api, setup, world_id: str) -> dict[str, str]:
    location_ids: dict[str, str] = {}
    pending = {location.id: location for location in setup.locations}

    while pending:
        progressed = False
        for old_id, location in list(pending.items()):
            old_parent_id = setup.location_parents.get(old_id)
            if old_parent_id is not None and old_parent_id not in location_ids:
                continue

            if old_parent_id is None:
                created = api.post(
                    f"/worlds/{world_id}/locations",
                    json=model_payload(location),
                )
            else:
                created = api.post(
                    f"/locations/{location_ids[old_parent_id]}/locations",
                    json=model_payload(location),
                )
            location_ids[old_id] = created["id"]
            del pending[old_id]
            progressed = True

        if not progressed:
            unresolved = ", ".join(sorted(pending))
            raise RuntimeError(f"Unable to resolve location parent order for: {unresolved}")

    return location_ids


def create_landmarks(api: Api, setup, location_ids: dict[str, str]) -> dict[str, str]:
    landmark_ids = {}
    for old_location_id, landmarks in setup.landmarks_by_location.items():
        for landmark in landmarks:
            created = api.post(
                f"/locations/{location_ids[old_location_id]}/landmarks",
                json=model_payload(landmark),
            )
            landmark_ids[landmark.id] = created["id"]
    return landmark_ids


def create_characters(
    api: Api,
    setup,
    world_id: str,
    location_ids: dict[str, str],
    landmark_ids: dict[str, str],
) -> dict[str, str]:
    placement_by_character_id = {
        placement.character_id: placement
        for placement in setup.character_placements
    }
    character_ids = {}
    for character in setup.characters:
        placement = placement_by_character_id.get(character.id)
        payload = model_payload(character)
        if placement:
            payload["location_id"] = location_ids[placement.location_id]
            payload["position"] = placement.position
            if placement.landmark_id:
                payload["landmark_id"] = landmark_ids[placement.landmark_id]
        created = api.post(f"/worlds/{world_id}/characters", json=payload)
        if placement:
            api.put(
                f"/characters/{created['id']}/location",
                json={
                    "location_id": location_ids[placement.location_id],
                    "position": placement.position,
                },
            )
            if placement.landmark_id:
                api.put(
                    f"/characters/{created['id']}/landmark",
                    json={"landmark_id": landmark_ids[placement.landmark_id]},
                )
        character_ids[character.id] = created["id"]
    return character_ids


def create_background_characters(
    api: Api,
    setup,
    world_id: str,
    location_ids: dict[str, str],
    landmark_ids: dict[str, str],
) -> dict[str, str]:
    placement_by_character_id = {
        placement.character_id: placement
        for placement in setup.background_character_placements
    }
    character_ids = {}
    for character in setup.background_characters:
        placement = placement_by_character_id.get(character.id)
        payload = model_payload(character)
        if placement:
            payload["location_id"] = location_ids[placement.location_id]
            payload["position"] = placement.position
            if placement.landmark_id:
                payload["landmark_id"] = landmark_ids[placement.landmark_id]
        created = api.post(f"/worlds/{world_id}/background-characters", json=payload)
        if placement:
            api.put(
                f"/background-characters/{created['id']}/location",
                json={
                    "location_id": location_ids[placement.location_id],
                    "position": placement.position,
                },
            )
            if placement.landmark_id:
                api.put(
                    f"/background-characters/{created['id']}/landmark",
                    json={"landmark_id": landmark_ids[placement.landmark_id]},
                )
        character_ids[character.id] = created["id"]
    return character_ids


def map_simulation_entities_by_name(
    api: Api,
    path: str,
    simulation_id: str,
    source_entities,
) -> dict[str, str]:
    copied_entities = api.get(path, params={"simulation_id": simulation_id})
    copied_ids_by_identity = {
        (entity["name"], entity["description"]): entity["id"]
        for entity in copied_entities
    }
    return {
        entity.id: copied_ids_by_identity[(entity.name, entity.description)]
        for entity in source_entities
    }


def map_simulation_turns_by_sequence(api: Api, simulation_id: str, source_turns) -> dict[str, str]:
    copied_turns = api.get(
        "/turns",
        params={
            "simulation_id": simulation_id,
            "limit": max(len(source_turns), 1),
        },
    )
    copied_ids_by_sequence = {
        turn["sequence"]: turn["id"]
        for turn in copied_turns
    }
    return {
        turn.id: copied_ids_by_sequence[turn.sequence if turn.sequence >= 1 else index + 1]
        for index, turn in enumerate(source_turns)
    }


def assert_characters_are_located(
    api: Api,
    source_name: str,
    character_ids: dict[str, str],
    location_ids: dict[str, str],
):
    located_character_ids = set()
    for location_id in location_ids.values():
        for character in api.get("/characters", params={"location_id": location_id}):
            located_character_ids.add(character["id"])

    missing = {
        fixture_id: character_id
        for fixture_id, character_id in character_ids.items()
        if character_id not in located_character_ids
    }
    if missing:
        raise RuntimeError(
            f"{source_name} characters missing location relationships: {missing}"
        )


def create_items_and_stacks(
    api: Api,
    setup,
    source_path: str,
    source_id: str,
    location_ids: dict[str, str],
    entity_ids: dict[str, str],
    existing_item_ids: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    item_ids = existing_item_ids or {}
    if not existing_item_ids:
        for item in setup.items:
            created = api.post(f"{source_path}/{source_id}/items", json=model_payload(item))
            item_ids[item.id] = created["id"]

    stack_ids = {}
    for placement in setup.item_stack_placements:
        payload = model_payload(placement.stack)
        payload["quantity"] = placement.stack.quantity
        payload["quality"] = placement.stack.quality
        if placement.location_id:
            payload["location_id"] = location_ids[placement.location_id]
            payload["position"] = placement.position
        if placement.holder_id:
            payload["holder_id"] = entity_ids[placement.holder_id]
        if placement.owner_id:
            payload["owner_id"] = entity_ids[placement.owner_id]
        created = api.post(
            f"{source_path}/{source_id}/items/{item_ids[placement.item_id]}/stacks",
            json=payload,
        )
        stack_ids[placement.stack.id] = created["id"]

    return item_ids, stack_ids


def create_equipment(
    api: Api,
    setup,
    source_path: str,
    source_id: str,
    location_ids: dict[str, str],
    entity_ids: dict[str, str],
) -> dict[str, str]:
    placement_by_equipment_id = {
        placement.equipment_id: placement
        for placement in setup.equipment_placements
    }
    equipment_ids = {}
    for equipment in setup.equipment:
        placement = placement_by_equipment_id[equipment.id]
        payload = model_payload(equipment)
        if placement.location_id:
            payload["location_id"] = location_ids[placement.location_id]
            payload["position"] = placement.position
        if placement.owner_id:
            payload["owner_id"] = entity_ids[placement.owner_id]
        if placement.holder_id:
            payload["holder_id"] = entity_ids[placement.holder_id]
            payload["equipped"] = placement.equipped
            payload["equipped_position"] = placement.equipped_position
        created = api.post(f"{source_path}/{source_id}/equipment", json=payload)
        equipment_ids[equipment.id] = created["id"]
    return equipment_ids


def create_containers(
    api: Api,
    setup,
    source_path: str,
    source_id: str,
    location_ids: dict[str, str],
    item_ids: dict[str, str],
) -> dict[str, str]:
    placement_by_container_id = {
        placement.container_id: placement
        for placement in setup.container_placements
    }
    container_ids = {}
    for container in setup.containers:
        placement = placement_by_container_id[container.id]
        payload = model_payload(container)
        payload["location_id"] = location_ids[placement.location_id]
        payload["position"] = placement.position
        created = api.post(f"{source_path}/{source_id}/containers", json=payload)
        container_ids[container.id] = created["id"]

    for placement in setup.container_placements:
        if placement.unlocking_item_ids:
            api.put(
                f"/containers/{container_ids[placement.container_id]}/unlocking-items",
                json={
                    "item_ids": [
                        item_ids[item_id]
                        for item_id in placement.unlocking_item_ids
                    ]
                },
            )
    return container_ids


def create_intents(api: Api, setup, character_ids: dict[str, str]) -> dict[str, str]:
    intent_ids = {}
    for intent in setup.intents:
        character_id = character_ids[setup.intent_character_ids[intent.id]]
        created = api.post(
            f"/characters/{character_id}/intents",
            json=model_payload(intent),
        )
        intent_ids[intent.id] = created["id"]
    return intent_ids


def create_turns(api: Api, setup, world_id: str) -> dict[str, str]:
    turn = setup.initial_turn
    payload = model_payload(turn)
    payload["sequence"] = 1
    created = api.post(f"/worlds/{world_id}/turns", json=payload)
    return {turn.id: created["id"]}


def create_events(
    api: Api,
    setup,
    turn_ids: dict[str, str],
    character_ids: dict[str, str],
) -> dict[str, str]:
    involvements_by_event_id = {}
    for involvement in setup.event_involvements:
        involvements_by_event_id.setdefault(involvement.event_id, []).append(involvement)

    event_ids = {}
    for event in setup.events:
        created = api.post(
            "/events",
            json={
                **model_payload(event),
                "turn_ids": [turn_ids[setup.initial_turn.id]],
                "involved_characters": [
                    {
                        "character_id": character_ids[involvement.character_id],
                        "involvement": involvement.involvement,
                    }
                    for involvement in involvements_by_event_id.get(event.id, [])
                ],
            },
        )
        event_ids[event.id] = created["id"]
    return event_ids


def create_memories(
    api: Api,
    setup,
    event_ids: dict[str, str],
    character_ids: dict[str, str],
) -> dict[str, str]:
    memory_ids = {}
    for memory_seed in setup.memories:
        created = api.post(
            "/memories",
            json={
                **model_payload(memory_seed.memory),
                "event_id": event_ids[memory_seed.event_id],
                "support_type": memory_seed.support_type,
                "character_links": [
                    {
                        **character_link.model_dump(mode="json"),
                        "character_id": character_ids[character_link.character_id],
                    }
                    for character_link in memory_seed.character_links
                ],
            },
        )
        memory_ids[memory_seed.memory.id] = created["id"]
    return memory_ids


def insert_sample_world(base_url: str, replace: bool) -> dict[str, Any]:
    setup = build_sample_setup()
    api = Api(base_url)
    skipped = {
        "turn_sequence": "The evaluation fixture starts at sequence 0; the API sample insert remaps it to sequence 1.",
    }

    try:
        if replace:
            delete_existing_worlds(api, setup)

        author = create_author(api, setup)
        world_payload = model_payload(setup.world)
        world_payload["author_id"] = author["id"]
        world = api.post("/worlds", json=world_payload)

        location_ids = create_locations(api, setup, world["id"])
        landmark_ids = create_landmarks(api, setup, location_ids)
        turn_ids = create_turns(api, setup, world["id"])
        world_character_ids = create_characters(api, setup, world["id"], location_ids, landmark_ids)
        world_background_character_ids = create_background_characters(
            api,
            setup,
            world["id"],
            location_ids,
            landmark_ids,
        )
        assert_characters_are_located(
            api,
            "World",
            world_character_ids,
            location_ids,
        )
        item_ids = {}
        for item in setup.items:
            created = api.post(f"/worlds/{world['id']}/items", json=model_payload(item))
            item_ids[item.id] = created["id"]
        _, stack_ids = create_items_and_stacks(
            api,
            setup,
            "/worlds",
            world["id"],
            location_ids,
            {**world_character_ids, **world_background_character_ids},
            existing_item_ids=item_ids,
        )
        equipment_ids = create_equipment(
            api,
            setup,
            "/worlds",
            world["id"],
            location_ids,
            {**world_character_ids, **world_background_character_ids},
        )
        container_ids = create_containers(
            api,
            setup,
            "/worlds",
            world["id"],
            location_ids,
            item_ids,
        )

        simulation = api.post(f"/worlds/{world['id']}/simulations")

        simulation_location_ids = map_simulation_entities_by_name(
            api,
            "/locations",
            simulation["id"],
            setup.locations,
        )
        simulation_landmark_ids = map_simulation_entities_by_name(
            api,
            "/landmarks",
            simulation["id"],
            [
                landmark
                for landmarks in setup.landmarks_by_location.values()
                for landmark in landmarks
            ],
        )
        simulation_turn_ids = map_simulation_turns_by_sequence(api, simulation["id"], [setup.initial_turn])
        character_ids = map_simulation_entities_by_name(
            api,
            "/characters",
            simulation["id"],
            setup.characters,
        )
        background_character_ids = map_simulation_entities_by_name(
            api,
            "/background-characters",
            simulation["id"],
            setup.background_characters,
        )
        assert_characters_are_located(
            api,
            "Simulation",
            character_ids,
            simulation_location_ids,
        )
        simulation_equipment_ids = map_simulation_entities_by_name(
            api,
            "/equipment",
            simulation["id"],
            setup.equipment,
        )
        simulation_container_ids = map_simulation_entities_by_name(
            api,
            "/containers",
            simulation["id"],
            setup.containers,
        )
        intent_ids = create_intents(api, setup, character_ids)
        event_ids = create_events(api, setup, simulation_turn_ids, character_ids)
        memory_ids = create_memories(api, setup, event_ids, character_ids)

        return {
            "base_url": base_url,
            "author": author,
            "world": world,
            "simulation": simulation,
            "created_counts": {
                "locations": len(location_ids),
                "landmarks": len(landmark_ids),
                "turns": len(turn_ids),
                "characters": len(world_character_ids),
                "background_characters": len(world_background_character_ids),
                "items": len(item_ids),
                "stacks": len(stack_ids),
                "equipment": len(equipment_ids),
                "containers": len(container_ids),
                "events": len(event_ids),
                "memories": len(memory_ids),
                "intents": len(intent_ids),
            },
            "id_map": {
                "locations": location_ids,
                "landmarks": landmark_ids,
                "turns": turn_ids,
                "characters": world_character_ids,
                "background_characters": world_background_character_ids,
                "simulation_locations": simulation_location_ids,
                "simulation_landmarks": simulation_landmark_ids,
                "simulation_turns": simulation_turn_ids,
                "simulation_characters": character_ids,
                "simulation_background_characters": background_character_ids,
                "simulation_equipment": simulation_equipment_ids,
                "simulation_containers": simulation_container_ids,
                "items": item_ids,
                "stacks": stack_ids,
                "equipment": equipment_ids,
                "containers": container_ids,
                "events": event_ids,
                "memories": memory_ids,
                "intents": intent_ids,
            },
            "skipped": skipped,
        }
    finally:
        api.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Insert the evaluation sample world through a running backend API.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing worlds with the same sample world name before inserting.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    base_url = (
        os.getenv("WSE_API_BASE_URL")
        or os.getenv("WORLD_SIMULATION_ENGINE_API_URL")
        or os.getenv("API_BASE_URL")
        or "http://localhost:9797"
    )
    result = insert_sample_world(base_url, replace=args.replace)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
