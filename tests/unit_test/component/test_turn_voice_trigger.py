import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

import pytest

from world_simulation_engine.component.tts_generator.turn_voice_trigger import TurnVoiceTrigger
from world_simulation_engine.misc.enums import ConnectionType, TtsGenerationMode, TurnType
from world_simulation_engine.model import AllTalkXttsModelConfig, CharacterTtsConfig, ConnectionConfig, \
    GeneratedVoiceMediaFile, PresentationBlockType, PresentationCompletion, Turn, TurnPresentationBlock, \
    TtsGenerationConfig
from world_simulation_engine.service.tts_service.alltalk_v2 import TtsAllTalkV2
from world_simulation_engine.service.tts_service.tts_result import TtsFileResult


def make_block(*, block_type, text="hi", speaker_id=None, voice_media_id=None, block_id=None) -> TurnPresentationBlock:
    now = datetime.now(UTC)
    return TurnPresentationBlock(
        id=block_id or "block-1",
        turn_id="turn-1",
        sequence=0,
        type=block_type,
        text=text,
        speaker_id=speaker_id,
        voice_media_id=voice_media_id,
        completion=PresentationCompletion.COMPLETE,
        created_at=now,
        updated_at=now,
    )


def make_trigger(**overrides) -> tuple[TurnVoiceTrigger, MagicMock]:
    db = MagicMock()
    db.config = MagicMock()
    db.config.get_tts_generation_config = AsyncMock(return_value=TtsGenerationConfig(
        mode=TtsGenerationMode.AUTO, narrator_voice="male_01.wav",
        rvc_narrator_voice="voices/male.pth", rvc_narrator_pitch=1,
    ))
    db.config.get_tts_by_source = AsyncMock(return_value=AllTalkXttsModelConfig(
        id="backend-1", language="en", narrator_enabled=True,
    ))
    db.config.get_connection_by_tts_source = AsyncMock(return_value=ConnectionConfig(
        id="conn-1", type=ConnectionType.ALLTALK, name="Local AllTalk", base_url="http://alltalk.test",
    ))
    db.character_tts_config = MagicMock()
    db.character_tts_config.get_character_tts_config = AsyncMock(return_value=CharacterTtsConfig(
        character_voice="female_01.wav", rvc_character_voice="voices/female.pth", rvc_character_pitch=-2,
    ))
    db.turn_presentation = MagicMock()
    db.turn_presentation.list_blocks = AsyncMock(return_value=[])
    db.turn_presentation.get_block = AsyncMock(return_value=None)
    db.media = MagicMock()
    db.media.create_media = AsyncMock(side_effect=lambda media: media)
    db.media.link_presentation_block_voice = AsyncMock(return_value=None)
    db.media.list_voice_media_to_prune = AsyncMock(return_value=[])
    db.media.get_media = AsyncMock(return_value=None)
    db.turn = MagicMock()
    db.turn.get_simulation_id_for_turn = AsyncMock(return_value="sim-1")

    for key, value in overrides.items():
        parts = key.split(".")
        target = db
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], value)

    storage = MagicMock()
    storage.save_bytes = AsyncMock(return_value=MagicMock(digest="hash-1"))
    storage.delete = AsyncMock(return_value=None)

    return TurnVoiceTrigger(database=db, storage=storage), db


@pytest.fixture(autouse=True)
def fake_generate_file(monkeypatch):
    calls = []

    async def fake(self, text, *, character_voice=None, language=None, output_file_name=None,
                   rvc_character_voice=None, rvc_character_pitch=None):
        calls.append({
            "text": text,
            "character_voice": character_voice,
            "rvc_character_voice": rvc_character_voice,
            "rvc_character_pitch": rvc_character_pitch,
        })
        return TtsFileResult(audio=b"fake-audio")

    monkeypatch.setattr(TtsAllTalkV2, "generate_file", fake)
    return calls


async def test_maybe_generate_for_turn_noops_when_mode_is_manual(fake_generate_file):
    trigger, db = make_trigger()
    db.config.get_tts_generation_config = AsyncMock(return_value=TtsGenerationConfig(mode=TtsGenerationMode.MANUAL))
    turn = Turn(id="turn-1", sequence=1, type=TurnType.SYSTEM_RESPONSE, content="x", start_time=datetime.now(UTC))

    await trigger.maybe_generate_for_turn(simulation_id="sim-1", turn=turn)

    assert fake_generate_file == []
    db.turn_presentation.list_blocks.assert_not_awaited()


async def test_maybe_generate_for_turn_noops_when_no_config(fake_generate_file):
    trigger, db = make_trigger()
    db.config.get_tts_generation_config = AsyncMock(return_value=None)
    turn = Turn(id="turn-1", sequence=1, type=TurnType.SYSTEM_RESPONSE, content="x", start_time=datetime.now(UTC))

    await trigger.maybe_generate_for_turn(simulation_id="sim-1", turn=turn)

    assert fake_generate_file == []


async def test_maybe_generate_for_turn_noops_when_no_backend_configured(fake_generate_file):
    trigger, db = make_trigger()
    db.config.get_tts_by_source = AsyncMock(return_value=None)
    turn = Turn(id="turn-1", sequence=1, type=TurnType.SYSTEM_RESPONSE, content="x", start_time=datetime.now(UTC))

    # Must not raise even though no backend is configured - this is a fire-and-forget hook.
    await trigger.maybe_generate_for_turn(simulation_id="sim-1", turn=turn)

    assert fake_generate_file == []


