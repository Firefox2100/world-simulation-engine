import json
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, ContainerState, EventInvolvement, \
    IntentHorizon, IntentStatus, IntentType, MemoryStance, MemorySupportType, Salience, SupportedLanguage, TurnType
from world_simulation_engine.model import AllTalkXttsModelConfig, Author, BackgroundCharacter, Character, \
    CharacterTtsConfig, Container, ConnectionConfig, CurrentActivity, EntityRelationship, EntityVariableSet, \
    Equipment, Event, GenericRelationshipDetails, Intent, Item, ItemStack, Landmark, Location, MediaFile, \
    MemoryAtom, OllamaChatModelConfig, OllamaEmbedModelConfig, PromptMediaFile, RelationshipEntityRef, \
    RelationshipScope, Turn, VariableDefinition
from world_simulation_engine.misc.enums import MediaType
from world_simulation_engine.service import AuthorNotFoundError, DatabaseService, StorageService, \
    WorldExportService, WorldImportError, WorldImportService
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink
from integration_test.database_service.helpers import create_world


async def _build_rich_world(db: DatabaseService, storage: StorageService, driver):
    world = await create_world(driver)

    city = Location(id=str(uuid4()), name="City", description="A city")
    market = Location(id=str(uuid4()), name="Market", description="A market")
    await db.location.create_location(city, source_id=world.id)
    await db.location.create_location(market, source_id=world.id, contained_in=city.id)
    landmark = Landmark(id=str(uuid4()), name="Fountain", description="A fountain")
    await db.location.create_landmark(landmark, market.id)

    alex = Character(
        id=str(uuid4()), user_controlled=True, name="Alex", age=30, gender="non-binary",
        appearance="Plain clothes", description="A test character", public_state="Idle",
        private_state="Idle", current_activity=CurrentActivity(name="idle"),
    )
    blair = Character(
        id=str(uuid4()), user_controlled=False, name="Blair", age=28, gender="woman",
        appearance="Neat clothes", description="Another test character", public_state="Idle",
        private_state="Idle", current_activity=CurrentActivity(name="idle"),
    )
    await db.character.create_character(alex, world.id)
    await db.character.create_character(blair, world.id)
    await db.character.move_to_location(alex.id, market.id, position="near the stalls")
    await db.character.anchor_to_landmark(alex.id, landmark.id)

    background = BackgroundCharacter(id=str(uuid4()), name="Shopkeeper", description="A busy shopkeeper")
    await db.character.create_background_character(
        background, world.id, location_id=market.id, position="behind the counter", landmark_id=landmark.id,
    )

    item = Item(id=str(uuid4()), name="Apple", description="A crisp apple", unique=False)
    await db.item.create_item(item, world.id)
    stack = ItemStack(id=str(uuid4()), quantity=3, quality="fresh")
    await db.item.create_stack(item.id, stack, source_id=world.id, holder_id=alex.id, owner_id=alex.id)

    equipment = Equipment(id=str(uuid4()), name="Lantern", description="A brass lantern", quality="worn")
    await db.equipment.create_equipment(equipment, world.id)
    await db.equipment.change_owner(equipment.id, alex.id)
    await db.equipment.change_hold_state(equipment.id, alex.id, equipped=True, equipped_position="belt")

    key_item = Item(id=str(uuid4()), name="Key", description="A brass key", unique=True)
    await db.item.create_item(key_item, world.id)
    container = Container(
        id=str(uuid4()), name="Chest", description="A wooden chest", state=ContainerState.UNLOCKED,
    )
    await db.container.create_container(container, world.id, location_id=market.id, position="in the corner")
    contained_stack = ItemStack(id=str(uuid4()), quantity=1, quality="boxed")
    await db.item.create_stack(item.id, contained_stack, source_id=world.id, location_id=market.id)
    await db.container.put_stack_in_container(contained_stack.id, container.id)
    await db.container.add_unlocking_item(key_item.id, container.id)

    turn = Turn(
        id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE,
        content=json.dumps({"blocks": [
            {"type": "speech", "character_id": alex.id, "character_name": "Alex", "text": "I'm here."},
        ]}),
        start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    await db.turn.create_turn(turn, world.id)
    event = Event(id=str(uuid4()), name="Arrival", summary="Alex arrives at the market.")
    await db.event.create_event(event, [turn.id])
    await db.event.add_character_involvement(event.id, alex.id, EventInvolvement.PARTICIPATE)

    memory = MemoryAtom(id=str(uuid4()), summary="Alex was here.", keywords=["arrival"], embedding=None)
    await db.memory.create_memory_atom(
        memory,
        event_id=event.id,
        support_type=MemorySupportType.DIRECT,
        character_links=[
            CharacterMemoryLink(
                character_id=alex.id, confidence=0.9, salience=Salience.MEDIUM, stance=MemoryStance.REMEMBER,
            ),
        ],
    )

    intent = Intent(
        id=str(uuid4()), type=IntentType.QUEST, name="Find supplies", description="Alex wants supplies.",
        keywords=["supplies"], embedding=None, priority=0.5, urgency=0.5, status=IntentStatus.ACTIVE,
        horizon=IntentHorizon.SHORT,
    )
    await db.intent.create_intent(intent, alex.id)
    await db.intent.add_event_creation(event.id, intent.id)

    relationship_evidence_memory = memory
    relationship = EntityRelationship(
        scope_type=RelationshipScope.WORLD,
        scope_id=world.id,
        source=RelationshipEntityRef(type="character", id=alex.id, name=alex.name),
        target=RelationshipEntityRef(type="character", id=blair.id, name=blair.name),
        label="knows",
        details=GenericRelationshipDetails(),
        evidence_memory_ids=[relationship_evidence_memory.id],
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        last_changed_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    await db.entity_relationship.create_relationship(relationship)

    variable_set = EntityVariableSet(
        source_id=world.id,
        owner_type="character",
        owner_id=alex.id,
        variables=[
            VariableDefinition(
                name="health", value_type="integer", value=80, default_value=100,
                description="Hit points.", minimum=0, maximum=100,
            ),
        ],
        last_updated_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    await db.variable.create_variable_set(variable_set)

    connection = ConnectionConfig(
        id=str(uuid4()), type=ConnectionType.OLLAMA, name="Local Ollama",
        base_url="http://internal-host:11434", api_key="super-secret-key",
    )
    await db.config.create_connection(connection)
    chat_config = OllamaChatModelConfig(id=str(uuid4()), name="Narrator Chat", model="llama3.1")
    await db.config.create_chat(chat_config)
    await db.config.link_connection(chat_config.id, connection.id)
    await db.config.link_chat(world.id, chat_config.id, ComponentType.NARRATOR)

    embed_config = OllamaEmbedModelConfig(id=str(uuid4()), model="nomic-embed-text")
    await db.config.create_embed(embed_config)
    await db.config.link_embed(world.id, embed_config.id, ComponentType.CHARACTER_SIMULATOR)

    tts_connection = ConnectionConfig(
        id=str(uuid4()), type=ConnectionType.ALLTALK, name="Local AllTalk",
        base_url="http://internal-host:7851", api_key=None,
    )
    await db.config.create_connection(tts_connection)
    tts_backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en", temperature=0.75)
    await db.config.create_tts(tts_backend)
    await db.config.link_connection(tts_backend.id, tts_connection.id)
    await db.character_tts_config.set_character_tts_config(
        alex.id, CharacterTtsConfig(character_voice="female_01.wav"),
    )
    await db.character_tts_config.link_character_tts_backend(alex.id, tts_backend.id)

    prompt_content = json.dumps([{"role": "system", "content": "You are a narrator."}]).encode("utf-8")
    prompt_stored = await storage.save_bytes(prompt_content)
    prompt_media = PromptMediaFile(
        id=str(uuid4()), title="Narrator prompt", hash=prompt_stored.digest, filename="narrator-prompt",
        prompt_name="narrate_resolved_turn_prompt", language=SupportedLanguage.ENGLISH,
        component=ComponentType.NARRATOR,
    )
    await db.media.create_media(prompt_media)
    await db.media.set_prompt_media(world.id, prompt_media.id)

    cover_content = b"fake-png-bytes-for-world-cover"
    cover_stored = await storage.save_bytes(cover_content)
    cover_media = MediaFile(
        id=str(uuid4()), type=MediaType.PNG, title="World cover", hash=cover_stored.digest, filename="world-cover",
    )
    await db.media.create_media(cover_media)
    await db.media.set_cover_image(world.id, cover_media.id)
    await db.media.set_cover_image(alex.id, cover_media.id)

    return {
        "world": world,
        "alex": alex,
        "blair": blair,
        "market": market,
        "landmark": landmark,
        "container": container,
        "key_item": key_item,
        "equipment": equipment,
        "tts_backend": tts_backend,
    }


async def test_import_world_recreates_full_content(clean_neo4j, tmp_path):
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    built = await _build_rich_world(db, storage, clean_neo4j)
    source_world = built["world"]

    archive_bytes = await WorldExportService(database=db, storage=storage).export_world(source_world.id)

    import_author = Author(id=str(uuid4()), name="Import Author")
    await db.world.create_author(import_author)

    imported_world = await WorldImportService(database=db, storage=storage).import_world(
        archive_bytes, import_author.id,
    )

    assert imported_world.id != source_world.id
    assert imported_world.name == source_world.name
    assert imported_world.language == source_world.language

    imported_author = await db.world.get_author_by_world(imported_world.id)
    assert imported_author.id == import_author.id

    locations = await db.location.list_locations(world_id=imported_world.id)
    assert {location.name for location in locations} == {"City", "Market"}
    parent_map = await db.location.get_parent_map(imported_world.id)
    market_copy = next(location for location in locations if location.name == "Market")
    city_copy = next(location for location in locations if location.name == "City")
    assert parent_map[market_copy.id] == city_copy.id

    landmarks = await db.location.list_landmarks(world_id=imported_world.id)
    assert len(landmarks) == 1
    landmark_location_map = await db.location.get_landmark_location_map(imported_world.id)
    assert landmark_location_map[landmarks[0].id] == market_copy.id

    characters = await db.character.list_characters(world_id=imported_world.id)
    assert {character.name for character in characters} == {"Alex", "Blair"}
    alex_copy = next(character for character in characters if character.name == "Alex")
    blair_copy = next(character for character in characters if character.name == "Blair")

    position_map = await db.character.get_position_map(imported_world.id)
    assert position_map[alex_copy.id]["location_id"] == market_copy.id
    assert position_map[alex_copy.id]["position"] == "near the stalls"
    assert position_map[alex_copy.id]["landmark_id"] == landmarks[0].id

    background_characters = await db.character.list_background_characters(world_id=imported_world.id)
    assert len(background_characters) == 1

    tts_config = await db.character_tts_config.get_character_tts_config(alex_copy.id)
    assert tts_config.character_voice == "female_01.wav"
    assert tts_config.backend is not None
    assert tts_config.backend.language == "en"
    # The source world's own tts_backend already exists in this same database (with its real
    # connection attached), so config dedup should reuse that exact node rather than creating a
    # connection-less duplicate.
    assert tts_config.backend.id == built["tts_backend"].id
    assert tts_config.backend.connection is not None

    equipment_list = await db.equipment.list_equipment(world_id=imported_world.id)
    lantern = next(item for item in equipment_list if item.name == "Lantern")
    assert lantern.owner_id == alex_copy.id
    assert lantern.holder_id == alex_copy.id
    equipment_inventory = await db.equipment.get_equipment_inventory(alex_copy.id)
    lantern_inventory = next(item for item in equipment_inventory if item.name == "Lantern")
    assert lantern_inventory.equipped is True
    assert lantern_inventory.equipped_position == "belt"

    items = await db.item.list_items(world_id=imported_world.id)
    assert {item.name for item in items} == {"Apple", "Key"}
    apple_copy = next(item for item in items if item.name == "Apple")
    key_copy = next(item for item in items if item.name == "Key")

    stacks = await db.item.list_stacks(world_id=imported_world.id)
    alex_stack = next(stack for stack in stacks if stack.holder_id == alex_copy.id)
    assert alex_stack.item.id == apple_copy.id
    assert alex_stack.quantity == 3

    containers = await db.container.list_containers(world_id=imported_world.id)
    assert len(containers) == 1
    chest_copy = containers[0]
    assert chest_copy.location_id == market_copy.id
    held_stacks = await db.container.get_held_stacks(chest_copy.id)
    assert len(held_stacks) == 1
    unlocking_items = await db.container.get_unlocking_items(chest_copy.id)
    assert unlocking_items[0].id == key_copy.id

    turns = await db.turn.list_turns(source_id=imported_world.id, limit=100)
    assert len(turns) == 1
    # The turn's serialized NarrationProposal content embeds a SpeechBlock.character_id that must
    # be rewritten from the source world's character id to the freshly imported copy's id.
    turn_content = json.loads(turns[0].content)
    assert turn_content["blocks"][0]["character_id"] == alex_copy.id
    assert turn_content["blocks"][0]["character_id"] != built["alex"].id
    events = await db.event.list_events(turn_id=turns[0].id)
    assert len(events) == 1
    memories = await db.memory.list_memories(event_id=events[0].id)
    assert len(memories) == 1

    intents = await db.intent.list_intents(character_id=alex_copy.id)
    assert len(intents) == 1
    intent_links = await db.intent.get_event_links([intents[0].id])
    assert intent_links[intents[0].id]["created_by_event_id"] == events[0].id

    relationships = await db.entity_relationship.list_relationships(scope_id=imported_world.id, active_only=False)
    assert len(relationships) == 1
    relationship_copy = relationships[0]
    assert relationship_copy.source.id == alex_copy.id
    assert relationship_copy.target.id == blair_copy.id
    assert relationship_copy.evidence_memory_ids == [memories[0].id]

    variable_set_copy = await db.variable.get_variable_set(alex_copy.id)
    assert variable_set_copy is not None
    assert variable_set_copy.source_id == imported_world.id
    assert variable_set_copy.variables[0].name == "health"
    assert variable_set_copy.variables[0].value == 80
    assert await db.variable.get_variable_set(blair_copy.id) is None

    chat_assignments = await db.config.list_chats_by_source(imported_world.id)
    assert chat_assignments[ComponentType.NARRATOR].model == "llama3.1"
    # Same reuse rationale as the tts backend above: the source chat config already exists in this
    # database, so dedup reuses it (real connection and all) instead of creating a duplicate.
    assert chat_assignments[ComponentType.NARRATOR].connection is not None

    embed_assignments = await db.config.list_embeds_by_source(imported_world.id)
    assert embed_assignments[ComponentType.CHARACTER_SIMULATOR].model == "nomic-embed-text"

    world_cover = await db.media.get_cover_image(imported_world.id)
    assert world_cover is not None
    alex_cover = await db.media.get_cover_image(alex_copy.id)
    assert alex_cover.id == world_cover.id

    prompt_media = await db.media.get_source_prompt_media(
        imported_world.id, SupportedLanguage.ENGLISH, "narrate_resolved_turn_prompt", ComponentType.NARRATOR,
    )
    assert prompt_media is not None


async def test_import_succeeds_for_archives_predating_entity_variable_sets(clean_neo4j, tmp_path):
    """Older archives simply don't have data/entity_variable_sets.jsonl - import must not treat a
    missing optional section as a corrupt archive, since most worlds have no tracked variables
    anyway."""
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    built = await _build_rich_world(db, storage, clean_neo4j)
    archive_bytes = await WorldExportService(database=db, storage=storage).export_world(built["world"].id)

    with ZipFile(BytesIO(archive_bytes)) as original:
        legacy_buffer = BytesIO()
        with ZipFile(legacy_buffer, mode="w", compression=ZIP_DEFLATED) as legacy:
            for name in original.namelist():
                if name == "data/entity_variable_sets.jsonl":
                    continue
                legacy.writestr(name, original.read(name))

    author = Author(id=str(uuid4()), name="Legacy Archive Author")
    await db.world.create_author(author)

    imported_world = await WorldImportService(database=db, storage=storage).import_world(
        legacy_buffer.getvalue(), author.id,
    )

    characters = await db.character.list_characters(world_id=imported_world.id)
    alex_copy = next(character for character in characters if character.name == "Alex")
    assert await db.variable.get_variable_set(alex_copy.id) is None


async def test_import_deduplicates_configs_and_media_on_repeat_import(clean_neo4j, tmp_path):
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    built = await _build_rich_world(db, storage, clean_neo4j)
    archive_bytes = await WorldExportService(database=db, storage=storage).export_world(built["world"].id)

    author = Author(id=str(uuid4()), name="Repeat Import Author")
    await db.world.create_author(author)

    service = WorldImportService(database=db, storage=storage)
    first_world = await service.import_world(archive_bytes, author.id)

    chats_after_first = await db.config.list_chats()
    embeds_after_first = await db.config.list_embeds()
    ttss_after_first = await db.config.list_ttss()
    media_after_first = await db.media.list_media()

    second_world = await service.import_world(archive_bytes, author.id)

    assert second_world.id != first_world.id

    chats_after_second = await db.config.list_chats()
    embeds_after_second = await db.config.list_embeds()
    ttss_after_second = await db.config.list_ttss()
    media_after_second = await db.media.list_media()

    assert len(chats_after_second) == len(chats_after_first)
    assert len(embeds_after_second) == len(embeds_after_first)
    assert len(ttss_after_second) == len(ttss_after_first)
    assert len(media_after_second) == len(media_after_first)

    first_chat_assignments = await db.config.list_chats_by_source(first_world.id)
    second_chat_assignments = await db.config.list_chats_by_source(second_world.id)
    assert first_chat_assignments[ComponentType.NARRATOR].id == second_chat_assignments[ComponentType.NARRATOR].id


async def test_import_rejects_invalid_zip(clean_neo4j, tmp_path):
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    author = Author(id=str(uuid4()), name="Bad Zip Author")
    await db.world.create_author(author)

    service = WorldImportService(database=db, storage=storage)

    with pytest.raises(WorldImportError):
        await service.import_world(b"not a zip file", author.id)


async def test_import_rejects_wrong_format_version(clean_neo4j, tmp_path):
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    author = Author(id=str(uuid4()), name="Bad Version Author")
    await db.world.create_author(author)

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"spec": "wse_world", "spec_version": "999.0"}))

    service = WorldImportService(database=db, storage=storage)

    with pytest.raises(WorldImportError):
        await service.import_world(buffer.getvalue(), author.id)


