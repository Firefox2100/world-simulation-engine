import os
from unittest.mock import AsyncMock, Mock

import pytest

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.image_generator import CharacterImageGenerator, \
    CharacterPortraitImageGenerator, ItemImageGenerator, LocationImageGenerator, SceneImageGenerator
from world_simulation_engine.misc.enums import ComponentType, ImageGenerationType
from world_simulation_engine.model import Character, CurrentActivity, GeneratedImageMediaFile, Item, Location


def make_character(character_id="character_1", name="Clara Whitlock") -> Character:
    return Character(
        id=character_id,
        name=name,
        age=42,
        gender="female",
        appearance="Weathered hands, a faded apron",
        description="The innkeeper",
        public_state="Behind the bar",
        private_state="Careful",
        current_activity=CurrentActivity(name="serving"),
    )


def make_identity_media(*, entity_kind: str, tags, description) -> GeneratedImageMediaFile:
    component = {
        "character": ComponentType.CHARACTER_IMAGE_GENERATOR,
        "location": ComponentType.LOCATION_IMAGE_GENERATOR,
    }[entity_kind]
    return GeneratedImageMediaFile(
        hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
        component=component, workflow_name=entity_kind,
        canonical_tags=tags, canonical_description=description,
    )


def stub_state_generation(monkeypatch, *, per_entity_tags_and_description):
    """Stub CharacterImageGenerator/LocationImageGenerator.generate_as_cover_image so composite
    generators (portrait/scene) can be tested without a real LLM/ComfyUI round trip."""

    async def fake_generate_as_cover_image(self, *, source_id, entity_id):
        kind = "location" if isinstance(self, LocationImageGenerator) else "character"
        tags, description = per_entity_tags_and_description[entity_id]
        return make_identity_media(entity_kind=kind, tags=tags, description=description)

    monkeypatch.setattr(CharacterImageGenerator, "generate_as_cover_image", fake_generate_as_cover_image)
    monkeypatch.setattr(LocationImageGenerator, "generate_as_cover_image", fake_generate_as_cover_image)


async def test_character_image_generator_fetches_character_and_builds_context():
    character = make_character()
    database = Mock()
    database.character.get_character = AsyncMock(return_value=character)
    generator = CharacterImageGenerator(database=database, storage=Mock())

    entity = await generator._get_entity("character_1")
    context = await generator._build_context(entity)

    assert entity == character
    database.character.get_character.assert_awaited_once_with("character_1")
    assert generator.COMPONENT_TYPE == ComponentType.CHARACTER_IMAGE_GENERATOR
    assert generator.WORKFLOW_NAME == "character"
    assert context.subjects[0].entity_id == "character_1"
    assert context.subjects[0].kind == "character"
    assert context.subjects[0].name == "Clara Whitlock"
    assert "innkeeper" in context.subjects[0].description
    assert "Weathered hands" in context.subjects[0].details
    assert context.subjects[0].pose_hint == "Behind the bar"
    assert "no scene" in context.purpose


async def test_location_image_generator_fetches_location_and_builds_context():
    location = Location(id="location_1", name="Tavern", description="A dim tavern with a crackling fire")
    database = Mock()
    database.location.get_location = AsyncMock(return_value=location)
    generator = LocationImageGenerator(database=database, storage=Mock())

    entity = await generator._get_entity("location_1")
    context = await generator._build_context(entity)

    assert entity == location
    database.location.get_location.assert_awaited_once_with("location_1")
    assert generator.COMPONENT_TYPE == ComponentType.LOCATION_IMAGE_GENERATOR
    assert generator.WORKFLOW_NAME == "location"
    assert context.subjects[0].entity_id == "location_1"
    assert context.subjects[0].kind == "location"
    assert context.subjects[0].name == "Tavern"
    assert "people" in generator.NEGATIVE_PROMPT


async def test_item_image_generator_fetches_item_and_builds_context():
    item = Item(id="item_1", name="Ledger", description="A leather-bound ledger with brass corners")
    database = Mock()
    database.item.get_item = AsyncMock(return_value=item)
    generator = ItemImageGenerator(database=database, storage=Mock())

    entity = await generator._get_entity("item_1")
    context = await generator._build_context(entity)

    assert entity == item
    database.item.get_item.assert_awaited_once_with("item_1")
    assert generator.COMPONENT_TYPE == ComponentType.ITEM_IMAGE_GENERATOR
    assert generator.WORKFLOW_NAME == "item"
    assert context.subjects[0].entity_id == "item_1"
    assert context.subjects[0].kind == "item"
    assert "hands" in generator.NEGATIVE_PROMPT


async def test_character_portrait_generator_requires_a_location():
    character = make_character()
    database = Mock()
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=None)
    generator = CharacterPortraitImageGenerator(database=database, storage=Mock())

    with pytest.raises(ValueError, match="is not in a location"):
        await generator.generate_portrait(simulation_id="simulation_1", character_id="character_1")


