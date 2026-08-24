from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

from world_simulation_engine.misc.enums import ContainerState, WorldStateCheckpointType
from world_simulation_engine.model import BackgroundCharacter, Character, Container, CurrentActivity, \
    EntityRelationship, Equipment, RelationshipEntityRef, Turn, WorldStateCheckpoint
from world_simulation_engine.service.simulation_state_checkpoint_service import SimulationStateCheckpointService


def make_character(**overrides) -> Character:
    defaults = dict(
        id="character_1",
        name="Alex",
        age=30,
        gender="unknown",
        appearance="Plain",
        description="A character",
        public_state="Standing",
        private_state="Focused",
        current_activity=CurrentActivity(name="idle"),
    )
    defaults.update(overrides)
    return Character(**defaults)


def make_database() -> Mock:
    database = Mock()
    database.character.list_characters = AsyncMock(return_value=[])
    database.character.list_background_characters = AsyncMock(return_value=[])
    database.character.get_position_map = AsyncMock(return_value={})
    database.character.get_background_position_map = AsyncMock(return_value={})
    database.item.list_items = AsyncMock(return_value=[])
    database.item.list_stacks = AsyncMock(return_value=[])
    database.equipment.list_equipment = AsyncMock(return_value=[])
    database.equipment.get_hold_types = AsyncMock(return_value={})
    database.container.list_containers = AsyncMock(return_value=[])
    database.container.get_unlocking_items = AsyncMock(return_value=[])
    database.variable.list_variable_sets_by_source = AsyncMock(return_value=[])
    database.entity_relationship.list_relationships = AsyncMock(return_value=[])
    database.emotion.get_state = AsyncMock(return_value=None)
    database.subjective_entity_claim.list_claims = AsyncMock(return_value=[])
    database.memory.list_memories = AsyncMock(return_value=[])
    database.memory.get_event_links = AsyncMock(return_value={})
    database.memory.get_character_links = AsyncMock(return_value={})
    database.event.list_events = AsyncMock(return_value=[])
    database.event.get_turn_links = AsyncMock(return_value={})
    database.event.get_character_involvements = AsyncMock(return_value={})
    database.world_state_checkpoint.save_checkpoint = AsyncMock(side_effect=lambda checkpoint: checkpoint)
    database.turn.delete_turns_after = AsyncMock(return_value=0)
    return database


def make_checkpoint(**overrides) -> WorldStateCheckpoint:
    defaults = dict(
        simulation_id="simulation_1",
        type=WorldStateCheckpointType.AFTER_USER_INPUT,
        turn_id="turn_1",
        turn_sequence=1,
    )
    defaults.update(overrides)
    return WorldStateCheckpoint(**defaults)


# ---------------------------------------------------------------------- capture


async def test_capture_merges_position_map_into_captured_characters():
    database = make_database()
    character = make_character()
    database.character.list_characters = AsyncMock(return_value=[character])
    database.character.get_position_map = AsyncMock(
        return_value={"character_1": {"location_id": "location_1", "position": "by the door", "landmark_id": None}}
    )
    service = SimulationStateCheckpointService(database=database)

    checkpoint = await service.capture(
        simulation_id="simulation_1",
        type=WorldStateCheckpointType.AFTER_USER_INPUT,
        turn=Turn(id="turn_1", sequence=1, type="user_input", content="", start_time=datetime(2026, 1, 1, tzinfo=UTC)),
    )

    assert len(checkpoint.characters) == 1
    entry = checkpoint.characters[0]
    assert entry["entity"]["id"] == "character_1"
    assert entry["location_id"] == "location_1"
    assert entry["position"] == "by the door"
    database.world_state_checkpoint.save_checkpoint.assert_awaited_once()


async def test_capture_merges_hold_type_into_captured_equipment():
    database = make_database()
    equipment = Equipment(id="equipment_1", name="Sword", description="A blade", holder_id="character_1")
    database.equipment.list_equipment = AsyncMock(return_value=[equipment])
    database.equipment.get_hold_types = AsyncMock(
        return_value={"equipment_1": {"equipped": True, "equipped_position": "back"}}
    )
    service = SimulationStateCheckpointService(database=database)

    checkpoint = await service.capture(simulation_id="simulation_1", type=WorldStateCheckpointType.AFTER_USER_INPUT, turn=None)

    entry = checkpoint.equipment[0]
    assert entry["equipped"] is True
    assert entry["equipped_position"] == "back"


async def test_capture_iterates_per_character_for_emotion_and_claims():
    database = make_database()
    database.character.list_characters = AsyncMock(return_value=[make_character(id="character_1"), make_character(id="character_2")])
    database.emotion.get_state = AsyncMock(return_value=None)
    database.subjective_entity_claim.list_claims = AsyncMock(return_value=[])
    service = SimulationStateCheckpointService(database=database)

    await service.capture(simulation_id="simulation_1", type=WorldStateCheckpointType.AFTER_USER_INPUT, turn=None)

    assert database.emotion.get_state.await_count == 2
    assert database.subjective_entity_claim.list_claims.await_count == 2


async def test_capture_omits_turn_boundary_when_no_turn_supplied():
    database = make_database()
    service = SimulationStateCheckpointService(database=database)

    checkpoint = await service.capture(
        simulation_id="simulation_1", type=WorldStateCheckpointType.BEFORE_OOC_MUTATION, turn=None,
    )

    assert checkpoint.turn_id is None
    assert checkpoint.turn_sequence is None


# ---------------------------------------------------------------------- restore


async def test_restore_deletes_turns_after_the_checkpoint_boundary_first():
    database = make_database()
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(turn_sequence=41)

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.turn.delete_turns_after.assert_awaited_once_with("simulation_1", 41)


