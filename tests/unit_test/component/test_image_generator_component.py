import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from world_simulation_engine.component.image_generator.image_generator_component import CanonicalIdentity, \
    ImageGeneratorComponent, ImageParticipant, ImagePromptBuildContext, ImageSubjectContext
from world_simulation_engine.misc.consts import PROMPTS, WORKFLOWS
from world_simulation_engine.misc.enums import ComponentType, ConnectionType, ImageGenerationType, MediaType, \
    SupportedLanguage
from world_simulation_engine.model import ComfyUiImageModelConfig, ConnectionConfig, GeneratedImageMediaFile, \
    ImagePromptProposal, MediaFile, TransientImagePromptProposal, World


class _FakeEntity:
    def __init__(self, entity_id: str, name: str):
        self.id = entity_id
        self.name = name


class _FakeImageGenerator(ImageGeneratorComponent):
    COMPONENT_TYPE = ComponentType.CHARACTER_IMAGE_GENERATOR
    WORKFLOW_NAME = "character"

    async def _get_entity(self, entity_id: str):
        return await self._db.character.get_character(entity_id)

    async def _build_context(self, entity) -> ImagePromptBuildContext:
        return ImagePromptBuildContext(
            purpose="test purpose",
            subjects=[ImageSubjectContext(
                entity_id=entity.id, kind="character", name=entity.name, description="a description",
            )],
        )


def make_world() -> World:
    return World(
        id="world_1",
        name="World",
        description="A test world",
        starting_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        version=1,
        language=SupportedLanguage.ENGLISH,
    )


def make_database():
    database = Mock()
    database.world.get_world = AsyncMock(return_value=make_world())
    database.world.get_world_by_simulation = AsyncMock(return_value=None)
    database.config.get_image_by_source = AsyncMock(return_value=None)
    database.config.get_connection_by_image_source = AsyncMock(return_value=None)
    database.config.get_chat_by_source = AsyncMock(return_value=None)
    database.config.get_connection_by_source = AsyncMock(return_value=None)
    database.character.get_character = AsyncMock(return_value=None)
    database.media.get_cover_image = AsyncMock(return_value=None)
    database.media.create_media = AsyncMock(side_effect=lambda media: media)
    database.media.add_generated_image_link = AsyncMock()
    database.media.link_turn_generated_image = AsyncMock()
    database.media.set_cover_image = AsyncMock()
    return database


def make_full_proposal(**overrides) -> ImagePromptProposal:
    defaults = dict(
        canonical_tags=["tall", "brown hair", "scar"],
        canonical_description="A tall figure with brown hair and a scar.",
        transient_tags=["evening", "tavern", "calm"],
        transient_description="Standing calmly by the bar.",
    )
    defaults.update(overrides)
    return ImagePromptProposal(**defaults)


def make_transient_proposal(**overrides) -> TransientImagePromptProposal:
    defaults = dict(
        transient_tags=["morning", "smiling", "bright"],
        transient_description="Smiling in the morning light.",
    )
    defaults.update(overrides)
    return TransientImagePromptProposal(**defaults)


# --- resolve_language / prepare_workflow / prepare_prompt / prepare_llm_service / prepare_image_service ---
# (unchanged infra, still covered)

async def test_resolve_language_from_world_id():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    language = await generator._resolve_language("world_1")

    assert language == SupportedLanguage.ENGLISH


async def test_resolve_language_raises_when_source_not_found():
    database = make_database()
    database.world.get_world = AsyncMock(return_value=None)
    generator = _FakeImageGenerator(database=database, storage=Mock())

    with pytest.raises(ValueError, match="World for source"):
        await generator._resolve_language("missing")


async def test_prepare_workflow_uses_workflow_loader_when_configured():
    database = make_database()
    workflow_loader = Mock()
    workflow_loader.load_workflow = AsyncMock(return_value={"workflow": {}, "positive_prompt": "/1/inputs/text"})
    generator = _FakeImageGenerator(database=database, storage=Mock(), workflow_loader=workflow_loader)

    result = await generator._prepare_workflow("source_1")

    assert result == {"workflow": {}, "positive_prompt": "/1/inputs/text"}


async def test_prepare_workflow_falls_back_to_builtin_without_workflow_loader():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    result = await generator._prepare_workflow("source_1")

    assert result == WORKFLOWS["character"]


async def test_prepare_prompt_falls_back_to_builtin_without_prompt_loader():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    result = await generator._prepare_prompt(
        source_id="source_1", language=SupportedLanguage.ENGLISH, prompt_name="image_prompt_builder",
    )

    assert len(result) == len(PROMPTS[SupportedLanguage.ENGLISH]["image_prompt_builder"])


