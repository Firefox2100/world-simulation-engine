"""Loads a self-contained "world bundle" directory into a live, simulation-scoped
`DatabaseService` for the evaluation_test suite.

A bundle directory is the same shape `WorldExportService` produces (unzipped): `manifest.json`,
`world.json`, `author.json`, `data/*.jsonl` - plus an `eval/` subdirectory of extras that only
make sense for a test fixture, not a real export: `eval/simulation.json` (the live `Simulation`
this bundle instantiates - a real export has no such thing, only a reusable world *template*),
`eval/character_emotions.jsonl` (baseline `EmotionState`s - emotions are simulation-runtime state,
never part of a world export either), and `eval/scenarios.json` (hand-authored "intended input"
test cases - e.g. `SceneCoordinationResult` fixtures and free-text turns - that exercise this
bundle's specific characters/locations/items).

Unlike `WorldImportService` (which always mints fresh ids - the right call for a real user
importing an untrusted upload, so two imports of the same archive can never collide), this loader
preserves every id exactly as authored in the bundle: a bundle's ids are trusted, stable,
human-chosen values (e.g. "character_arthur_moore") that both test code and its own
`eval/scenarios.json` reference directly, and that stability across runs is the entire point.

Unlike the real world-to-simulation instantiation path (`create_simulation` in
`router/simulation.py`, which copies a reusable *template* World into a fresh Simulation with new
ids), this loader creates every entity directly scoped to a `Simulation` in one pass: a bundle
represents a ready-to-run evaluation scenario, not a template a user browses before choosing to
start playing, so there is no separate "template" stage to model here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from world_simulation_engine.misc.enums import EventInvolvement, MemorySupportType
from world_simulation_engine.model import (
    Author,
    BackgroundCharacter,
    Character,
    Container,
    EmotionState,
    EmotionVector,
    Equipment,
    Event,
    Intent,
    Item,
    ItemStack,
    Landmark,
    Location,
    MemoryAtom,
    Simulation,
    Turn,
    World,
)
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink

_SUPPORTED_FORMAT_VERSION = 1

# Every evaluation world bundle - both the checked-in default (blackwater_observatory) and any
# SillyTavern-card-derived ones generated locally via scripts/build_card_world_bundle.py - lives
# under this one directory. tests/evaluation_test/worlds/.gitignore excludes every subdirectory
# here from git *except* an explicit allow-list (blackwater_observatory today): a generated
# world's content may be licensed SillyTavern card material (CLAUDE.md hard rule 2), so a new
# bundle is never committed by accident - checking one in is an explicit, deliberate edit to that
# .gitignore, not the default.
WORLDS_DIR = Path(__file__).parent / "worlds"
DEFAULT_WORLD_DIR = WORLDS_DIR / "blackwater_observatory"


def discover_world_dirs() -> list[Path]:
    """Every world bundle available to the evaluation suite (whether checked into git or only
    generated locally) - sorted for stable test collection order. A fresh checkout with nothing
    generated yet still returns at least the checked-in ones."""
    if not WORLDS_DIR.is_dir():
        return []
    return sorted((entry for entry in WORLDS_DIR.iterdir() if entry.is_dir()), key=lambda path: path.name)


@dataclass(frozen=True)
class WorldBundle:
    """Everything a loaded bundle's tests need: the live `Simulation` to run components against,
    plus its `eval/scenarios.json` ("intended input" test cases for this bundle specifically)."""

    author: Author
    world: World
    simulation: Simulation
    initial_turn: Turn
    scenarios: dict[str, Any]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def load_world_bundle(database: DatabaseService, folder: Path) -> WorldBundle:
    manifest = _read_json(folder / "manifest.json")
    if manifest.get("format_version") != _SUPPORTED_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported world bundle format version in {folder}: {manifest.get('format_version')!r}"
        )

    author = Author.model_validate(_read_json(folder / "author.json"))
    world = World.model_validate(_read_json(folder / "world.json"))
    simulation = Simulation.model_validate(_read_json(folder / "eval" / "simulation.json"))
    # Optional: a freshly-generated bundle may not have any hand-authored "intended input" cases
    # yet (see scripts/build_card_world_bundle.py) - an empty scenarios file just means this world
    # contributes zero parametrized cases until someone adds them, not a broken bundle.
    scenarios_path = folder / "eval" / "scenarios.json"
    scenarios = _read_json(scenarios_path) if scenarios_path.exists() else {}

    await database.world.create_author(author)
    await database.world.create_world(world, author.id)
    await database.simulation.create_simulation(simulation, world.id)

    data = folder / "data"

    turn_rows = sorted(_read_jsonl(data / "turns.jsonl"), key=lambda r: r["sequence"])
    if not turn_rows:
        raise ValueError(f"World bundle {folder} has no turns - at least an opening turn is required")
    initial_turn = Turn.model_validate(turn_rows[0])
    for row in turn_rows:
        await database.turn.create_turn(Turn.model_validate(row), simulation.id)

    # Locations and (conceptual) items are world-level authored content; everything else below is
    # simulation-level - matches WorldExportService's own World-vs-Simulation split.
    for row in _read_jsonl(data / "locations.jsonl"):
        await database.location.create_location(
            location=Location.model_validate(row),
            source_id=world.id,
            contained_in=row.get("parent_location_id"),
        )

    for row in _read_jsonl(data / "landmarks.jsonl"):
        await database.location.create_landmark(Landmark.model_validate(row), row["location_id"])

    for row in _read_jsonl(data / "containers.jsonl"):
        await database.container.create_container(
            container=Container.model_validate(row),
            source_id=simulation.id,
            location_id=row.get("location_id"),
            position=row.get("position"),
        )

    for row in _read_jsonl(data / "characters.jsonl"):
        character = Character.model_validate(row)
        await database.character.create_character(character, simulation.id)
        if row.get("location_id"):
            await database.character.move_to_location(
                character_id=character.id, location_id=row["location_id"], position=row.get("position"),
            )
        if row.get("landmark_id"):
            await database.character.anchor_to_landmark(character.id, row["landmark_id"])

    for row in _read_jsonl(data / "background_characters.jsonl"):
        await database.character.create_background_character(
            BackgroundCharacter.model_validate(row),
            source_id=simulation.id,
            location_id=row.get("location_id"),
            position=row.get("position"),
            landmark_id=row.get("landmark_id"),
        )

    for row in _read_jsonl(data / "items.jsonl"):
        await database.item.create_item(Item.model_validate(row), world.id)

    for row in _read_jsonl(data / "item_stacks.jsonl"):
        stack_row = {k: v for k, v in row.items() if k != "item_id"}
        await database.item.create_stack(
            item_id=row["item_id"],
            stack=ItemStack.model_validate(stack_row),
            location_id=row.get("location_id"),
            position=row.get("position"),
            source_id=simulation.id,
            holder_id=row.get("holder_id"),
            owner_id=row.get("owner_id"),
        )

    for row in _read_jsonl(data / "equipment.jsonl"):
        equipment = Equipment.model_validate(row)
        await database.equipment.create_equipment(
            equipment, source_id=simulation.id, location_id=row.get("location_id"), position=row.get("position"),
        )
        if row.get("owner_id"):
            await database.equipment.change_owner(equipment.id, row["owner_id"])
        if row.get("holder_id"):
            await database.equipment.change_hold_state(
                equipment_id=equipment.id,
                holder_id=row["holder_id"],
                equipped=row.get("equipped", False),
                equipped_position=row.get("equipped_position"),
            )

    for row in _read_jsonl(data / "containers.jsonl"):
        for item_id in row.get("unlocking_item_ids", []):
            await database.container.add_unlocking_item(item_id, row["id"])

    all_turn_ids = [row["id"] for row in _read_jsonl(data / "turns.jsonl")]
    for row in _read_jsonl(data / "events.jsonl"):
        event = Event.model_validate(row)
        await database.event.create_event(event, turn_ids=row.get("turn_ids") or all_turn_ids)
        for involved in row.get("involved_characters", []):
            await database.event.add_character_involvement(
                event_id=event.id,
                character_id=involved["character_id"],
                involvement=EventInvolvement(involved["involvement"]),
            )

    for row in _read_jsonl(data / "memories.jsonl"):
        memory_row = {k: v for k, v in row.items() if k not in ("event_id", "support_type", "character_links")}
        await database.memory.create_memory_atom(
            memory=MemoryAtom.model_validate(memory_row),
            event_id=row["event_id"],
            support_type=MemorySupportType(row["support_type"]),
            character_links=[CharacterMemoryLink.model_validate(link) for link in row.get("character_links", [])],
        )

    for row in _read_jsonl(data / "intents.jsonl"):
        intent_row = {k: v for k, v in row.items() if k != "character_id"}
        await database.intent.create_intent(
            intent=Intent.model_validate(intent_row), character_id=row["character_id"],
        )

    for row in _read_jsonl(folder / "eval" / "character_emotions.jsonl"):
        await database.emotion.create_state(EmotionState(
            simulation_id=simulation.id,
            character_id=row["character_id"],
            baseline=EmotionVector.model_validate(row["baseline"]),
            last_updated_at=simulation.current_time,
        ))

    return WorldBundle(
        author=author, world=world, simulation=simulation, initial_turn=initial_turn, scenarios=scenarios,
    )
