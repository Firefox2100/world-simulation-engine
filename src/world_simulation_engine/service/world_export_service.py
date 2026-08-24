"""Exports a world's authored template data (entities, prompts, non-connection configs, and
media) as a self-contained zip archive.

Connection profiles (base URLs, API keys) are deliberately excluded from every config so an
export never leaks instance-specific credentials, while still carrying enough of each model
config (provider, model name, sampling parameters) to reproduce the same setup elsewhere.
"""

import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from world_simulation_engine.misc.enums import MediaType
from world_simulation_engine.model import MediaFile
from world_simulation_engine.service.database import DatabaseService
from world_simulation_engine.service.storage_service import StorageService
from world_simulation_engine.service.world_bundle_spec import WORLD_BUNDLE_SPEC, WORLD_BUNDLE_SPEC_VERSION

_ALL_TURNS_LIMIT = 1_000_000
_ALL_RELATIONSHIPS_LIMIT = 100_000

_MEDIA_EXTENSIONS = {
    MediaType.PNG: "png",
    MediaType.JSON: "json",
    MediaType.WAV: "wav",
}

def _dump(model: Any) -> dict:
    return model.model_dump(mode="json")


def _strip_connection(config: Any) -> dict:
    """Config is shared setup, not instance-specific data, but the connection it uses (base_url,
    api_key) is - so it's the one thing always zeroed out of an export."""
    data = config.model_dump(mode="json")
    data["connection"] = None
    return data


def _media_filename(media: MediaFile) -> str:
    extension = _MEDIA_EXTENSIONS.get(media.type, "bin")
    return f"{media.id}.{extension}"


def _jsonl(rows: list[dict]) -> bytes:
    return ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else "")).encode("utf-8")