async def test_prepare_llm_service_raises_without_chat_config():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    with pytest.raises(ValueError, match="does not have a chat model configured"):
        await generator._prepare_llm_service("source_1")


async def test_prepare_image_service_raises_without_image_config():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    with pytest.raises(ValueError, match="does not have an image model configured"):
        await generator._prepare_image_service("source_1")


async def test_prepare_image_service_builds_image_service_with_workflow():
    database = make_database()
    image_config = ComfyUiImageModelConfig(id="image_1", model="anima-base-v1.0.safetensors")
    connection = ConnectionConfig(id="connection_1", type=ConnectionType.COMFYUI, name="Local ComfyUI")
    database.config.get_image_by_source = AsyncMock(return_value=image_config)
    database.config.get_connection_by_image_source = AsyncMock(return_value=connection)
    generator = _FakeImageGenerator(database=database, storage=Mock())

    image_service = await generator._prepare_image_service("source_1")

    assert image_service._model_config == image_config
    assert image_service._connection_config == connection


# --- canonical identity lookup ---

async def test_get_existing_canonical_identity_returns_none_without_cover():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    assert await generator._get_existing_canonical_identity("character_1") is None


async def test_get_existing_canonical_identity_returns_none_for_non_generated_cover():
    database = make_database()
    database.media.get_cover_image = AsyncMock(return_value=MediaFile(hash="a" * 64, filename="x", type=MediaType.PNG))
    generator = _FakeImageGenerator(database=database, storage=Mock())

    assert await generator._get_existing_canonical_identity("character_1") is None


async def test_get_existing_canonical_identity_returns_identity_from_generated_cover():
    database = make_database()
    database.media.get_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
        component=ComponentType.CHARACTER_IMAGE_GENERATOR, workflow_name="character",
        canonical_tags=["tall"], canonical_description="A tall figure.",
    ))
    generator = _FakeImageGenerator(database=database, storage=Mock())

    identity = await generator._get_existing_canonical_identity("character_1")

    assert identity == CanonicalIdentity(tags=["tall"], description="A tall figure.")


async def test_ensure_canonical_identity_reuses_existing():
    database = make_database()
    database.media.get_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
        component=ComponentType.CHARACTER_IMAGE_GENERATOR, workflow_name="character",
        canonical_tags=["tall"], canonical_description="A tall figure.",
    ))
    generator = _FakeImageGenerator(database=database, storage=Mock())
    state_generator = Mock()
    state_generator.generate_as_cover_image = AsyncMock()

    identity = await generator._ensure_canonical_identity(
        state_generator=state_generator, source_id="source_1", entity_id="character_1",
    )

    assert identity == CanonicalIdentity(tags=["tall"], description="A tall figure.")
    state_generator.generate_as_cover_image.assert_not_awaited()


async def test_ensure_canonical_identity_establishes_when_missing():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())
    state_generator = Mock()
    state_generator.generate_as_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
        component=ComponentType.LOCATION_IMAGE_GENERATOR, workflow_name="location",
        canonical_tags=["stone walls"], canonical_description="A stone-walled room.",
    ))

    identity = await generator._ensure_canonical_identity(
        state_generator=state_generator, source_id="source_1", entity_id="location_1",
    )

    assert identity == CanonicalIdentity(tags=["stone walls"], description="A stone-walled room.")
    state_generator.generate_as_cover_image.assert_awaited_once_with(source_id="source_1", entity_id="location_1")


# --- generate(): establish vs reuse ---

async def test_generate_establishes_identity_on_first_generation(monkeypatch):
    database = make_database()
    entity = _FakeEntity("character_1", "Alex")
    database.character.get_character = AsyncMock(return_value=entity)
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="b" * 64))
    generator = _FakeImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    generator._build_full_prompt = AsyncMock(return_value=make_full_proposal())
    generator._build_transient_prompt = AsyncMock()
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    media = await generator.generate(source_id="source_1", entity_id="character_1")

    generator._build_full_prompt.assert_awaited_once()
    generator._build_transient_prompt.assert_not_awaited()
    assert media.generation_type == ImageGenerationType.STATE
    assert media.canonical_tags == ["tall", "brown hair", "scar"]
    assert media.canonical_description == "A tall figure with brown hair and a scar."
    assert media.transient_tags == ["evening", "tavern", "calm"]
    image_service.generate_image.assert_awaited_once_with(
        positive_prompt="tall, brown hair, scar, evening, tavern, calm. "
                        "A tall figure with brown hair and a scar. Standing calmly by the bar.",
        negative_prompt=_FakeImageGenerator.NEGATIVE_PROMPT,
    )