async def test_import_raises_for_missing_author(clean_neo4j, tmp_path):
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    built = await _build_rich_world(db, storage, clean_neo4j)
    archive_bytes = await WorldExportService(database=db, storage=storage).export_world(built["world"].id)

    service = WorldImportService(database=db, storage=storage)

    with pytest.raises(AuthorNotFoundError):
        await service.import_world(archive_bytes, str(uuid4()))


async def test_import_assembled_sections_persists_a_full_world_without_a_zip_archive(clean_neo4j, tmp_path):
    """The SillyTavern import pipeline's `WorldAssembler` produces exactly this `world`/`sections`
    shape (§7 of SILLYTAVERN_IMPORT_PLAN.md) - this exercises the shared persistence path it uses,
    with no zip archive involved at all."""
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    author = Author(id=str(uuid4()), name="ST Import Author")
    await db.world.create_author(author)

    now = datetime.now(UTC).isoformat()
    world_row = {
        "name": "Imported World", "description": "A coastal town.",
        "starting_time": now, "language": "en",
    }
    sections = {
        "locations": [
            {"id": "loc-1", "name": "City", "description": "A city.", "parent_location_id": None},
            {"id": "loc-2", "name": "House", "description": "A house.", "parent_location_id": "loc-1"},
        ],
        "landmarks": [],
        "characters": [{
            "id": "char-1", "user_controlled": False, "name": "Example", "age": 21, "gender": "female",
            "appearance": "Plain", "description": "A fictional resident.", "public_state": "Present",
            "private_state": "Thinking",
            "current_activity": {
                "name": "idle", "started_at": None, "expected_end": None,
                "interruptible": True, "constraints": [],
            },
            "speech_style": "playful",
        }],
        "background_characters": [{"id": "bg-1", "name": "The Guard", "description": "Stands watch at the gate."}],
        "items": [], "item_stacks": [], "equipment": [], "containers": [],
        "turns": [{
            "id": "turn-1", "sequence": 0, "type": "system_response",
            "content": json.dumps({"blocks": [
                {"type": "speech", "character_id": "char-1", "character_name": "Example", "text": "Hi!"},
            ]}),
            "start_time": now,
        }],
        "events": [{
            "id": "evt-1", "name": "The Project", "summary": "They collaborated.", "turn_ids": ["turn-1"],
            "involved_characters": [{"character_id": "char-1", "involvement": "participate"}],
        }],
        "memories": [{
            "id": "mem-1", "summary": "We collaborated.", "keywords": ["project"], "embedding": None,
            "event_id": "evt-1", "support_type": "direct",
            "character_links": [{
                "character_id": "char-1", "confidence": 1.0, "salience": "medium",
                "stance": "remember", "behavioural_relevance": None,
            }],
        }],
        "intents": [{
            "id": "int-1", "type": "quest", "name": "Complete review", "description": "Complete the review.",
            "keywords": [], "embedding": None, "priority": 0.9, "urgency": 0.5, "status": "active",
            "desired_state": None, "success_conditions": [], "failure_conditions": [],
            "maintenance_conditions": [], "deadline": None, "horizon": "long", "constraints": [],
            "current_plan": [], "next_action_biases": [], "blockers": [], "open_threads": [],
            "character_id": "char-1", "created_by_event_id": None, "contributed_by_event_ids": [],
        }],
        "entity_relationships": [{
            "label": "colleagues", "public_description": "Former colleagues.", "private_description": None,
            "visibility": "objective", "perspective_character_id": None, "confidence": 1.0,
            "details": {"kind": "generic", "attributes": {}}, "evidence_memory_ids": [],
            "source": {"type": "character", "id": "char-1", "name": None},
            "target": {"type": "background_character", "id": "bg-1", "name": None},
            "created_at": now, "last_changed_at": now, "version": 1, "active": True,
        }],
        "entity_variable_sets": [{
            "owner_type": "character", "owner_id": "char-1",
            "variables": [{
                "name": "hp", "value_type": "integer", "value": 100, "default_value": 100,
                "description": "Health.", "minimum": 0, "maximum": 100, "allowed_values": [],
            }],
            "last_updated_at": now,
        }],
        "chat_configs": [], "embed_configs": [], "image_configs": [], "tts_configs": [],
        "prompts": [], "workflows": [], "media": [],
    }

    world = await WorldImportService(database=db, storage=storage).import_assembled_sections(
        world_row, sections, author.id,
    )

    assert world.name == "Imported World"
    assert world.description == "A coastal town."

    locations = await db.location.list_locations(world_id=world.id)
    assert {location.name for location in locations} == {"City", "House"}
    parent_map = await db.location.get_parent_map(world.id)
    house = next(location for location in locations if location.name == "House")
    city = next(location for location in locations if location.name == "City")
    assert parent_map[house.id] == city.id

    characters = await db.character.list_characters(world_id=world.id)
    assert [character.name for character in characters] == ["Example"]
    example = characters[0]

    background_characters = await db.character.list_background_characters(world_id=world.id)
    assert [character.name for character in background_characters] == ["The Guard"]
    guard = background_characters[0]

    events = await db.event.list_events(character_id=example.id)
    assert [event.name for event in events] == ["The Project"]

    memories = await db.memory.list_memories(character_id=example.id)
    assert [memory.summary for memory in memories] == ["We collaborated."]

    intents = await db.intent.list_intents(character_id=example.id)
    assert [intent.name for intent in intents] == ["Complete review"]

    relationships = await db.entity_relationship.list_relationships(scope_id=world.id, active_only=False)
    assert len(relationships) == 1
    assert relationships[0].source.id == example.id
    assert relationships[0].target.id == guard.id

    variable_set = await db.variable.get_variable_set(example.id)
    assert variable_set is not None
    assert variable_set.variables[0].name == "hp"
    assert variable_set.variables[0].value == 100

    # The turn's serialized NarrationProposal content embeds a SpeechBlock.character_id that was
    # assigned by the SillyTavern extraction pipeline ("char-1") before any real Character row
    # existed - it must be rewritten to the freshly created character's real id, or the turn's
    # speaker avatar/lookup can never resolve again (see turn_content_remap.py).
    turns = await db.turn.list_turns(source_id=world.id, limit=10)
    assert len(turns) == 1
    turn_content = json.loads(turns[0].content)
    assert turn_content["blocks"][0]["character_id"] == example.id
    assert turn_content["blocks"][0]["character_id"] != "char-1"