async def test_restore_overwrites_existing_character_and_rehomes_location():
    database = make_database()
    character = make_character()
    database.character.overwrite_character = AsyncMock(return_value=character)
    database.character.create_character = AsyncMock()
    database.character.move_to_location = AsyncMock()
    database.character.remove_character_landmark = AsyncMock()
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(characters=[
        {"entity": character.model_dump(mode="json"), "location_id": "location_1", "position": "near the door"},
    ])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.character.create_character.assert_not_awaited()
    database.character.overwrite_character.assert_awaited_once()
    database.character.move_to_location.assert_awaited_once_with("character_1", "location_1", "near the door")
    database.character.remove_character_landmark.assert_awaited_once_with("character_1")


async def test_restore_creates_character_when_overwrite_finds_nothing_to_update():
    database = make_database()
    character = make_character()
    database.character.overwrite_character = AsyncMock(return_value=None)
    database.character.create_character = AsyncMock(return_value=character)
    database.character.move_to_location = AsyncMock()
    database.character.remove_character_landmark = AsyncMock()
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(characters=[
        {"entity": character.model_dump(mode="json"), "location_id": "location_1", "position": None},
    ])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.character.create_character.assert_awaited_once()
    create_kwargs = database.character.create_character.await_args.kwargs
    assert create_kwargs["source_id"] == "simulation_1"
    assert create_kwargs["location_id"] == "location_1"


async def test_restore_deletes_character_not_present_in_checkpoint():
    database = make_database()
    database.character.list_characters = AsyncMock(return_value=[make_character(id="character_extra")])
    database.character.delete_character = AsyncMock(return_value=True)
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(characters=[])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.character.delete_character.assert_awaited_once_with("character_extra")


async def test_restore_reconciles_relationship_via_force_set_then_falls_back_to_create():
    database = make_database()
    relationship = EntityRelationship(
        id="relationship_1",
        scope_type="simulation",
        scope_id="simulation_1",
        source=RelationshipEntityRef(type="character", id="character_1"),
        target=RelationshipEntityRef(type="character", id="character_2"),
        label="ally",
        visibility="public",
        confidence=0.8,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_changed_at=datetime(2026, 1, 1, tzinfo=UTC),
        version=1,
    )
    database.entity_relationship.force_set_relationship = AsyncMock(return_value=None)
    database.entity_relationship.create_relationship = AsyncMock(return_value=relationship)
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(entity_relationships=[{"entity": relationship.model_dump(mode="json")}])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.entity_relationship.force_set_relationship.assert_awaited_once()
    database.entity_relationship.create_relationship.assert_awaited_once()


async def test_restore_deletes_extra_relationship_not_in_checkpoint():
    relationship = EntityRelationship(
        id="relationship_extra",
        scope_type="simulation",
        scope_id="simulation_1",
        source=RelationshipEntityRef(type="character", id="character_1"),
        target=RelationshipEntityRef(type="character", id="character_2"),
        label="ally",
        visibility="public",
        confidence=0.8,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_changed_at=datetime(2026, 1, 1, tzinfo=UTC),
        version=1,
    )
    database = make_database()
    database.entity_relationship.list_relationships = AsyncMock(return_value=[relationship])
    database.entity_relationship.delete_relationship = AsyncMock(return_value=True)
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(entity_relationships=[])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.entity_relationship.delete_relationship.assert_awaited_once_with("relationship_extra")


async def test_restore_rehomes_before_deleting_extra_characters():
    """The ordering guarantee that matters: an extra (post-checkpoint) character's cascading
    delete must not run until every survivor has already been re-homed away from it."""
    database = make_database()
    character = make_character()
    database.character.overwrite_character = AsyncMock(return_value=character)
    database.character.list_characters = AsyncMock(return_value=[character, make_character(id="character_extra")])
    database.character.delete_character = AsyncMock(return_value=True)

    call_order = []
    database.character.move_to_location = AsyncMock(side_effect=lambda *a, **k: call_order.append("rehome"))
    database.character.remove_character_landmark = AsyncMock()

    async def record_delete(character_id):
        call_order.append("delete")
        return True

    database.character.delete_character = AsyncMock(side_effect=record_delete)
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(characters=[
        {"entity": character.model_dump(mode="json"), "location_id": "location_1", "position": None},
    ])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    assert call_order == ["rehome", "delete"]


async def test_restore_container_resyncs_unlocking_items():
    database = make_database()
    container = Container(id="container_1", name="Chest", description="A chest", state=ContainerState.OPEN)
    database.container.overwrite_container = AsyncMock(return_value=container)
    database.container.replace_unlocking_items = AsyncMock()
    database.container.remove_location = AsyncMock()
    database.container.remove_holder = AsyncMock()
    database.container.remove_owner = AsyncMock()
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(containers=[
        {"entity": container.model_dump(mode="json"), "unlocking_item_ids": ["item_1"]},
    ])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.container.replace_unlocking_items.assert_awaited_once_with("container_1", ["item_1"])


async def test_restore_deletes_extra_background_character():
    background = BackgroundCharacter(id="background_extra", name="Passerby", description="Someone passing by")
    database = make_database()
    database.character.list_background_characters = AsyncMock(return_value=[background])
    database.character.delete_background_character = AsyncMock(return_value=True)
    service = SimulationStateCheckpointService(database=database)
    checkpoint = make_checkpoint(background_characters=[])

    await service.restore(simulation_id="simulation_1", checkpoint=checkpoint)

    database.character.delete_background_character.assert_awaited_once_with("background_extra")