async def test_maybe_generate_for_turn_only_voices_narration_and_speech_blocks(fake_generate_file):
    trigger, db = make_trigger()
    blocks = [
        make_block(block_type=PresentationBlockType.NARRATION, text="narration text", block_id="b-narration"),
        make_block(
            block_type=PresentationBlockType.SPEECH, text="speech text",
            speaker_id="char-1", block_id="b-speech",
        ),
        make_block(block_type=PresentationBlockType.THOUGHT, text="a thought", block_id="b-thought"),
        make_block(block_type=PresentationBlockType.ACTION, text="an action", block_id="b-action"),
        make_block(
            block_type=PresentationBlockType.SPEECH, text="already voiced",
            speaker_id="char-1", voice_media_id="existing-media", block_id="b-already-voiced",
        ),
    ]
    db.turn_presentation.list_blocks = AsyncMock(return_value=blocks)
    turn = Turn(id="turn-1", sequence=1, type=TurnType.SYSTEM_RESPONSE, content="x", start_time=datetime.now(UTC))

    await trigger.maybe_generate_for_turn(simulation_id="sim-1", turn=turn)

    generated_texts = {call["text"] for call in fake_generate_file}
    assert generated_texts == {"narration text", "speech text"}
    db.media.list_voice_media_to_prune.assert_awaited_once()


async def test_narration_block_uses_generation_config_narrator_voice(fake_generate_file):
    trigger, db = make_trigger()
    block = make_block(block_type=PresentationBlockType.NARRATION, text="narration text")
    db.turn_presentation.list_blocks = AsyncMock(return_value=[block])
    turn = Turn(id="turn-1", sequence=1, type=TurnType.SYSTEM_RESPONSE, content="x", start_time=datetime.now(UTC))

    await trigger.maybe_generate_for_turn(simulation_id="sim-1", turn=turn)

    assert fake_generate_file == [{
        "text": "narration text",
        "character_voice": "male_01.wav",
        "rvc_character_voice": "voices/male.pth",
        "rvc_character_pitch": 1,
    }]
    db.character_tts_config.get_character_tts_config.assert_not_awaited()


async def test_speech_block_uses_character_voice_not_narrator_voice(fake_generate_file):
    trigger, db = make_trigger()
    block = make_block(block_type=PresentationBlockType.SPEECH, text="speech text", speaker_id="char-1")
    db.turn_presentation.list_blocks = AsyncMock(return_value=[block])
    turn = Turn(id="turn-1", sequence=1, type=TurnType.SYSTEM_RESPONSE, content="x", start_time=datetime.now(UTC))

    await trigger.maybe_generate_for_turn(simulation_id="sim-1", turn=turn)

    assert fake_generate_file == [{
        "text": "speech text",
        "character_voice": "female_01.wav",
        "rvc_character_voice": "voices/female.pth",
        "rvc_character_pitch": -2,
    }]
    db.character_tts_config.get_character_tts_config.assert_awaited_once_with("char-1")


async def test_resolve_backend_forces_narrator_enabled_false_regardless_of_config():
    trigger, db = make_trigger()
    # backend config has narrator_enabled=True configured
    assert db.config.get_tts_by_source.return_value.narrator_enabled is True

    tts_service = await trigger._resolve_backend("sim-1")  # pylint: disable=protected-access

    assert tts_service is not None
    # the *original* fetched config is untouched...
    assert db.config.get_tts_by_source.return_value.narrator_enabled is True
    # ...but the driver actually built from it must never use AllTalk's own narrator-splitting,
    # since our own per-block split already guarantees purity.
    assert tts_service.driver._narrator_enabled is False  # pylint: disable=protected-access


async def test_generate_for_block_raises_for_missing_block():
    trigger, db = make_trigger()
    db.turn_presentation.get_block = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await trigger.generate_for_block(block_id="missing")


async def test_generate_for_block_raises_for_non_voiceable_block_type():
    trigger, db = make_trigger()
    db.turn_presentation.get_block = AsyncMock(
        return_value=make_block(block_type=PresentationBlockType.THOUGHT),
    )

    with pytest.raises(ValueError, match="not a narration or speech segment"):
        await trigger.generate_for_block(block_id="block-1")


async def test_generate_for_block_is_idempotent(fake_generate_file):
    trigger, db = make_trigger()
    existing_media = GeneratedVoiceMediaFile(
        hash="h", filename="f", presentation_block_id="block-1", turn_id="turn-1", text="hi",
    )
    db.turn_presentation.get_block = AsyncMock(return_value=make_block(
        block_type=PresentationBlockType.NARRATION, voice_media_id=existing_media.id,
    ))
    db.media.get_media = AsyncMock(return_value=existing_media)

    result = await trigger.generate_for_block(block_id="block-1")

    assert result is existing_media
    assert fake_generate_file == []
    db.config.get_tts_by_source.assert_not_awaited()


async def test_generate_for_block_raises_when_no_backend_configured():
    trigger, db = make_trigger()
    db.turn_presentation.get_block = AsyncMock(
        return_value=make_block(block_type=PresentationBlockType.NARRATION),
    )
    db.config.get_tts_by_source = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="does not have a TTS backend configured"):
        await trigger.generate_for_block(block_id="block-1")