class WorldExportService:
    def __init__(self, database: DatabaseService, storage: StorageService):
        self._db = database
        self._storage = storage

    async def export_world(self, world_id: str) -> bytes:
        db = self._db
        world = await db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found")

        author = await db.world.get_author_by_world(world_id)

        locations = await db.location.list_locations(world_id=world_id)
        landmarks = await db.location.list_landmarks(world_id=world_id)
        location_parents = await db.location.get_parent_map(world_id)
        landmark_locations = await db.location.get_landmark_location_map(world_id)

        characters = await db.character.list_characters(world_id=world_id)
        character_positions = await db.character.get_position_map(source_id=world_id)
        background_characters = await db.character.list_background_characters(world_id=world_id)
        background_positions = await db.character.get_background_position_map(source_id=world_id)

        items = await db.item.list_items(world_id=world_id)
        stacks = await db.item.list_stacks(world_id=world_id)
        equipment = await db.equipment.list_equipment(world_id=world_id)
        equipment_hold_types = await db.equipment.get_hold_types([item.id for item in equipment])
        containers = await db.container.list_containers(world_id=world_id)
        held_by_holder = self._group_holdings(stacks, equipment, containers)
        unlocking_items_by_container = await self._collect_unlocking_items(containers)

        turns = await db.turn.list_turns(source_id=world_id, limit=_ALL_TURNS_LIMIT)
        events = await self._collect_events(turns)
        turn_links = await db.event.get_turn_links([event.id for event in events])
        involvements = await db.event.get_character_involvements([event.id for event in events])

        memories = await self._collect_memories(events)
        memory_event_links = await db.memory.get_event_links([memory.id for memory in memories])
        memory_character_links = await db.memory.get_character_links([memory.id for memory in memories])

        intents = await self._collect_intents(characters)
        intent_event_links = await db.intent.get_event_links([intent.id for intent in intents])
        intent_holders = await db.intent.get_holder_map([intent.id for intent in intents])

        relationships = await db.entity_relationship.list_relationships(
            scope_id=world_id,
            active_only=False,
            limit=_ALL_RELATIONSHIPS_LIMIT,
        )
        subjective_claims = await db.subjective_entity_claim.list_world_claims(world_id)
        entity_variable_sets = await db.variable.list_variable_sets_by_source(world_id)

        chat_assignments = await db.config.list_chats_by_source(world_id)
        embed_assignments = await db.config.list_embeds_by_source(world_id)
        image_assignments = await db.config.list_images_by_source(world_id)
        tts_assignments = await db.config.list_ttss_by_source(world_id)

        character_tts_configs = await self._collect_character_tts_configs(characters)

        prompt_media = await db.media.list_prompt_media(world_id=world_id)
        workflow_media = await db.media.list_workflow_media(world_id=world_id)

        cover_media_by_target = await self._collect_covers(world_id, locations, landmarks, characters,
                                                            background_characters, items, equipment, containers)

        media_by_id: dict[str, MediaFile] = {}
        for media in [*cover_media_by_target.values(), *prompt_media, *workflow_media]:
            media_by_id[media.id] = media

        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps({
                "spec": WORLD_BUNDLE_SPEC,
                "spec_version": WORLD_BUNDLE_SPEC_VERSION,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "world_id": world_id,
                "world_name": world.name,
            }, ensure_ascii=False, indent=2))
            archive.writestr("world.json", json.dumps({
                **_dump(world),
                "cover_media_id": self._cover_id(cover_media_by_target, "world", world_id),
            }, ensure_ascii=False, indent=2))
            archive.writestr("author.json", json.dumps(_dump(author) if author else None, ensure_ascii=False, indent=2))

            archive.writestr("data/locations.jsonl", _jsonl([
                {**_dump(location), "parent_location_id": location_parents.get(location.id)}
                for location in locations
            ]))
            archive.writestr("data/landmarks.jsonl", _jsonl([
                {
                    **_dump(landmark),
                    "location_id": landmark_locations.get(landmark.id),
                    "cover_media_id": self._cover_id(cover_media_by_target, "landmarks", landmark.id),
                }
                for landmark in landmarks
            ]))
            archive.writestr("data/characters.jsonl", _jsonl([
                {
                    **_dump(character),
                    **character_positions.get(character.id, {"location_id": None, "position": None, "landmark_id": None}),
                    "tts_config": character_tts_configs.get(character.id),
                    "cover_media_id": self._cover_id(cover_media_by_target, "characters", character.id),
                }
                for character in characters
            ]))
            archive.writestr("data/background_characters.jsonl", _jsonl([
                {
                    **_dump(character),
                    **background_positions.get(
                        character.id, {"location_id": None, "position": None, "landmark_id": None},
                    ),
                    "cover_media_id": self._cover_id(cover_media_by_target, "background_characters", character.id),
                }
                for character in background_characters
            ]))
            archive.writestr("data/items.jsonl", _jsonl([
                {**_dump(item), "cover_media_id": self._cover_id(cover_media_by_target, "items", item.id)}
                for item in items
            ]))
            archive.writestr("data/item_stacks.jsonl", _jsonl([
                {
                    **{key: value for key, value in _dump(stack).items() if key != "item"},
                    "item_id": stack.item.id if stack.item else None,
                }
                for stack in stacks
            ]))
            archive.writestr("data/equipment.jsonl", _jsonl([
                {
                    **_dump(item),
                    **equipment_hold_types.get(item.id, {"equipped": False, "equipped_position": None}),
                    "cover_media_id": self._cover_id(cover_media_by_target, "equipment", item.id),
                }
                for item in equipment
            ]))
            archive.writestr("data/containers.jsonl", _jsonl([
                {
                    **_dump(container),
                    **held_by_holder.get(
                        container.id,
                        {"held_stack_ids": [], "held_equipment_ids": [], "held_container_ids": []},
                    ),
                    "unlocking_item_ids": unlocking_items_by_container.get(container.id, []),
                    "cover_media_id": self._cover_id(cover_media_by_target, "containers", container.id),
                }
                for container in containers
            ]))
            archive.writestr("data/turns.jsonl", _jsonl([_dump(turn) for turn in turns]))
            archive.writestr("data/events.jsonl", _jsonl([
                {
                    **_dump(event),
                    "turn_ids": turn_links.get(event.id, []),
                    "involved_characters": involvements.get(event.id, []),
                }
                for event in events
            ]))
            archive.writestr("data/memories.jsonl", _jsonl([
                {
                    **_dump(memory),
                    **(memory_event_links.get(memory.id) or {"event_id": None, "support_type": None}),
                    "character_links": memory_character_links.get(memory.id, []),
                }
                for memory in memories
            ]))
            archive.writestr("data/intents.jsonl", _jsonl([
                {
                    **_dump(intent),
                    **intent_event_links.get(intent.id, {"created_by_event_id": None, "contributed_by_event_ids": []}),
                    "character_id": intent_holders.get(intent.id),
                }
                for intent in intents
            ]))
            archive.writestr("data/entity_relationships.jsonl", _jsonl([
                _dump(relationship) for relationship in relationships
            ]))
            archive.writestr("data/subjective_entity_claims.jsonl", _jsonl([
                _dump(claim) for claim in subjective_claims
            ]))
            archive.writestr("data/entity_variable_sets.jsonl", _jsonl([
                _dump(variable_set) for variable_set in entity_variable_sets
            ]))

            archive.writestr("configs/chat.jsonl", _jsonl([
                {"component": str(component), "config": _strip_connection(config)}
                for component, config in chat_assignments.items()
            ]))
            archive.writestr("configs/embed.jsonl", _jsonl([
                {"component": str(component), "config": _strip_connection(config)}
                for component, config in embed_assignments.items()
            ]))
            archive.writestr("configs/image.jsonl", _jsonl([
                {"component": str(component), "config": _strip_connection(config)}
                for component, config in image_assignments.items()
            ]))
            archive.writestr("configs/tts.jsonl", _jsonl(
                self._tts_config_rows(tts_assignments, character_tts_configs),
            ))

            archive.writestr("prompts.jsonl", _jsonl([
                {
                    "component": str(media.component) if media.component else None,
                    "language": str(media.language),
                    "prompt_name": media.prompt_name,
                    "media_id": media.id,
                }
                for media in prompt_media
            ]))
            archive.writestr("workflows.jsonl", _jsonl([
                {"workflow_name": media.workflow_name, "media_id": media.id}
                for media in workflow_media
            ]))

            media_manifest_rows = []
            for media in media_by_id.values():
                media_manifest_rows.append({**_dump(media), "file": f"media/files/{_media_filename(media)}"})
                if await self._storage.exists(media.hash):
                    content = await self._storage.get_bytes(media.hash)
                    archive.writestr(f"media/files/{_media_filename(media)}", content)
            archive.writestr("media/manifest.jsonl", _jsonl(media_manifest_rows))

        return buffer.getvalue()

    @staticmethod
    def _cover_id(cover_media_by_target: dict[tuple[str, str], MediaFile], section: str, entity_id: str) -> str | None:
        media = cover_media_by_target.get((section, entity_id))
        return media.id if media else None

    async def _collect_covers(self, world_id, locations, landmarks, characters, background_characters,
                              items, equipment, containers) -> dict[tuple[str, str], MediaFile]:
        targets = [("world", world_id)]
        targets += [("locations", entity.id) for entity in locations]
        targets += [("landmarks", entity.id) for entity in landmarks]
        targets += [("characters", entity.id) for entity in characters]
        targets += [("background_characters", entity.id) for entity in background_characters]
        targets += [("items", entity.id) for entity in items]
        targets += [("equipment", entity.id) for entity in equipment]
        targets += [("containers", entity.id) for entity in containers]

        covers: dict[tuple[str, str], MediaFile] = {}
        for section, entity_id in targets:
            cover = await self._db.media.get_cover_image(entity_id)
            if cover:
                covers[(section, entity_id)] = cover
        return covers

    async def _collect_events(self, turns) -> list:
        events_by_id: dict[str, Any] = {}
        for turn in turns:
            for event in await self._db.event.list_events(turn_id=turn.id):
                events_by_id[event.id] = event
        return list(events_by_id.values())

    async def _collect_memories(self, events) -> list:
        memories_by_id: dict[str, Any] = {}
        for event in events:
            for memory in await self._db.memory.list_memories(event_id=event.id):
                memories_by_id[memory.id] = memory
        return list(memories_by_id.values())

    async def _collect_intents(self, characters) -> list:
        intents_by_id: dict[str, Any] = {}
        for character in characters:
            for intent in await self._db.intent.list_intents(character_id=character.id):
                intents_by_id[intent.id] = intent
        return list(intents_by_id.values())

    async def _collect_character_tts_configs(self, characters) -> dict[str, dict]:
        configs = {}
        for character in characters:
            config = await self._db.character_tts_config.get_character_tts_config(character.id)
            if config:
                configs[character.id] = {
                    "character_voice": config.character_voice,
                    "rvc_character_voice": config.rvc_character_voice,
                    "rvc_character_pitch": config.rvc_character_pitch,
                    "backend_config_id": config.backend.id if config.backend else None,
                    "backend": _strip_connection(config.backend) if config.backend else None,
                }
        return configs

    async def _collect_unlocking_items(self, containers) -> dict[str, list[str]]:
        unlocking_items = {}
        for container in containers:
            items = await self._db.container.get_unlocking_items(container.id)
            if items:
                unlocking_items[container.id] = [item.id for item in items]
        return unlocking_items

    @staticmethod
    def _group_holdings(stacks, equipment, containers) -> dict[str, dict[str, list[str]]]:
        held: dict[str, dict[str, list[str]]] = {}

        def add(holder_id: str | None, key: str, entity_id: str) -> None:
            if not holder_id:
                return
            held.setdefault(holder_id, {"held_stack_ids": [], "held_equipment_ids": [], "held_container_ids": []})
            held[holder_id][key].append(entity_id)

        for stack in stacks:
            add(stack.holder_id, "held_stack_ids", stack.id)
        for item in equipment:
            add(item.holder_id, "held_equipment_ids", item.id)
        for container in containers:
            add(container.holder_id, "held_container_ids", container.id)

        return held

    @staticmethod
    def _tts_config_rows(tts_assignments: dict, character_tts_configs: dict[str, dict]) -> list[dict]:
        """configs/tts.jsonl carries every distinct backend referenced anywhere - per-component
        assignments (component set) and character voices (component null, since a character's
        backend need not be assigned to any component) - deduplicated by config id."""
        rows_by_id: dict[str, dict] = {}
        for component, config in tts_assignments.items():
            rows_by_id[config.id] = {"component": str(component), "config": _strip_connection(config)}
        for character_config in character_tts_configs.values():
            backend = character_config.get("backend")
            if backend and backend["id"] not in rows_by_id:
                rows_by_id[backend["id"]] = {"component": None, "config": backend}
        return list(rows_by_id.values())
