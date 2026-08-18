import json
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, ContainerState, EventInvolvement, \
    IntentHorizon, IntentStatus, IntentType, MediaType, MemoryStance, MemorySupportType, Salience, \
    SupportedLanguage, TurnType
from world_simulation_engine.model import AllTalkXttsModelConfig, BackgroundCharacter, Character, \
    CharacterTtsConfig, Container, ConnectionConfig, CurrentActivity, EntityRelationship, EntityVariableSet, \
    Equipment, Event, GenericRelationshipDetails, Intent, Item, ItemStack, Landmark, Location, MediaFile, \
    MemoryAtom, OllamaChatModelConfig, OllamaEmbedModelConfig, PromptMediaFile, RelationshipEntityRef, \
    RelationshipScope, Turn, VariableDefinition
from world_simulation_engine.service import DatabaseService, StorageService, WorldExportService
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink
from integration_test.database_service.helpers import create_world


async def test_export_world_produces_complete_and_credential_free_archive(clean_neo4j, tmp_path):
    db = DatabaseService(clean_neo4j)
    storage = StorageService(tmp_path / "storage")
    await storage.initialise()

    world = await create_world(clean_neo4j)

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
        content="Alex arrives at the market.", start_time=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
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

    relationship = EntityRelationship(
        scope_type=RelationshipScope.WORLD,
        scope_id=world.id,
        source=RelationshipEntityRef(type="character", id=alex.id, name=alex.name),
        target=RelationshipEntityRef(type="character", id=blair.id, name=blair.name),
        label="knows",
        details=GenericRelationshipDetails(),
        evidence_memory_ids=[],
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

    exporter = WorldExportService(database=db, storage=storage)
    archive_bytes = await exporter.export_world(world.id)

    with ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())

        def read_json(name):
            return json.loads(archive.read(name))

        def read_jsonl(name):
            content = archive.read(name).decode("utf-8")
            return [json.loads(line) for line in content.splitlines() if line]

        assert "manifest.json" in names
        manifest = read_json("manifest.json")
        assert manifest["world_id"] == world.id
        assert manifest["spec"] == "wse_world"
        assert manifest["spec_version"] == "1.0"

        world_data = read_json("world.json")
        assert world_data["id"] == world.id
        assert world_data["name"] == world.name

        author_data = read_json("author.json")
        assert author_data["name"] == "Test Author"

        locations = {row["id"]: row for row in read_jsonl("data/locations.jsonl")}
        assert locations[market.id]["parent_location_id"] == city.id
        assert locations[city.id]["parent_location_id"] is None

        landmarks = {row["id"]: row for row in read_jsonl("data/landmarks.jsonl")}
        assert landmarks[landmark.id]["name"] == "Fountain"

        characters = {row["id"]: row for row in read_jsonl("data/characters.jsonl")}
        alex_row = characters[alex.id]
        assert alex_row["location_id"] == market.id
        assert alex_row["position"] == "near the stalls"
        assert alex_row["landmark_id"] == landmark.id
        assert alex_row["tts_config"]["character_voice"] == "female_01.wav"
        assert alex_row["tts_config"]["backend_config_id"] == tts_backend.id
        assert alex_row["tts_config"]["backend"]["connection"] is None
        assert characters[blair.id]["tts_config"] is None
        assert alex_row["cover_media_id"] is None

        background_rows = {row["id"]: row for row in read_jsonl("data/background_characters.jsonl")}
        assert background_rows[background.id]["location_id"] == market.id
        assert background_rows[background.id]["landmark_id"] == landmark.id

        items = {row["id"]: row for row in read_jsonl("data/items.jsonl")}
        assert set(items.keys()) == {item.id, key_item.id}

        stacks = {row["id"]: row for row in read_jsonl("data/item_stacks.jsonl")}
        assert stacks[stack.id]["item_id"] == item.id
        assert stacks[stack.id]["holder_id"] == alex.id
        assert stacks[stack.id]["owner_id"] == alex.id
        assert stacks[contained_stack.id]["holder_id"] == container.id

        equipment_rows = {row["id"]: row for row in read_jsonl("data/equipment.jsonl")}
        assert equipment_rows[equipment.id]["owner_id"] == alex.id

        container_rows = {row["id"]: row for row in read_jsonl("data/containers.jsonl")}
        container_row = container_rows[container.id]
        assert container_row["held_stack_ids"] == [contained_stack.id]
        assert container_row["unlocking_item_ids"] == [key_item.id]
        assert container_row["location_id"] == market.id

        turns = {row["id"]: row for row in read_jsonl("data/turns.jsonl")}
        assert turns[turn.id]["content"] == "Alex arrives at the market."

        events = {row["id"]: row for row in read_jsonl("data/events.jsonl")}
        event_row = events[event.id]
        assert event_row["turn_ids"] == [turn.id]
        assert event_row["involved_characters"] == [{"character_id": alex.id, "involvement": "participate"}]

        memories = {row["id"]: row for row in read_jsonl("data/memories.jsonl")}
        memory_row = memories[memory.id]
        assert memory_row["event_id"] == event.id
        assert memory_row["character_links"][0]["character_id"] == alex.id

        intents = {row["id"]: row for row in read_jsonl("data/intents.jsonl")}
        assert intents[intent.id]["created_by_event_id"] == event.id

        relationships = read_jsonl("data/entity_relationships.jsonl")
        assert any(row["label"] == "knows" for row in relationships)

        variable_sets = read_jsonl("data/entity_variable_sets.jsonl")
        assert len(variable_sets) == 1
        assert variable_sets[0]["owner_id"] == alex.id
        assert variable_sets[0]["variables"][0]["name"] == "health"
        assert variable_sets[0]["variables"][0]["value"] == 80

        chat_rows = read_jsonl("configs/chat.jsonl")
        assert len(chat_rows) == 1
        assert chat_rows[0]["component"] == "narrator"
        assert chat_rows[0]["config"]["connection"] is None
        assert chat_rows[0]["config"]["model"] == "llama3.1"

        embed_rows = read_jsonl("configs/embed.jsonl")
        assert embed_rows[0]["config"]["connection"] is None

        tts_rows = read_jsonl("configs/tts.jsonl")
        assert len(tts_rows) == 1
        assert tts_rows[0]["config"]["connection"] is None
        assert tts_rows[0]["config"]["id"] == tts_backend.id

        prompt_rows = read_jsonl("prompts.jsonl")
        assert prompt_rows[0]["prompt_name"] == "narrate_resolved_turn_prompt"
        assert prompt_rows[0]["component"] == "narrator"

        media_manifest = {row["id"]: row for row in read_jsonl("media/manifest.jsonl")}
        assert cover_media.id in media_manifest
        assert prompt_media.id in media_manifest
        assert archive.read(media_manifest[cover_media.id]["file"]) == cover_content
        assert archive.read(media_manifest[prompt_media.id]["file"]) == prompt_content

        # No credential-bearing text anywhere in the archive.
        for name in names:
            if name.startswith("media/files/"):
                continue
            assert b"super-secret-key" not in archive.read(name)
            assert b"internal-host" not in archive.read(name)