async def test_generate_reuses_existing_identity_and_only_regenerates_transient(monkeypatch):
    database = make_database()
    entity = _FakeEntity("character_1", "Alex")
    database.character.get_character = AsyncMock(return_value=entity)
    database.media.get_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
        component=ComponentType.CHARACTER_IMAGE_GENERATOR, workflow_name="character",
        canonical_tags=["tall", "brown hair"], canonical_description="A tall figure with brown hair.",
    ))
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="b" * 64))
    generator = _FakeImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    generator._build_full_prompt = AsyncMock()
    generator._build_transient_prompt = AsyncMock(return_value=make_transient_proposal())
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    media = await generator.generate(source_id="source_1", entity_id="character_1")

    generator._build_full_prompt.assert_not_awaited()
    generator._build_transient_prompt.assert_awaited_once()
    passed_context = generator._build_transient_prompt.await_args.kwargs["context"]
    assert passed_context.subjects[0].canonical_tags == ["tall", "brown hair"]
    assert passed_context.subjects[0].canonical_description == "A tall figure with brown hair."
    # Canonical identity carried forward unchanged; only transient content is new.
    assert media.canonical_tags == ["tall", "brown hair"]
    assert media.canonical_description == "A tall figure with brown hair."
    assert media.transient_tags == ["morning", "smiling", "bright"]


async def test_generate_raises_when_entity_not_found():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    with pytest.raises(ValueError, match="Entity character_1 not found"):
        await generator.generate(source_id="source_1", entity_id="character_1")


async def test_generate_as_cover_image_sets_cover(monkeypatch):
    database = make_database()
    entity = _FakeEntity("character_1", "Alex")
    database.character.get_character = AsyncMock(return_value=entity)
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="b" * 64))
    generator = _FakeImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    generator._build_full_prompt = AsyncMock(return_value=make_full_proposal())
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    media = await generator.generate_as_cover_image(source_id="source_1", entity_id="character_1")

    database.media.set_cover_image.assert_awaited_once_with("character_1", media.id)


# --- _store_generated_image / _generate_from_parts ---

async def test_store_generated_image_links_entities_and_turn(monkeypatch):
    database = make_database()
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="a" * 64))
    generator = _FakeImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(return_value=b"normalised-png-bytes"),
    )

    media = await generator._store_generated_image(
        entity_ids=["character_1", "location_1"],
        image_bytes=b"raw-bytes",
        generation_type=ImageGenerationType.SCENE,
        canonical_tags=["tall", "stone walls"],
        canonical_description="A tall figure in a stone-walled room.",
        transient_tags=["evening"],
        transient_description="Talking quietly.",
        title="Scene",
        turn_id="turn_1",
    )

    assert isinstance(media, MediaFile)
    assert media.type == MediaType.PNG
    assert media.canonical_tags == ["tall", "stone walls"]
    assert media.transient_tags == ["evening"]
    storage.save_bytes.assert_awaited_once_with(b"normalised-png-bytes")
    assert database.media.add_generated_image_link.await_count == 2
    database.media.add_generated_image_link.assert_any_await(source_id="character_1", media_id=media.id)
    database.media.add_generated_image_link.assert_any_await(source_id="location_1", media_id=media.id)
    database.media.link_turn_generated_image.assert_awaited_once_with(turn_id="turn_1", media_id=media.id)


async def test_generate_from_parts_combines_canonical_and_transient_into_prompt(monkeypatch):
    database = make_database()
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="a" * 64))
    generator = _FakeImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    await generator._generate_from_parts(
        source_id="source_1", entity_ids=["character_1"],
        canonical_tags=["tall"], canonical_description="A tall figure.",
        transient_tags=["smiling"], transient_description="Smiling warmly.",
        generation_type=ImageGenerationType.STATE,
    )

    image_service.generate_image.assert_awaited_once_with(
        positive_prompt="tall, smiling. A tall figure. Smiling warmly.",
        negative_prompt=_FakeImageGenerator.NEGATIVE_PROMPT,
    )


# --- _generate_composite / _ensure_participants (multi-subject) ---

