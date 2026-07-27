from datetime import UTC, datetime
from uuid import uuid4

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, TurnType, TtsGenerationMode
from world_simulation_engine.model import AllTalkXttsModelConfig, CharacterTtsConfig, ConnectionConfig, \
    GeneratedVoiceMediaFile, PresentationBlockType, PresentationCompletion, Simulation, Turn, \
    TurnPresentationBlock, TurnPresentationRendering, TtsGenerationConfig
from world_simulation_engine.service.database.character_tts_config_store import CharacterTtsConfigStore
from world_simulation_engine.service.database.config_store import ConfigStore
from world_simulation_engine.service.database.media_store import MediaStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.turn_presentation_store import TurnPresentationStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def _make_simulation(clean_neo4j, world):
    simulation = Simulation(
        id=str(uuid4()), name="TTS Simulation", description="d",
        current_time=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    return simulation


async def test_generated_voice_media_round_trips_and_links_to_presentation_block(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await _make_simulation(clean_neo4j, world)
    character = await create_character(clean_neo4j, simulation.id)

    turn_store = TurnStore(clean_neo4j)
    turn_presentation_store = TurnPresentationStore(clean_neo4j)
    media_store = MediaStore(clean_neo4j)

    turn = await turn_store.create_turn(
        Turn(id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="c", start_time=world.starting_time),
        source_id=simulation.id,
    )
    now = datetime.now(UTC)
    block = TurnPresentationBlock(
        turn_id=turn.id, sequence=0, type=PresentationBlockType.SPEECH, text="Hello there.",
        speaker_id=character.id, speaker_name=character.name, completion=PresentationCompletion.COMPLETE,
        created_at=now, updated_at=now,
    )
    rendering = await turn_presentation_store.replace_rendering(
        TurnPresentationRendering(turn_id=turn.id, blocks=[block]),
    )
    assert rendering.blocks[0].voice_media_id is None

    voice_media = GeneratedVoiceMediaFile(
        hash="hash-1", filename=block.id, presentation_block_id=block.id, turn_id=turn.id,
        character_id=character.id, text=block.text, voice_reference="female_01.wav",
    )
    created = await media_store.create_media(voice_media)
    assert isinstance(created, GeneratedVoiceMediaFile)
    assert created.character_id == character.id
    assert created.voice_reference == "female_01.wav"

    linked = await media_store.link_presentation_block_voice(block.id, created.id)
    assert linked.id == created.id

    fetched_block = await turn_presentation_store.get_block(block.id)
    assert fetched_block.voice_media_id == created.id

    listed_blocks = await turn_presentation_store.list_blocks(turn_ids=[turn.id])
    assert listed_blocks[0].voice_media_id == created.id

    fetched_media = await media_store.get_media(created.id)
    assert fetched_media == created


async def test_list_voice_media_to_prune_respects_keep_last_turns(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await _make_simulation(clean_neo4j, world)
    turn_store = TurnStore(clean_neo4j)
    turn_presentation_store = TurnPresentationStore(clean_neo4j)
    media_store = MediaStore(clean_neo4j)

    media_ids_by_turn = {}
    for sequence in range(1, 4):
        turn = await turn_store.create_turn(
            Turn(
                id=str(uuid4()), sequence=sequence, type=TurnType.SYSTEM_RESPONSE,
                content="c", start_time=world.starting_time,
            ),
            source_id=simulation.id,
        )
        now = datetime.now(UTC)
        block = TurnPresentationBlock(
            turn_id=turn.id, sequence=0, type=PresentationBlockType.NARRATION, text=f"turn {sequence}",
            completion=PresentationCompletion.COMPLETE, created_at=now, updated_at=now,
        )
        await turn_presentation_store.replace_rendering(TurnPresentationRendering(turn_id=turn.id, blocks=[block]))
        media = await media_store.create_media(GeneratedVoiceMediaFile(
            hash=f"hash-{sequence}", filename=block.id, presentation_block_id=block.id,
            turn_id=turn.id, text=block.text,
        ))
        await media_store.link_presentation_block_voice(block.id, media.id)
        media_ids_by_turn[sequence] = media.id

    # 3 turns exist (sequence 1, 2, 3); keeping the last 2 should flag only turn 1's media.
    to_prune = await media_store.list_voice_media_to_prune(simulation_id=simulation.id, keep_last_turns=2)
    assert {media.id for media in to_prune} == {media_ids_by_turn[1]}

    # keeping the last 10 (more turns than exist) should flag nothing.
    assert await media_store.list_voice_media_to_prune(simulation_id=simulation.id, keep_last_turns=10) == []

    # keeping 0 flags all of them.
    all_ids = {media.id for media in await media_store.list_voice_media_to_prune(
        simulation_id=simulation.id, keep_last_turns=0,
    )}
    assert all_ids == set(media_ids_by_turn.values())


async def test_tts_generation_config_get_and_set(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await _make_simulation(clean_neo4j, world)
    config_store = ConfigStore(clean_neo4j)

    assert await config_store.get_tts_generation_config(simulation.id) is None

    config = TtsGenerationConfig(mode=TtsGenerationMode.AUTO, autoplay_in_browser=True)
    saved = await config_store.set_tts_generation_config(simulation.id, config)

    assert saved == config
    assert saved.autoplay_in_browser is True
    assert await config_store.get_tts_generation_config(simulation.id) == config

    updated_config = TtsGenerationConfig(id=config.id, mode=TtsGenerationMode.MANUAL, autoplay_in_browser=False)
    resaved = await config_store.set_tts_generation_config(simulation.id, updated_config)

    assert resaved == updated_config
    assert resaved.autoplay_in_browser is False
    assert await config_store.get_tts_generation_config(simulation.id) == updated_config
    assert await config_store.get_tts_generation_config(str(uuid4())) is None


async def test_get_simulation_id_for_turn(clean_neo4j):
    world = await create_world(clean_neo4j)
    simulation = await _make_simulation(clean_neo4j, world)
    turn_store = TurnStore(clean_neo4j)

    turn = await turn_store.create_turn(
        Turn(id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="c", start_time=world.starting_time),
        source_id=simulation.id,
    )

    assert await turn_store.get_simulation_id_for_turn(turn.id) == simulation.id
    assert await turn_store.get_simulation_id_for_turn(str(uuid4())) is None

    # A turn created directly under a World (not a Simulation) should not resolve to a simulation.
    world_turn = await turn_store.create_turn(
        Turn(id=str(uuid4()), sequence=1, type=TurnType.SYSTEM_RESPONSE, content="c", start_time=world.starting_time),
        source_id=world.id,
    )
    assert await turn_store.get_simulation_id_for_turn(world_turn.id) is None


async def test_character_tts_config_backend_link_used_for_voice_resolution(clean_neo4j):
    """Exercises the full config graph a TurnVoiceTrigger reads: Simulation-linked backend +
    per-character voice config, independent of any generation call."""
    world = await create_world(clean_neo4j)
    simulation = await _make_simulation(clean_neo4j, world)
    character = await create_character(clean_neo4j, simulation.id)
    config_store = ConfigStore(clean_neo4j)
    character_tts_store = CharacterTtsConfigStore(clean_neo4j)

    connection = ConnectionConfig(
        id=str(uuid4()), type=ConnectionType.ALLTALK, name="Local AllTalk", base_url="http://localhost:7851",
    )
    backend = AllTalkXttsModelConfig(id=str(uuid4()), language="en", narrator_voice="male_01.wav")
    await config_store.create_connection(connection)
    await config_store.create_tts(backend)
    await config_store.link_connection(backend.id, connection.id)
    await config_store.link_tts(simulation.id, backend.id, ComponentType.NARRATOR_TTS)
    await character_tts_store.set_character_tts_config(
        character.id, CharacterTtsConfig(character_voice="female_01.wav"),
    )

    resolved_backend = await config_store.get_tts_by_source(simulation.id, ComponentType.NARRATOR_TTS)
    resolved_connection = await config_store.get_connection_by_tts_source(resolved_backend.id)
    resolved_character_config = await character_tts_store.get_character_tts_config(character.id)

    assert resolved_backend.id == backend.id
    assert resolved_backend.narrator_voice == "male_01.wav"
    assert resolved_connection.id == connection.id
    assert resolved_character_config.character_voice == "female_01.wav"
