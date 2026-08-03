"""Imports a world archive produced by ``WorldExportService`` back into the database.

A world is always created fresh (new ids throughout), even if a world with the same name already
exists - re-importing the same archive twice is expected to produce two independent worlds. The
two exceptions are:

- Configurations (chat/embed/image/tts model configs) are deduplicated against whatever already
  exists in the target system: if an existing configuration matches the imported one exactly
  (ignoring id and connection, since connection is never exported), the existing one is reused
  instead of creating a duplicate.
- Media files are deduplicated by content hash: if a media node with the same hash and the same
  logical role (same prompt/workflow identity, or - for generic media such as covers - just the
  same hash) already exists, it is reused instead of creating a new node. The underlying blob
  storage is already hash-addressed, so this only avoids redundant *Media* graph nodes.
"""

import json
from io import BytesIO
from typing import Any
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from pydantic import TypeAdapter, ValidationError

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import BackgroundCharacter, Character, CharacterTtsConfig, ChatModelConfigUnion, \
    Container, EmbedModelConfigUnion, EntityRelationship, EntityVariableSet, Equipment, Event, \
    ImageModelConfigUnion, Intent, Item, ItemStack, Landmark, Location, MediaFile, MemoryAtom, PromptMediaFile, \
    Turn, TtsModelConfigUnion, WorkflowMediaFile, World
from world_simulation_engine.service.database import DatabaseService
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink
from world_simulation_engine.service.storage_service import StorageService

_SUPPORTED_FORMAT_VERSION = 1

_ChatConfigAdapter = TypeAdapter(ChatModelConfigUnion)
_EmbedConfigAdapter = TypeAdapter(EmbedModelConfigUnion)
_ImageConfigAdapter = TypeAdapter(ImageModelConfigUnion)
_TtsConfigAdapter = TypeAdapter(TtsModelConfigUnion)


class WorldImportError(ValueError):
    """The uploaded archive is missing, corrupted, or not in the expected export format."""


class AuthorNotFoundError(Exception):
    """The author_id supplied for the import does not exist."""


def _media_model_from_row(row: dict) -> MediaFile:
    if row.get("prompt_name") is not None:
        return PromptMediaFile.model_validate(row)
    if row.get("workflow_name") is not None:
        return WorkflowMediaFile.model_validate(row)
    return MediaFile.model_validate(row)


def _find_media_match(candidate: MediaFile, existing: list[MediaFile]) -> MediaFile | None:
    for other in existing:
        if type(other) is not type(candidate):
            continue
        if isinstance(candidate, PromptMediaFile):
            if (other.prompt_name, other.language, other.component) == \
                    (candidate.prompt_name, candidate.language, candidate.component):
                return other
        elif isinstance(candidate, WorkflowMediaFile):
            if other.workflow_name == candidate.workflow_name:
                return other
        else:
            return other
    return None


