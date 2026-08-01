from uuid import uuid4

from world_simulation_engine.misc.enums import ConnectionType
from world_simulation_engine.model import AllTalkPiperModelConfig, AllTalkXttsModelConfig, CharacterTtsConfig, \
    ConnectionConfig
from world_simulation_engine.service.database.character_tts_config_store import CharacterTtsConfigStore
from world_simulation_engine.service.database.character_store import CharacterStore
from world_simulation_engine.service.database.config_store import ConfigStore
from integration_test.database_service.helpers import create_character, create_world


async def test_copy_character_tts_configs_shares_backend_not_copies_it(clean_neo4j):
    world = await create_world(clean_neo4j)
    target_world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id, name="Alex")
    voiced_character = await create_character(clean_neo4j, world.id, name="Voiced")
    character_store = CharacterStore(clean_neo4j)
    config_store = ConfigStore(clean_neo4j)
    tts_config_store = CharacterTtsConfigStore(clean_neo4j)

    backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en", temperature=0.75)
    await config_store.create_tts(backend)
    await tts_config_store.set_character_tts_config(
        voiced_character.id,
        CharacterTtsConfig(character_voice="female_01.wav", rvc_character_pitch=2),
    )
    await tts_config_store.link_character_tts_backend(voiced_character.id, backend.id)

    _, character_pairs = await character_store.copy_characters(
        world.id, target_world.id, return_pairs=True,
    )
    copied_character_id = next(
        pair["copy_id"] for pair in character_pairs if pair["source_id"] == voiced_character.id
    )
    unvoiced_copy_id = next(
        pair["copy_id"] for pair in character_pairs if pair["source_id"] == character.id
    )

    copied_configs, config_pairs = await tts_config_store.copy_character_tts_configs(character_pairs)

    assert len(copied_configs) == 1
    copied_config = copied_configs[0]
    assert copied_config.character_voice == "female_01.wav"
    assert copied_config.rvc_character_pitch == 2
    # The backend model config is shared config, not per-character data - it must be the exact
    # same node, not a duplicate, so editing/deleting it affects both the world and the copy alike.
    assert copied_config.backend == backend

    fetched = await tts_config_store.get_character_tts_config(copied_character_id)
    assert fetched == copied_config
    assert config_pairs == [
        {
            "source_id": (await tts_config_store.get_character_tts_config(voiced_character.id)).id,
            "copy_id": copied_config.id,
        }
    ]

    # A character with no configured voice should be silently skipped, not raise.
    assert await tts_config_store.get_character_tts_config(unvoiced_copy_id) is None
    assert await tts_config_store.copy_character_tts_configs([]) == ([], [])


async def test_character_tts_config_crud_and_backend_link(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    config_store = ConfigStore(clean_neo4j)
    store = CharacterTtsConfigStore(clean_neo4j)

    backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en", temperature=0.75)
    await config_store.create_tts(backend)

    assert await store.get_character_tts_config(character.id) is None

    config = CharacterTtsConfig(character_voice="female_01.wav", rvc_character_pitch=2)
    saved = await store.set_character_tts_config(character.id, config)

    assert saved.id == config.id
    assert saved.character_voice == "female_01.wav"
    assert saved.rvc_character_pitch == 2
    assert saved.backend is None
    assert await store.get_character_tts_config(character.id) == saved

    linked = await store.link_character_tts_backend(character.id, backend.id)

    assert linked.backend == backend
    assert linked.character_voice == "female_01.wav"
    assert await store.get_character_tts_config(character.id) == linked

    # Re-saving voice fields must not disturb the linked backend.
    updated = await store.set_character_tts_config(
        character.id,
        CharacterTtsConfig(id=config.id, character_voice="male_01.wav"),
    )
    assert updated.character_voice == "male_01.wav"
    assert updated.backend == backend

    assert await store.unlink_character_tts_backend(character.id) is True
    unlinked = await store.get_character_tts_config(character.id)
    assert unlinked.backend is None
    assert unlinked.character_voice == "male_01.wav"

    assert await store.delete_character_tts_config(character.id) is True
    assert await store.get_character_tts_config(character.id) is None
    assert await store.delete_character_tts_config(character.id) is False


async def test_multiple_characters_share_one_backend_with_different_voices(clean_neo4j):
    world = await create_world(clean_neo4j)
    alice = await create_character(clean_neo4j, world.id, name="Alice")
    bob = await create_character(clean_neo4j, world.id, name="Bob")
    config_store = ConfigStore(clean_neo4j)
    store = CharacterTtsConfigStore(clean_neo4j)

    shared_backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en")
    await config_store.create_tts(shared_backend)

    await store.set_character_tts_config(alice.id, CharacterTtsConfig(character_voice="female_01.wav"))
    await store.set_character_tts_config(bob.id, CharacterTtsConfig(character_voice="male_01.wav"))
    await store.link_character_tts_backend(alice.id, shared_backend.id)
    await store.link_character_tts_backend(bob.id, shared_backend.id)

    alice_config = await store.get_character_tts_config(alice.id)
    bob_config = await store.get_character_tts_config(bob.id)

    assert alice_config.character_voice == "female_01.wav"
    assert bob_config.character_voice == "male_01.wav"
    assert alice_config.backend == shared_backend
    assert bob_config.backend == shared_backend


async def test_link_character_tts_backend_replaces_previous_backend(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    config_store = ConfigStore(clean_neo4j)
    store = CharacterTtsConfigStore(clean_neo4j)

    first_backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en")
    second_backend = AllTalkPiperModelConfig(id=str(uuid4()), speed=1.2)
    await config_store.create_tts(first_backend)
    await config_store.create_tts(second_backend)
    await store.set_character_tts_config(character.id, CharacterTtsConfig(character_voice="female_01.wav"))

    await store.link_character_tts_backend(character.id, first_backend.id)
    relinked = await store.link_character_tts_backend(character.id, second_backend.id)

    assert relinked.backend == second_backend


async def test_delete_character_cascades_to_tts_config_but_not_shared_backend(clean_neo4j):
    world = await create_world(clean_neo4j)
    character = await create_character(clean_neo4j, world.id)
    config_store = ConfigStore(clean_neo4j)
    tts_config_store = CharacterTtsConfigStore(clean_neo4j)
    character_store = CharacterStore(clean_neo4j)

    backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en")
    await config_store.create_tts(backend)
    await tts_config_store.set_character_tts_config(character.id, CharacterTtsConfig(character_voice="female_01.wav"))
    await tts_config_store.link_character_tts_backend(character.id, backend.id)

    assert await character_store.delete_character(character.id) is True

    assert await tts_config_store.get_character_tts_config(character.id) is None
    assert await config_store.get_tts(backend.id) == backend