async def test_character_portrait_generator_ensures_both_identities_and_links_turn(monkeypatch):
    character = make_character()
    location = Location(id="location_1", name="Tavern", description="A dim tavern")
    database = Mock()
    database.character.get_character = AsyncMock(return_value=character)
    database.location.get_location_by_character = AsyncMock(return_value=location)
    database.location.get_location = AsyncMock(return_value=location)
    database.turn.get_turn = AsyncMock(return_value=Mock(content="fallback"))
    database.turn_presentation.list_blocks = AsyncMock(return_value=[Mock(text="Clara pours a drink.")])
    database.media.create_media = AsyncMock(side_effect=lambda media: media)
    database.media.add_generated_image_link = AsyncMock()
    database.media.link_turn_generated_image = AsyncMock()
    # Neither participant has an established identity yet - both must be ensured before the portrait.
    database.media.get_cover_image = AsyncMock(return_value=None)
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="a" * 64))
    generator = CharacterPortraitImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    stub_state_generation(monkeypatch, per_entity_tags_and_description={
        "character_1": (["character-tag"], "character identity"),
        "location_1": (["location-tag"], "location identity"),
    })
    generator._build_transient_prompt = AsyncMock(return_value=Mock(
        transient_tags=["evening", "candlelight", "quiet"],
        transient_description="Clara stands calmly near the fire.",
    ))
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    media = await generator.generate_portrait(
        simulation_id="simulation_1", character_id="character_1", turn_id="turn_1",
    )

    assert media.generation_type == ImageGenerationType.CHARACTER_PORTRAIT
    assert media.canonical_tags == ["character-tag", "location-tag"]
    context = generator._build_transient_prompt.await_args.kwargs["context"]
    assert context.narration == "Clara pours a drink."
    assert [subject.entity_id for subject in context.subjects] == ["character_1", "location_1"]
    database.media.add_generated_image_link.assert_any_await(source_id="character_1", media_id=media.id)
    database.media.add_generated_image_link.assert_any_await(source_id="location_1", media_id=media.id)
    database.media.link_turn_generated_image.assert_awaited_once_with(turn_id="turn_1", media_id=media.id)


async def test_scene_generator_requires_present_characters():
    location = Location(id="location_1", name="Tavern", description="A dim tavern")
    database = Mock()
    database.location.get_location = AsyncMock(return_value=location)
    database.get_characters_in_location = AsyncMock(return_value=[])
    generator = SceneImageGenerator(database=database, storage=Mock())

    with pytest.raises(ValueError, match="No characters are currently present"):
        await generator.generate_scene(simulation_id="simulation_1", location_id="location_1")


async def test_scene_generator_ensures_identity_for_location_and_every_present_character(monkeypatch):
    location = Location(id="location_1", name="Tavern", description="A dim tavern")
    clara = make_character(character_id="character_1", name="Clara")
    arthur = make_character(character_id="character_2", name="Arthur")
    database = Mock()
    database.location.get_location = AsyncMock(return_value=location)
    database.get_characters_in_location = AsyncMock(return_value=[
        (clara, location, None, None),
        (arthur, location, None, None),
    ])
    database.turn.get_turn = AsyncMock(return_value=None)
    database.media.create_media = AsyncMock(side_effect=lambda media: media)
    database.media.add_generated_image_link = AsyncMock()
    database.media.link_turn_generated_image = AsyncMock()
    database.media.get_cover_image = AsyncMock(return_value=None)
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="a" * 64))
    generator = SceneImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    stub_state_generation(monkeypatch, per_entity_tags_and_description={
        "location_1": (["identity-location_1"], "identity of location_1"),
        "character_1": (["identity-character_1"], "identity of character_1"),
        "character_2": (["identity-character_2"], "identity of character_2"),
    })
    generator._build_transient_prompt = AsyncMock(return_value=Mock(
        transient_tags=["evening", "busy", "loud"],
        transient_description="The two chat over drinks.",
    ))
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    media = await generator.generate_scene(simulation_id="simulation_1", location_id="location_1")

    assert media.generation_type == ImageGenerationType.SCENE
    assert media.canonical_tags == ["identity-location_1", "identity-character_1", "identity-character_2"]
    context = generator._build_transient_prompt.await_args.kwargs["context"]
    assert {subject.name for subject in context.subjects} == {"Tavern", "Clara", "Arthur"}
    assert database.media.add_generated_image_link.await_count == 3
    linked_source_ids = {
        call.kwargs["source_id"] for call in database.media.add_generated_image_link.await_args_list
    }
    assert linked_source_ids == {"location_1", "character_1", "character_2"}