def _configs_equal(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a.model_dump(exclude={"id", "connection"}) == b.model_dump(exclude={"id", "connection"})


class WorldImportService:
    def __init__(self, database: DatabaseService, storage: StorageService):
        self._db = database
        self._storage = storage

    async def import_world(self, archive_bytes: bytes, author_id: str) -> World:
        archive = self._open_archive(archive_bytes)

        manifest = self._read_json(archive, "manifest.json")
        if not isinstance(manifest, dict) or manifest.get("format_version") != _SUPPORTED_FORMAT_VERSION:
            raise WorldImportError(
                f"Unsupported export format version: {manifest.get('format_version') if isinstance(manifest, dict) else manifest!r}"
            )

        world_row = self._read_json(archive, "world.json")
        if not isinstance(world_row, dict):
            raise WorldImportError("The archive's world.json is not a valid world record")

        sections = {
            "locations": self._read_jsonl(archive, "data/locations.jsonl"),
            "landmarks": self._read_jsonl(archive, "data/landmarks.jsonl"),
            "characters": self._read_jsonl(archive, "data/characters.jsonl"),
            "background_characters": self._read_jsonl(archive, "data/background_characters.jsonl"),
            "items": self._read_jsonl(archive, "data/items.jsonl"),
            "item_stacks": self._read_jsonl(archive, "data/item_stacks.jsonl"),
            "equipment": self._read_jsonl(archive, "data/equipment.jsonl"),
            "containers": self._read_jsonl(archive, "data/containers.jsonl"),
            "turns": self._read_jsonl(archive, "data/turns.jsonl"),
            "events": self._read_jsonl(archive, "data/events.jsonl"),
            "memories": self._read_jsonl(archive, "data/memories.jsonl"),
            "intents": self._read_jsonl(archive, "data/intents.jsonl"),
            "entity_relationships": self._read_jsonl(archive, "data/entity_relationships.jsonl"),
            # Optional: added after entity variable sets existed. Older archives simply don't have
            # this file, and a world/simulation with no tracked variables is a normal, common case
            # even for archives that do.
            "entity_variable_sets": self._read_optional_jsonl(archive, "data/entity_variable_sets.jsonl"),
            "chat_configs": self._read_jsonl(archive, "configs/chat.jsonl"),
            "embed_configs": self._read_jsonl(archive, "configs/embed.jsonl"),
            "image_configs": self._read_jsonl(archive, "configs/image.jsonl"),
            "tts_configs": self._read_jsonl(archive, "configs/tts.jsonl"),
            "prompts": self._read_jsonl(archive, "prompts.jsonl"),
            "workflows": self._read_jsonl(archive, "workflows.jsonl"),
            "media": self._read_jsonl(archive, "media/manifest.jsonl"),
        }

        try:
            world = World.model_validate({**world_row, "id": str(uuid4())})
        except ValidationError as exc:
            raise WorldImportError(f"Invalid world data in archive: {exc}") from exc

        created_world = await self._db.world.create_world(world, author_id)
        if not created_world:
            raise AuthorNotFoundError(author_id)

        try:
            await self._import_world_contents(created_world, world_row, sections, archive)
        except (ValidationError, KeyError, TypeError, IndexError) as exc:
            raise WorldImportError(f"The archive contains invalid or unexpected data: {exc}") from exc

        return created_world

    async def import_assembled_sections(self,
                                        world_row: dict,
                                        sections: dict[str, list],
                                        author_id: str,
                                        ) -> World:
        """Entry point for a caller that already has a `world`/`sections` bundle in memory - shaped
        exactly like `import_world` builds from an archive - rather than a real uploaded zip file
        (e.g. the SillyTavern import pipeline's `WorldAssembler` output). Skips the archive
        round-trip `import_world` needs for a real upload: there is no zip to open, and `sections`
        never carries media for this caller, so `archive=None` is safe (`_import_media` never
        touches it when `sections["media"]` is empty)."""
        try:
            world = World.model_validate({**world_row, "id": str(uuid4())})
        except ValidationError as exc:
            raise WorldImportError(f"Invalid world data: {exc}") from exc

        created_world = await self._db.world.create_world(world, author_id)
        if not created_world:
            raise AuthorNotFoundError(author_id)

        try:
            await self._import_world_contents(created_world, world_row, sections, archive=None)
        except (ValidationError, KeyError, TypeError, IndexError) as exc:
            raise WorldImportError(
                f"The assembled world contains invalid or unexpected data: {exc}"
            ) from exc

        return created_world

    async def _import_world_contents(self,
                                     world: World,
                                     world_row: dict,
                                     sections: dict[str, list],
                                     archive: ZipFile | None,
                                     ) -> None:
        media_id_map = await self._import_media(archive, sections["media"])

        id_map: dict[str, str] = {}
        await self._import_locations(world.id, sections["locations"], id_map)
        await self._import_landmarks(sections["landmarks"], id_map, media_id_map)
        await self._import_characters(world.id, sections["characters"], id_map, media_id_map)
        await self._import_background_characters(world.id, sections["background_characters"], id_map, media_id_map)
        await self._import_items(world.id, sections["items"], id_map, media_id_map)
        await self._import_containers(world.id, sections["containers"], id_map, media_id_map)
        await self._import_equipment(world.id, sections["equipment"], id_map, media_id_map)
        await self._import_item_stacks(world.id, sections["item_stacks"], id_map)

        turn_id_map = await self._import_turns(world.id, sections["turns"])
        event_id_map = await self._import_events(sections["events"], turn_id_map, id_map)
        memory_id_map = await self._import_memories(sections["memories"], event_id_map, id_map)
        await self._import_intents(sections["intents"], id_map, event_id_map)
        await self._import_relationships(world.id, sections["entity_relationships"], id_map, memory_id_map)
        await self._import_entity_variable_sets(world.id, sections["entity_variable_sets"], id_map)

        await self._import_chat_assignments(world.id, sections["chat_configs"])
        await self._import_embed_assignments(world.id, sections["embed_configs"])
        await self._import_image_assignments(world.id, sections["image_configs"])
        tts_id_map = await self._import_tts_assignments(world.id, sections["tts_configs"])
        await self._import_character_tts_configs(sections["characters"], id_map, tts_id_map)

        await self._import_prompts(world.id, sections["prompts"], media_id_map)
        await self._import_workflows(world.id, sections["workflows"], media_id_map)

        world_cover = media_id_map.get(world_row.get("cover_media_id"))
        if world_cover:
            await self._db.media.set_cover_image(world.id, world_cover)

    # -- archive reading -------------------------------------------------------------------

    @staticmethod
    def _open_archive(archive_bytes: bytes) -> ZipFile:
        try:
            archive = ZipFile(BytesIO(archive_bytes))
        except BadZipFile as exc:
            raise WorldImportError("The uploaded file is not a valid zip archive") from exc

        if archive.testzip() is not None:
            raise WorldImportError("The uploaded zip archive is corrupted")

        return archive

    @staticmethod
    def _read_member(archive: ZipFile, name: str) -> bytes:
        try:
            return archive.read(name)
        except KeyError as exc:
            raise WorldImportError(f"The archive is missing required file {name!r}") from exc
        except Exception as exc:
            raise WorldImportError(f"The archive file {name!r} could not be read (corrupted archive?)") from exc

    @classmethod
    def _read_json(cls, archive: ZipFile, name: str) -> Any:
        raw = cls._read_member(archive, name)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorldImportError(f"The archive file {name!r} is not valid JSON") from exc

    @classmethod
    def _read_jsonl(cls, archive: ZipFile, name: str) -> list[dict]:
        raw = cls._read_member(archive, name)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorldImportError(f"The archive file {name!r} is not valid UTF-8 text") from exc

        rows = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise WorldImportError(f"The archive file {name!r} has invalid JSON on line {line_number}") from exc
            if not isinstance(row, dict):
                raise WorldImportError(f"The archive file {name!r} has an unexpected entry on line {line_number}")
            rows.append(row)

        return rows

    @classmethod
    def _read_optional_jsonl(cls, archive: ZipFile, name: str) -> list[dict]:
        """Like `_read_jsonl`, but a missing file means "no rows" rather than a corrupt archive."""
        if name not in archive.namelist():
            return []
        return cls._read_jsonl(archive, name)

    # -- media ------------------------------------------------------------------------------

    async def _import_media(self, archive: ZipFile | None, rows: list[dict]) -> dict[str, str]:
        media_id_map: dict[str, str] = {}

        for row in rows:
            candidate = _media_model_from_row(row)
            existing = await self._db.media.get_media_by_hash(candidate.hash)
            match = _find_media_match(candidate, existing)
            if match:
                media_id_map[row["id"]] = match.id
                continue

            file_path = row.get("file")
            if file_path and file_path in archive.namelist():
                content = self._read_member(archive, file_path)
                await self._storage.save_bytes(content, expected_digest=candidate.hash)

            new_media = candidate.model_copy(update={"id": str(uuid4())})
            created = await self._db.media.create_media(new_media)
            media_id_map[row["id"]] = created.id

        return media_id_map

    # -- world entities -----------------------------------------------------------------------

    async def _import_locations(self, world_id: str, rows: list[dict], id_map: dict[str, str]) -> None:
        by_parent: dict[str | None, list[dict]] = {}
        for row in rows:
            by_parent.setdefault(row.get("parent_location_id"), []).append(row)

        queue = list(by_parent.get(None, []))
        processed = 0
        while queue:
            row = queue.pop(0)
            location = Location.model_validate(row).model_copy(update={"id": str(uuid4())})
            parent_id = id_map.get(row["parent_location_id"]) if row.get("parent_location_id") else None
            created = await self._db.location.create_location(location, world_id, contained_in=parent_id)
            if not created:
                raise WorldImportError(f"Failed to import location {row['id']!r}")
            id_map[row["id"]] = created.id
            processed += 1
            queue.extend(by_parent.get(row["id"], []))

        if processed != len(rows):
            raise WorldImportError("The location hierarchy in the archive is inconsistent (orphaned parent references)")

    async def _import_landmarks(self, rows: list[dict], id_map: dict[str, str], media_id_map: dict[str, str]) -> None:
        for row in rows:
            landmark = Landmark.model_validate(row).model_copy(update={"id": str(uuid4())})
            location_id = id_map.get(row.get("location_id"))
            if not location_id:
                raise WorldImportError(f"Landmark {row['id']!r} references an unknown location")

            created = await self._db.location.create_landmark(landmark, location_id)
            if not created:
                raise WorldImportError(f"Failed to import landmark {row['id']!r}")
            id_map[row["id"]] = created.id

            await self._maybe_set_cover(created.id, row, media_id_map)

    async def _import_characters(self,
                                 world_id: str,
                                 rows: list[dict],
                                 id_map: dict[str, str],
                                 media_id_map: dict[str, str],
                                 ) -> None:
        for row in rows:
            character = Character.model_validate(row).model_copy(update={"id": str(uuid4())})
            location_id = id_map.get(row.get("location_id")) if row.get("location_id") else None
            landmark_id = id_map.get(row.get("landmark_id")) if row.get("landmark_id") else None

            created = await self._db.character.create_character(
                character, world_id, location_id=location_id, position=row.get("position"), landmark_id=landmark_id,
            )
            if not created:
                raise WorldImportError(f"Failed to import character {row['id']!r}")
            id_map[row["id"]] = created.id

            await self._maybe_set_cover(created.id, row, media_id_map)

    async def _import_background_characters(self,
                                            world_id: str,
                                            rows: list[dict],
                                            id_map: dict[str, str],
                                            media_id_map: dict[str, str],
                                            ) -> None:
        for row in rows:
            character = BackgroundCharacter.model_validate(row).model_copy(update={"id": str(uuid4())})
            location_id = id_map.get(row.get("location_id")) if row.get("location_id") else None
            landmark_id = id_map.get(row.get("landmark_id")) if row.get("landmark_id") else None

            created = await self._db.character.create_background_character(
                character, world_id, location_id=location_id, position=row.get("position"), landmark_id=landmark_id,
            )
            if not created:
                raise WorldImportError(f"Failed to import background character {row['id']!r}")
            id_map[row["id"]] = created.id

            await self._maybe_set_cover(created.id, row, media_id_map)

    async def _import_items(self,
                            world_id: str,
                            rows: list[dict],
                            id_map: dict[str, str],
                            media_id_map: dict[str, str],
                            ) -> None:
        for row in rows:
            item = Item.model_validate(row).model_copy(update={"id": str(uuid4())})
            created = await self._db.item.create_item(item, world_id)
            if not created:
                raise WorldImportError(f"Failed to import item {row['id']!r}")
            id_map[row["id"]] = created.id

            await self._maybe_set_cover(created.id, row, media_id_map)

    async def _import_containers(self,
                                 world_id: str,
                                 rows: list[dict],
                                 id_map: dict[str, str],
                                 media_id_map: dict[str, str],
                                 ) -> None:
        for row in rows:
            container = Container.model_validate(row).model_copy(update={"id": str(uuid4())})
            location_id = id_map.get(row.get("location_id")) if row.get("location_id") else None

            created = await self._db.container.create_container(
                container, world_id, location_id=location_id, position=row.get("position"),
            )
            if not created:
                raise WorldImportError(f"Failed to import container {row['id']!r}")
            id_map[row["id"]] = created.id

            await self._maybe_set_cover(created.id, row, media_id_map)

        for row in rows:
            new_id = id_map[row["id"]]
            holder_id = id_map.get(row.get("holder_id")) if row.get("holder_id") else None
            owner_id = id_map.get(row.get("owner_id")) if row.get("owner_id") else None
            if holder_id or owner_id:
                await self._db.container.assign_container(new_id, holder_id=holder_id, owner_id=owner_id)

            unlocking_item_ids = [
                id_map[item_id] for item_id in row.get("unlocking_item_ids", []) if item_id in id_map
            ]
            for item_id in unlocking_item_ids:
                await self._db.container.add_unlocking_item(item_id, new_id)

    async def _import_equipment(self,
                                world_id: str,
                                rows: list[dict],
                                id_map: dict[str, str],
                                media_id_map: dict[str, str],
                                ) -> None:
        for row in rows:
            equipment = Equipment.model_validate(row).model_copy(update={"id": str(uuid4())})
            location_id = id_map.get(row.get("location_id")) if row.get("location_id") else None

            created = await self._db.equipment.create_equipment(
                equipment, world_id, location_id=location_id, position=row.get("position"),
            )
            if not created:
                raise WorldImportError(f"Failed to import equipment {row['id']!r}")
            id_map[row["id"]] = created.id

            holder_id = id_map.get(row.get("holder_id")) if row.get("holder_id") else None
            if holder_id:
                await self._db.equipment.change_hold_state(
                    created.id, holder_id,
                    equipped=bool(row.get("equipped")),
                    equipped_position=row.get("equipped_position"),
                )
            owner_id = id_map.get(row.get("owner_id")) if row.get("owner_id") else None
            if owner_id:
                await self._db.equipment.change_owner(created.id, owner_id)

            await self._maybe_set_cover(created.id, row, media_id_map)

    async def _import_item_stacks(self, world_id: str, rows: list[dict], id_map: dict[str, str]) -> None:
        for row in rows:
            stack = ItemStack.model_validate(row).model_copy(update={"id": str(uuid4())})
            item_id = id_map.get(row.get("item_id"))
            if not item_id:
                raise WorldImportError(f"Item stack {row['id']!r} references an unknown item")

            location_id = id_map.get(row.get("location_id")) if row.get("location_id") else None
            holder_id = id_map.get(row.get("holder_id")) if row.get("holder_id") else None
            owner_id = id_map.get(row.get("owner_id")) if row.get("owner_id") else None

            created = await self._db.item.create_stack(
                item_id, stack,
                location_id=location_id, position=row.get("position"),
                source_id=world_id, holder_id=holder_id, owner_id=owner_id,
            )
            if not created:
                raise WorldImportError(f"Failed to import item stack {row['id']!r}")
            id_map[row["id"]] = created.id

    async def _maybe_set_cover(self, entity_id: str, row: dict, media_id_map: dict[str, str]) -> None:
        cover_id = media_id_map.get(row.get("cover_media_id"))
        if cover_id:
            await self._db.media.set_cover_image(entity_id, cover_id)

    # -- narrative ----------------------------------------------------------------------------

    async def _import_turns(self, world_id: str, rows: list[dict]) -> dict[str, str]:
        turn_id_map: dict[str, str] = {}
        previous_new_id: str | None = None

        for row in sorted(rows, key=lambda item: item["sequence"]):
            turn = Turn.model_validate(row).model_copy(update={"id": str(uuid4())})
            created = await self._db.turn.create_turn(turn, world_id, previous_turn_id=previous_new_id)
            turn_id_map[row["id"]] = created.id
            previous_new_id = created.id

        return turn_id_map

    async def _import_events(self,
                             rows: list[dict],
                             turn_id_map: dict[str, str],
                             id_map: dict[str, str],
                             ) -> dict[str, str]:
        event_id_map: dict[str, str] = {}

        for row in rows:
            event = Event.model_validate(row).model_copy(update={"id": str(uuid4())})
            new_turn_ids = [turn_id_map[tid] for tid in row.get("turn_ids", []) if tid in turn_id_map]
            if not new_turn_ids:
                raise WorldImportError(f"Event {row['id']!r} has no resolvable turns")

            created = await self._db.event.create_event(event, new_turn_ids)
            if not created:
                raise WorldImportError(f"Failed to import event {row['id']!r}")
            event_id_map[row["id"]] = created.id

            involvements = [
                {"character_id": id_map[inv["character_id"]], "involvement": inv["involvement"]}
                for inv in row.get("involved_characters", [])
                if inv["character_id"] in id_map
            ]
            if involvements:
                await self._db.event.replace_character_involvements(created.id, involvements)

        return event_id_map

    async def _import_memories(self,
                               rows: list[dict],
                               event_id_map: dict[str, str],
                               id_map: dict[str, str],
                               ) -> dict[str, str]:
        memory_id_map: dict[str, str] = {}

        for row in rows:
            memory = MemoryAtom.model_validate(row).model_copy(update={"id": str(uuid4())})
            event_id = event_id_map.get(row.get("event_id"))
            if not event_id:
                raise WorldImportError(f"Memory {row['id']!r} references an unknown event")

            character_links = [
                CharacterMemoryLink(
                    character_id=id_map[link["character_id"]],
                    confidence=link["confidence"],
                    salience=link["salience"],
                    behavioural_relevance=link.get("behavioural_relevance"),
                    stance=link["stance"],
                )
                for link in row.get("character_links", [])
                if link["character_id"] in id_map
            ]
            if not character_links:
                raise WorldImportError(f"Memory {row['id']!r} has no resolvable character links")

            created = await self._db.memory.create_memory_atom(
                memory, event_id=event_id, support_type=row["support_type"], character_links=character_links,
            )
            memory_id_map[row["id"]] = created.id

        return memory_id_map

    async def _import_intents(self,
                              rows: list[dict],
                              id_map: dict[str, str],
                              event_id_map: dict[str, str],
                              ) -> None:
        for row in rows:
            intent = Intent.model_validate(row).model_copy(update={"id": str(uuid4())})
            holder_id = id_map.get(row.get("character_id"))
            if not holder_id:
                raise WorldImportError(f"Intent {row['id']!r} references an unknown holder character")

            created = await self._db.intent.create_intent(intent, holder_id)
            if not created:
                raise WorldImportError(f"Failed to import intent {row['id']!r}")

            created_by = event_id_map.get(row.get("created_by_event_id"))
            if created_by:
                await self._db.intent.add_event_creation(created_by, created.id)

            contributed_by = [
                event_id_map[event_id] for event_id in row.get("contributed_by_event_ids", []) if event_id in event_id_map
            ]
            if contributed_by:
                await self._db.intent.replace_event_contributions(created.id, contributed_by)

    async def _import_relationships(self,
                                    world_id: str,
                                    rows: list[dict],
                                    id_map: dict[str, str],
                                    memory_id_map: dict[str, str],
                                    ) -> None:
        for row in rows:
            source_id = id_map.get(row["source"]["id"])
            target_id = id_map.get(row["target"]["id"])
            if not source_id or not target_id:
                continue

            perspective_id = None
            if row.get("perspective_character_id"):
                perspective_id = id_map.get(row["perspective_character_id"])
                if not perspective_id:
                    continue

            evidence_memory_ids = [
                memory_id_map[memory_id] for memory_id in row.get("evidence_memory_ids", []) if memory_id in memory_id_map
            ]

            relationship = EntityRelationship.model_validate({
                **row,
                "id": str(uuid4()),
                "scope_type": "world",
                "scope_id": world_id,
                "source": {**row["source"], "id": source_id},
                "target": {**row["target"], "id": target_id},
                "perspective_character_id": perspective_id,
                "evidence_memory_ids": evidence_memory_ids,
                "version": 1,
            })
            await self._db.entity_relationship.create_relationship(relationship)

    async def _import_entity_variable_sets(self,
                                           world_id: str,
                                           rows: list[dict],
                                           id_map: dict[str, str],
                                           ) -> None:
        """Optional: most entities have no tracked variables, so an empty/absent section is normal."""
        for row in rows:
            owner_id = id_map.get(row["owner_id"])
            if not owner_id:
                continue

            variable_set = EntityVariableSet.model_validate({
                **row,
                "id": str(uuid4()),
                "source_id": world_id,
                "owner_id": owner_id,
                "version": 1,
            })
            await self._db.variable.create_variable_set(variable_set)

    # -- configuration --------------------------------------------------------------------------

    async def _resolve_config(self,
                              config_dict: dict,
                              id_map: dict[str, str],
                              existing: list,
                              adapter: TypeAdapter,
                              create_fn,
                              ) -> str:
        original_id = config_dict["id"]
        if original_id in id_map:
            return id_map[original_id]

        candidate = adapter.validate_python(config_dict)
        match = next((other for other in existing if _configs_equal(other, candidate)), None)
        if match:
            id_map[original_id] = match.id
            return match.id

        created = await create_fn(candidate.model_copy(update={"id": str(uuid4())}))
        existing.append(created)
        id_map[original_id] = created.id
        return created.id

    async def _import_chat_assignments(self, world_id: str, rows: list[dict]) -> None:
        existing = await self._db.config.list_chats()
        id_map: dict[str, str] = {}
        for row in rows:
            new_id = await self._resolve_config(
                row["config"], id_map, existing, _ChatConfigAdapter, self._db.config.create_chat,
            )
            await self._db.config.link_chat(world_id, new_id, ComponentType(row["component"]))

    async def _import_embed_assignments(self, world_id: str, rows: list[dict]) -> None:
        existing = await self._db.config.list_embeds()
        id_map: dict[str, str] = {}
        for row in rows:
            new_id = await self._resolve_config(
                row["config"], id_map, existing, _EmbedConfigAdapter, self._db.config.create_embed,
            )
            await self._db.config.link_embed(world_id, new_id, ComponentType(row["component"]))

    async def _import_image_assignments(self, world_id: str, rows: list[dict]) -> None:
        existing = await self._db.config.list_images()
        id_map: dict[str, str] = {}
        for row in rows:
            new_id = await self._resolve_config(
                row["config"], id_map, existing, _ImageConfigAdapter, self._db.config.create_image,
            )
            await self._db.config.link_image(world_id, new_id, ComponentType(row["component"]))

    async def _import_tts_assignments(self, world_id: str, rows: list[dict]) -> dict[str, str]:
        existing = await self._db.config.list_ttss()
        id_map: dict[str, str] = {}
        for row in rows:
            new_id = await self._resolve_config(
                row["config"], id_map, existing, _TtsConfigAdapter, self._db.config.create_tts,
            )
            if row.get("component"):
                await self._db.config.link_tts(world_id, new_id, ComponentType(row["component"]))

        return id_map

    async def _import_character_tts_configs(self,
                                            character_rows: list[dict],
                                            id_map: dict[str, str],
                                            tts_id_map: dict[str, str],
                                            ) -> None:
        for row in character_rows:
            tts_config = row.get("tts_config")
            new_character_id = id_map.get(row["id"])
            if not tts_config or not new_character_id:
                continue

            config = CharacterTtsConfig(
                character_voice=tts_config.get("character_voice"),
                rvc_character_voice=tts_config.get("rvc_character_voice"),
                rvc_character_pitch=tts_config.get("rvc_character_pitch"),
            )
            await self._db.character_tts_config.set_character_tts_config(new_character_id, config)

            backend_new_id = tts_id_map.get(tts_config.get("backend_config_id"))
            if backend_new_id:
                await self._db.character_tts_config.link_character_tts_backend(new_character_id, backend_new_id)

    # -- prompts/workflows ----------------------------------------------------------------------

    async def _import_prompts(self, world_id: str, rows: list[dict], media_id_map: dict[str, str]) -> None:
        for row in rows:
            media_id = media_id_map.get(row.get("media_id"))
            if media_id:
                await self._db.media.set_prompt_media(world_id, media_id)

    async def _import_workflows(self, world_id: str, rows: list[dict], media_id_map: dict[str, str]) -> None:
        for row in rows:
            media_id = media_id_map.get(row.get("media_id"))
            if media_id:
                await self._db.media.set_workflow_media(world_id, media_id)
