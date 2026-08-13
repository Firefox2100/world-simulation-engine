"""
Insert an evaluation sample world through the backend HTTP API.

Reads a "world bundle" directory - the same format tests/evaluation_test/world_fixtures.py loads
directly into a DatabaseService for the evaluation test suite (see that module's docstring) - and
replays it through the real REST API instead: create the world-level template, POST
/worlds/{id}/simulations to instantiate a live simulation from it (exactly what a user does after
importing/creating a world), then map the copied simulation-scoped entities back by name to attach
simulation-scoped data (intents, events, memories, emotions) to them. This exercises the same
"template world -> instantiated simulation" path a real user goes through, unlike
world_fixtures.py's loader (which writes simulation-scoped rows directly, since evaluation tests
want an already-ready-to-run simulation, not a template to instantiate from).

Environment variables:
    WSE_API_BASE_URL, WORLD_SIMULATION_ENGINE_API_URL, or API_BASE_URL
        Base URL for the running backend. Defaults to http://localhost:9797.

Example:
    WSE_API_BASE_URL=http://localhost:9797 python scripts/insert_sample_world.py --replace
    python scripts/insert_sample_world.py --bundle tests/evaluation_test/assets/worlds/some-card --replace
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from world_simulation_engine.model import (  # noqa: E402
    Author,
    BackgroundCharacter,
    Character,
    Container,
    Equipment,
    EmotionVector,
    Event,
    Intent,
    Item,
    ItemStack,
    Landmark,
    Location,
    MemoryAtom,
    Turn,
    World,
)
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink  # noqa: E402

DEFAULT_BUNDLE_DIR = ROOT / "tests" / "evaluation_test" / "worlds" / "blackwater_observatory"


@dataclass(frozen=True)
class CharacterPlacement:
    character_id: str
    location_id: str | None
    position: str | None
    landmark_id: str | None


@dataclass(frozen=True)
class ContainerPlacement:
    container_id: str
    location_id: str | None
    position: str | None
    unlocking_item_ids: list[str]


@dataclass(frozen=True)
class ItemStackPlacement:
    item_id: str
    stack: ItemStack
    location_id: str | None
    position: str | None
    holder_id: str | None
    owner_id: str | None


@dataclass(frozen=True)
class EquipmentPlacement:
    equipment_id: str
    location_id: str | None
    position: str | None
    owner_id: str | None
    holder_id: str | None
    equipped: bool
    equipped_position: str | None


@dataclass(frozen=True)
class EventInvolvementSeed:
    event_id: str
    character_id: str
    involvement: str


@dataclass(frozen=True)
class MemorySeed:
    memory: MemoryAtom
    event_id: str
    support_type: str
    character_links: list[CharacterMemoryLink]


@dataclass(frozen=True)
class CharacterEmotionSeed:
    character_id: str
    baseline: EmotionVector


@dataclass(frozen=True)
class SampleWorldSetup:
    author: Author
    world: World
    initial_turn: Turn
    locations: list[Location]
    location_parents: dict[str, str | None]
    landmarks_by_location: dict[str, list[Landmark]]
    containers: list[Container]
    container_placements: list[ContainerPlacement]
    characters: list[Character]
    background_characters: list[BackgroundCharacter]
    character_placements: list[CharacterPlacement]
    background_character_placements: list[CharacterPlacement]
    items: list[Item]
    item_stack_placements: list[ItemStackPlacement]
    equipment: list[Equipment]
    equipment_placements: list[EquipmentPlacement]
    events: list[Event]
    event_involvements: list[EventInvolvementSeed]
    memories: list[MemorySeed]
    intents: list[Intent]
    intent_character_ids: dict[str, str]
    character_emotions: list[CharacterEmotionSeed]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_bundle_as_setup(bundle_dir: Path) -> SampleWorldSetup:
    """Read a world bundle directory (see world_fixtures.py) into the placement-list shape the
    rest of this script's REST-API-posting functions expect - a thin re-projection of each
    self-contained bundle row into the (entity, placement) pairs a template-world POST needs."""
    manifest = _read_json(bundle_dir / "manifest.json")
    if manifest.get("format_version") != 1:
        raise ValueError(f"Unsupported world bundle format version in {bundle_dir}: {manifest.get('format_version')!r}")

    author = Author.model_validate(_read_json(bundle_dir / "author.json"))
    world = World.model_validate(_read_json(bundle_dir / "world.json"))
    data = bundle_dir / "data"

    turn_rows = sorted(_read_jsonl(data / "turns.jsonl"), key=lambda row: row["sequence"])
    if not turn_rows:
        raise ValueError(f"World bundle {bundle_dir} has no turns - at least an opening turn is required")
    initial_turn = Turn.model_validate(turn_rows[0])

    location_rows = _read_jsonl(data / "locations.jsonl")
    locations = [Location.model_validate(row) for row in location_rows]
    location_parents = {row["id"]: row.get("parent_location_id") for row in location_rows}

    landmarks_by_location: dict[str, list[Landmark]] = {}
    for row in _read_jsonl(data / "landmarks.jsonl"):
        landmarks_by_location.setdefault(row["location_id"], []).append(Landmark.model_validate(row))

    container_rows = _read_jsonl(data / "containers.jsonl")
    containers = [Container.model_validate(row) for row in container_rows]
    container_placements = [
        ContainerPlacement(
            container_id=row["id"],
            location_id=row.get("location_id"),
            position=row.get("position"),
            unlocking_item_ids=row.get("unlocking_item_ids", []),
        )
        for row in container_rows
    ]

    character_rows = _read_jsonl(data / "characters.jsonl")
    characters = [Character.model_validate(row) for row in character_rows]
    character_placements = [
        CharacterPlacement(
            character_id=row["id"],
            location_id=row.get("location_id"),
            position=row.get("position"),
            landmark_id=row.get("landmark_id"),
        )
        for row in character_rows
    ]

    background_character_rows = _read_jsonl(data / "background_characters.jsonl")
    background_characters = [BackgroundCharacter.model_validate(row) for row in background_character_rows]
    background_character_placements = [
        CharacterPlacement(
            character_id=row["id"],
            location_id=row.get("location_id"),
            position=row.get("position"),
            landmark_id=row.get("landmark_id"),
        )
        for row in background_character_rows
    ]

    items = [Item.model_validate(row) for row in _read_jsonl(data / "items.jsonl")]

    item_stack_placements = []
    for row in _read_jsonl(data / "item_stacks.jsonl"):
        stack_row = {k: v for k, v in row.items() if k != "item_id"}
        item_stack_placements.append(ItemStackPlacement(
            item_id=row["item_id"],
            stack=ItemStack.model_validate(stack_row),
            location_id=row.get("location_id"),
            position=row.get("position"),
            holder_id=row.get("holder_id"),
            owner_id=row.get("owner_id"),
        ))

    equipment_rows = _read_jsonl(data / "equipment.jsonl")
    equipment = [Equipment.model_validate(row) for row in equipment_rows]
    equipment_placements = [
        EquipmentPlacement(
            equipment_id=row["id"],
            location_id=row.get("location_id"),
            position=row.get("position"),
            owner_id=row.get("owner_id"),
            holder_id=row.get("holder_id"),
            equipped=row.get("equipped", False),
            equipped_position=row.get("equipped_position"),
        )
        for row in equipment_rows
    ]

    events = [Event.model_validate(row) for row in _read_jsonl(data / "events.jsonl")]
    event_involvements = [
        EventInvolvementSeed(
            event_id=event_row["id"], character_id=involved["character_id"], involvement=involved["involvement"],
        )
        for event_row in _read_jsonl(data / "events.jsonl")
        for involved in event_row.get("involved_characters", [])
    ]

    memories = []
    for row in _read_jsonl(data / "memories.jsonl"):
        memory_row = {k: v for k, v in row.items() if k not in ("event_id", "support_type", "character_links")}
        memories.append(MemorySeed(
            memory=MemoryAtom.model_validate(memory_row),
            event_id=row["event_id"],
            support_type=row["support_type"],
            character_links=[CharacterMemoryLink.model_validate(link) for link in row.get("character_links", [])],
        ))

    intent_rows = _read_jsonl(data / "intents.jsonl")
    intents = [Intent.model_validate({k: v for k, v in row.items() if k != "character_id"}) for row in intent_rows]
    intent_character_ids = {row["id"]: row["character_id"] for row in intent_rows}

    character_emotions = [
        CharacterEmotionSeed(character_id=row["character_id"], baseline=EmotionVector.model_validate(row["baseline"]))
        for row in _read_jsonl(bundle_dir / "eval" / "character_emotions.jsonl")
    ]

    return SampleWorldSetup(
        author=author,
        world=world,
        initial_turn=initial_turn,
        locations=locations,
        location_parents=location_parents,
        landmarks_by_location=landmarks_by_location,
        containers=containers,
        container_placements=container_placements,
        characters=characters,
        background_characters=background_characters,
        character_placements=character_placements,
        background_character_placements=background_character_placements,
        items=items,
        item_stack_placements=item_stack_placements,
        equipment=equipment,
        equipment_placements=equipment_placements,
        events=events,
        event_involvements=event_involvements,
        memories=memories,
        intents=intents,
        intent_character_ids=intent_character_ids,
        character_emotions=character_emotions,
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

    def patch(self, path: str, **kwargs):
        return self._request("PATCH", path, **kwargs)

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


def create_character_emotions(
    api: Api,
    setup,
    simulation_id: str,
    character_ids: dict[str, str],
) -> None:
    for emotion_seed in setup.character_emotions:
        character_id = character_ids.get(emotion_seed.character_id)
        if not character_id:
            continue
        api.patch(
            f"/characters/{character_id}/emotion",
            params={"simulation_id": simulation_id},
            json={"baseline": emotion_seed.baseline.model_dump(mode="json")},
        )


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


def insert_sample_world(base_url: str, replace: bool, bundle_dir: Path) -> dict[str, Any]:
    setup = load_bundle_as_setup(bundle_dir)
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
        create_character_emotions(api, setup, simulation["id"], character_ids)

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
                "character_emotions": len(setup.character_emotions),
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
        description="Insert an evaluation sample world bundle through a running backend API.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing worlds with the same sample world name before inserting.",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=DEFAULT_BUNDLE_DIR,
        help=f"Path to a world bundle directory (see world_fixtures.py). Defaults to {DEFAULT_BUNDLE_DIR}.",
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
    result = insert_sample_world(base_url, replace=args.replace, bundle_dir=args.bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
