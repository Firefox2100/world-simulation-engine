from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from world_simulation_engine.service import SttService, SttTranscriptionResult
from .utils import db_dep


speech_recognition_router = APIRouter(
    tags=["Speech Recognition"],
)


@speech_recognition_router.post("/speech-recognition/transcribe", response_model=SttTranscriptionResult)
async def transcribe_speech(
        db: db_dep,
        file: UploadFile = File(...),
        language: Optional[str] = Form(None, description="Override the configured language for this call"),
):
    """STT is global rather than per-simulation - every simulation shares the one configured
    backend, so there is no source_id to resolve here (unlike image/TTS generation)."""
    stt_config = await db.config.get_global_stt()
    if not stt_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No STT model is configured",
        )

    connection_config = await db.config.get_connection_by_stt_source(stt_config.id)
    if not connection_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT model config {stt_config.id} does not have a connection configured",
        )

    audio = await file.read()
    stt_service = SttService(model_config=stt_config, connection_config=connection_config)

    return await stt_service.transcribe(
        audio,
        filename=file.filename or "audio.wav",
        content_type=file.content_type,
        language=language,
    )
