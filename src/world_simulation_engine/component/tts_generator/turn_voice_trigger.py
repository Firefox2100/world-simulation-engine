import asyncio

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import ComponentType, TtsGenerationMode
from world_simulation_engine.misc.logging import log_event
from world_simulation_engine.model import GeneratedVoiceMediaFile, MediaFile, PresentationBlockType, Turn, \
    TtsGenerationConfig, TurnPresentationBlock
from world_simulation_engine.service import DatabaseService, StorageService
from world_simulation_engine.service.tts_service.tts_service import TtsService

_TTS_GENERATION_SEMAPHORE = asyncio.Semaphore(CONFIG.tts_max_concurrency)

_VOICEABLE_BLOCK_TYPES = (PresentationBlockType.NARRATION, PresentationBlockType.SPEECH)


class TurnVoiceTrigger:
    """Generates and links TTS audio for a turn's narration/speech segments.

    manual: `maybe_generate_for_turn` no-ops; segments are only voiced via `generate_for_block`
    (an explicit per-segment request). auto: every narration/speech segment of a committed turn
    is voiced automatically. Both paths share one process-wide semaphore
    (`WSE_TTS_MAX_CONCURRENCY`, default 3) since they hit the same backend, and both prune voice
    media older than the last `WSE_TTS_MEDIA_RETENTION_TURNS` turns after generating.
    """

    COMPONENT_TYPE = ComponentType.NARRATOR_TTS

    def __init__(self,
                 database: DatabaseService,
                 storage: StorageService | None = None,
                 ):
        self._db = database
        self._storage = storage

    async def _resolve_backend(self, simulation_id: str) -> TtsService | None:
        tts_config = await self._db.config.get_tts_by_source(
            source_id=simulation_id,
            component=self.COMPONENT_TYPE,
        )
        if not tts_config:
            return None

        connection_config = await self._db.config.get_connection_by_tts_source(source_id=tts_config.id)
        if not connection_config:
            return None

        # Our own narration/speech split already guarantees each call is pure one-voice text, so
        # AllTalk's own quote-based narrator-splitting must stay off here regardless of what's
        # configured - otherwise it could reroute a call to the wrong voice.
        sanitized_config = tts_config.model_copy(update={"narrator_enabled": False})

        return TtsService(model_config=sanitized_config, connection_config=connection_config)

    async def _resolve_generation_config(self, simulation_id: str) -> TtsGenerationConfig:
        return await self._db.config.get_tts_generation_config(simulation_id) or TtsGenerationConfig()

    async def _resolve_voice(self,
                             *,
                             generation_config: TtsGenerationConfig,
                             block: TurnPresentationBlock,
                             ) -> tuple[str | None, str | None, int | None, str | None]:
        """Returns (voice, rvc_voice, rvc_pitch, character_id)."""
        if block.type == PresentationBlockType.SPEECH and block.speaker_id:
            character_config = await self._db.character_tts_config.get_character_tts_config(block.speaker_id)
            if character_config:
                return (
                    character_config.character_voice,
                    character_config.rvc_character_voice,
                    character_config.rvc_character_pitch,
                    block.speaker_id,
                )
            return None, None, None, block.speaker_id

        return (
            generation_config.narrator_voice,
            generation_config.rvc_narrator_voice,
            generation_config.rvc_narrator_pitch,
            None,
        )

    async def _generate_and_store(self,
                                  *,
                                  tts_service: TtsService,
                                  generation_config: TtsGenerationConfig,
                                  block: TurnPresentationBlock,
                                  ) -> MediaFile:
        voice, rvc_voice, rvc_pitch, character_id = await self._resolve_voice(
            generation_config=generation_config, block=block,
        )

        async with _TTS_GENERATION_SEMAPHORE:
            result = await tts_service.generate_file(
                block.text or "", voice=voice, rvc_voice=rvc_voice, rvc_pitch=rvc_pitch,
            )

        stored = await self._storage.save_bytes(result.audio)
        media = await self._db.media.create_media(GeneratedVoiceMediaFile(
            hash=stored.digest,
            filename=block.id,
            presentation_block_id=block.id,
            turn_id=block.turn_id,
            character_id=character_id,
            text=block.text or "",
            voice_reference=voice,
        ))
        await self._db.media.link_presentation_block_voice(block_id=block.id, media_id=media.id)

        return media

    async def _generate_and_store_safe(self,
                                       *,
                                       simulation_id: str,
                                       tts_service: TtsService,
                                       generation_config: TtsGenerationConfig,
                                       block: TurnPresentationBlock,
                                       ) -> None:
        try:
            await self._generate_and_store(
                tts_service=tts_service, generation_config=generation_config, block=block,
            )
        except Exception as exc:  # noqa: BLE001 - never let one segment's failure affect others
            log_event(
                "turn_voice_segment_generation_failed",
                simulation_id=simulation_id,
                block_id=block.id,
                turn_id=block.turn_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )

    async def _prune(self, simulation_id: str) -> None:
        stale_media = await self._db.media.list_voice_media_to_prune(
            simulation_id=simulation_id,
            keep_last_turns=CONFIG.tts_media_retention_turns,
        )
        for media in stale_media:
            deleted = await self._db.media.delete_media(media.id)
            if not deleted:
                continue
            _, remaining_hash_references = deleted
            if remaining_hash_references == 0:
                await self._storage.delete(media.hash, missing_ok=True)

    async def maybe_generate_for_turn(self, *, simulation_id: str, turn: Turn) -> None:
        """Fire-and-forget entry point: evaluate the simulation's TtsGenerationConfig and, if in
        auto mode, voice every narration/speech segment of this turn. Never raises - failures are
        logged and swallowed so this never disrupts the turn pipeline."""
        try:
            generation_config = await self._db.config.get_tts_generation_config(simulation_id)
            if not generation_config or generation_config.mode != TtsGenerationMode.AUTO:
                return

            tts_service = await self._resolve_backend(simulation_id)
            if not tts_service:
                return

            blocks = await self._db.turn_presentation.list_blocks(turn_ids=[turn.id])
            pending = [
                block for block in blocks
                if block.type in _VOICEABLE_BLOCK_TYPES and not block.voice_media_id
            ]
            if not pending:
                return

            await asyncio.gather(*(
                self._generate_and_store_safe(
                    simulation_id=simulation_id, tts_service=tts_service,
                    generation_config=generation_config, block=block,
                )
                for block in pending
            ))
            await self._prune(simulation_id)
        except Exception as exc:  # noqa: BLE001 - fire-and-forget, must never bubble up
            log_event(
                "turn_voice_generation_failed",
                simulation_id=simulation_id,
                turn_id=turn.id,
                error_type=type(exc).__name__,
                error=str(exc),
            )

    async def generate_for_block(self, *, block_id: str) -> MediaFile:
        """Manual, explicit entry point for one segment - ignores TtsGenerationConfig.mode.
        Idempotent: returns the existing Media if this block already has voice audio. Raises on
        failure, since the caller is a waiting HTTP request."""
        block = await self._db.turn_presentation.get_block(block_id)
        if not block:
            raise ValueError(f"Presentation block {block_id} not found")
        if block.type not in _VOICEABLE_BLOCK_TYPES:
            raise ValueError(f"Presentation block {block_id} is not a narration or speech segment")

        if block.voice_media_id:
            existing = await self._db.media.get_media(block.voice_media_id)
            if existing:
                return existing

        simulation_id = await self._db.turn.get_simulation_id_for_turn(block.turn_id)
        if not simulation_id:
            raise ValueError(f"Turn {block.turn_id} does not belong to a simulation")

        tts_service = await self._resolve_backend(simulation_id)
        if not tts_service:
            raise ValueError(f"Simulation {simulation_id} does not have a TTS backend configured")
        generation_config = await self._resolve_generation_config(simulation_id)

        media = await self._generate_and_store(
            tts_service=tts_service, generation_config=generation_config, block=block,
        )
        await self._prune(simulation_id)

        return media