async def test_ensure_participants_establishes_missing_and_reuses_existing():
    database = make_database()
    generator = _FakeImageGenerator(database=database, storage=Mock())

    known_state_generator = Mock()
    known_state_generator.generate_as_cover_image = AsyncMock()
    database.media.get_cover_image = AsyncMock(side_effect=lambda entity_id: (
        GeneratedImageMediaFile(
            hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
            component=ComponentType.LOCATION_IMAGE_GENERATOR, workflow_name="location",
            canonical_tags=["stone walls"], canonical_description="A stone-walled room.",
        ) if entity_id == "location_1" else None
    ))
    missing_state_generator = Mock()
    missing_state_generator.generate_as_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="b" * 64, filename="y", generation_type=ImageGenerationType.STATE,
        component=ComponentType.CHARACTER_IMAGE_GENERATOR, workflow_name="character",
        canonical_tags=["tall"], canonical_description="A tall figure.",
    ))

    participants = [
        ImageParticipant(
            entity_id="location_1", kind="location", name="Tavern", description="A dim tavern",
            details="A dim tavern", pose_hint="", state_generator=known_state_generator,
        ),
        ImageParticipant(
            entity_id="character_1", kind="character", name="Clara", description="The innkeeper",
            details="...", pose_hint="Behind the bar", state_generator=missing_state_generator,
        ),
    ]

    subjects = await generator._ensure_participants(source_id="source_1", participants=participants)

    assert subjects[0].canonical_tags == ["stone walls"]
    known_state_generator.generate_as_cover_image.assert_not_awaited()
    assert subjects[1].canonical_tags == ["tall"]
    missing_state_generator.generate_as_cover_image.assert_awaited_once_with(
        source_id="source_1", entity_id="character_1",
    )


async def test_generate_composite_combines_all_participant_identities(monkeypatch):
    database = make_database()
    storage = Mock()
    storage.save_bytes = AsyncMock(return_value=Mock(digest="a" * 64))
    generator = _FakeImageGenerator(database=database, storage=storage)
    monkeypatch.setattr(
        "world_simulation_engine.component.image_generator.image_generator_component.FormatNormaliser.normalise_image",
        Mock(side_effect=lambda data: data),
    )
    generator._build_transient_prompt = AsyncMock(return_value=make_transient_proposal(
        transient_tags=["night", "candlelight", "quiet"],
        transient_description="They talk quietly by candlelight.",
    ))
    image_service = Mock()
    image_service.generate_image = AsyncMock(return_value=b"png-bytes")
    generator._prepare_image_service = AsyncMock(return_value=image_service)

    location_generator = Mock()
    location_generator.generate_as_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="a" * 64, filename="x", generation_type=ImageGenerationType.STATE,
        component=ComponentType.LOCATION_IMAGE_GENERATOR, workflow_name="location",
        canonical_tags=["stone walls"], canonical_description="A stone-walled room.",
    ))
    character_generator = Mock()
    character_generator.generate_as_cover_image = AsyncMock(return_value=GeneratedImageMediaFile(
        hash="b" * 64, filename="y", generation_type=ImageGenerationType.STATE,
        component=ComponentType.CHARACTER_IMAGE_GENERATOR, workflow_name="character",
        canonical_tags=["tall"], canonical_description="A tall figure.",
    ))
    participants = [
        ImageParticipant(
            entity_id="location_1", kind="location", name="Tavern", description="A dim tavern",
            details="A dim tavern", pose_hint="", state_generator=location_generator,
        ),
        ImageParticipant(
            entity_id="character_1", kind="character", name="Clara", description="The innkeeper",
            details="...", pose_hint="Behind the bar", state_generator=character_generator,
        ),
    ]

    media = await generator._generate_composite(
        source_id="source_1", purpose="A scene.", participants=participants,
        generation_type=ImageGenerationType.SCENE, narration="Clara pours a drink.",
    )

    assert media.canonical_tags == ["stone walls", "tall"]
    assert media.canonical_description == "A stone-walled room. A tall figure."
    assert media.transient_tags == ["night", "candlelight", "quiet"]
    context = generator._build_transient_prompt.await_args.kwargs["context"]
    assert context.narration == "Clara pours a drink."
    assert [subject.entity_id for subject in context.subjects] == ["location_1", "character_1"]
    assert database.media.add_generated_image_link.await_count == 2


# --- narration helper (unchanged behaviour) ---

async def test_narration_for_turn_prefers_presentation_blocks():
    database = make_database()
    database.turn.get_turn = AsyncMock(return_value=Mock(content="raw content"))
    database.turn_presentation.list_blocks = AsyncMock(return_value=[
        Mock(text="First block."), Mock(text="Second block."),
    ])
    generator = _FakeImageGenerator(database=database, storage=Mock())

    narration = await generator._narration_for_turn("turn_1")

    assert narration == "First block.\nSecond block."


async def test_narration_for_turn_falls_back_to_raw_content_without_blocks():
    database = make_database()
    database.turn.get_turn = AsyncMock(return_value=Mock(content="raw content"))
    database.turn_presentation.list_blocks = AsyncMock(return_value=[])
    generator = _FakeImageGenerator(database=database, storage=Mock())

    narration = await generator._narration_for_turn("turn_1")

    assert narration == "raw content"
