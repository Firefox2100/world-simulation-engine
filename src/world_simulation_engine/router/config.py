from typing import Any, Optional
from uuid import uuid4
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from httpx import HTTPError
from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ComponentType, ConnectionType, ImageGenerationMode, \
    TtsGenerationMode, TtsTextFilteringMode, TtsTextNotInsideMode
from world_simulation_engine.model import AllTalkStatus, ConnectionConfig, OllamaChatModelConfig, \
    OpenAiChatModelConfig, ChatModelConfigUnion, OllamaEmbedModelConfig, OpenAiEmbedModelConfig, \
    GoogleGenAiEmbedModelConfig, MistralAiEmbedModelConfig, CohereEmbedModelConfig, PerplexityEmbedModelConfig, \
    CloudflareEmbedModelConfig, EmbedModelConfigUnion, ImageGenerationConfig, \
    AllTalkF5ttsModelConfig, AllTalkParlerModelConfig, \
    AllTalkPiperModelConfig, AllTalkVitsModelConfig, AllTalkXttsModelConfig, TtsModelConfigUnion, \
    TtsGenerationConfig, SttModelConfigUnion, WhisperCppSttModelConfig, ComfyUiImageModelConfig, \
    ImageModelConfigUnion
from world_simulation_engine.service.tts_service.alltalk_v2 import TtsAllTalkV2
from .utils import db_dep


config_router = APIRouter(
    tags=["Config"],
)


class ConnectionUpdate(BaseModel):
    """
    DTO model for updating connection configs
    """

    type: Optional[ConnectionType] = Field(None, description="Type of the connection")
    name: Optional[str] = Field(None, description="Name of the connection")
    base_url: Optional[str] = Field(None, description="Base URL for the connection")
    api_key: Optional[str] = Field(None, description="API key for the connection")


class ChatConfigUpdate(BaseModel):
    """
    DTO model for updating chat model configs
    """

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(None, description="The name of the chat config")
    model: Optional[str] = Field(None, description="The model to use for the chat")
    temperature: Optional[float] = Field(None, description="The temperature to use for the chat")
    context_window: Optional[int] = Field(None, description="The context window to use for the chat")
    seed: Optional[int] = Field(None, description="The seed to use for the chat")
    reasoning: Optional[str | bool | dict[str, Any]] = Field(
        None,
        description="Whether to enable reasoning for the chat",
    )
    stop_tokens: Optional[list[str]] = Field(None, description="The stop tokens to use for the chat")
    mirostat: Optional[int] = Field(None, description="Enable Mirostat sampling")
    mirostat_eta: Optional[float] = Field(None, description="Mirostat learning rate")
    mirostat_tau: Optional[float] = Field(None, description="Mirostat target entropy")
    num_predict: Optional[int] = Field(None, description="Maximum number of tokens to predict")
    repeat_penalty_window: Optional[int] = Field(None, description="Repeat penalty lookback window")
    repeat_penalty: Optional[float] = Field(None, description="Repeat penalty strength")


class EmbedConfigUpdate(BaseModel):
    """
    DTO model for updating embedding model configs
    """

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(None, description="The name of the embedding config")
    model: Optional[str] = Field(None, description="The model to use for embedding")
    dimension: Optional[int] = Field(None, description="The dimensionality of the model")
    context_window: Optional[int] = Field(None, description="The context window to use for embedding")


class TtsConfigUpdate(BaseModel):
    """
    DTO model for updating TTS model configs. Fields span every AllTalk engine; only the ones
    applicable to the target config's engine have any effect. Holds no voice of any kind - narrator
    voice is updated via TtsGenerationConfigUpdate and character voice via CharacterTtsConfigUpdate.
    """

    name: Optional[str] = Field(None, description="Display name of the TTS config")
    model: Optional[str] = Field(None, description="Name of the model to use")
    text_filtering: Optional[TtsTextFilteringMode] = Field(None, description="Text filtering mode")
    text_not_inside: Optional[TtsTextNotInsideMode] = Field(
        None, description="How to voice text that is not inside quotes",
    )
    narrator_enabled: Optional[bool] = Field(None, description="Whether to enable the narrator voice")
    output_file_timestamp: Optional[bool] = Field(None, description="Append a timestamp to the output file name")
    autoplay: Optional[bool] = Field(None, description="Play the generated audio at the provider's terminal")
    autoplay_volume: Optional[float] = Field(None, description="Playback volume if autoplay is enabled")
    language: Optional[str] = Field(None, description="Language for the TTS generation, if the engine supports it")
    speed: Optional[float] = Field(None, description="Speed of the generated speech, if the engine supports it")
    temperature: Optional[float] = Field(None, description="Sampling temperature, if the engine supports it")
    repetition_penalty: Optional[float] = Field(
        None, description="Repetition penalty, if the engine supports it",
    )


class ImageConfigUpdate(BaseModel):
    """
    DTO model for updating image model configs
    """

    model: Optional[str] = Field(None, description="Name of the model to use")
    vae: Optional[str] = Field(None, description="Name of the vae model to use")
    clip: Optional[str] = Field(None, description="Name of the clip model to use")
    image_width: Optional[int] = Field(None, description="Width of the image to generate")
    image_height: Optional[int] = Field(None, description="Height of the image to generate")
    seed: Optional[int] = Field(None, description="Seed for the random number generator")
    steps: Optional[int] = Field(None, description="Number of steps to generate for each image")
    cfg: Optional[int] = Field(None, description="Configuration parameters")


class SttConfigUpdate(BaseModel):
    """
    DTO model for updating STT model configs
    """

    model: Optional[str] = Field(None, description="Name of the model to use")
    language: Optional[str] = Field(None, description="Spoken language code, e.g. 'en' or 'auto'")
    translate: Optional[bool] = Field(None, description="Whether to translate the transcription into English")
    temperature: Optional[float] = Field(None, description="Sampling temperature for decoding")
    temperature_inc: Optional[float] = Field(None, description="Temperature increment used on decoding fallback")
    initial_prompt: Optional[str] = Field(None, description="Initial prompt text to bias vocabulary/context")
    carry_initial_prompt: Optional[bool] = Field(
        None, description="Whether to always prepend the initial prompt",
    )


class ImageGenerationConfigUpdate(BaseModel):
    """
    DTO model for updating a simulation's auto image generation configuration
    """

    mode: ImageGenerationMode = Field(..., description="manual, auto, or always")
    fallback_turns: int = Field(
        10,
        ge=1,
        description="In auto mode, force a generation if this many turns passed without one",
    )


class TtsGenerationConfigUpdate(BaseModel):
    """
    DTO model for updating a simulation's auto TTS generation configuration, and the narrator's voice.
    """

    mode: TtsGenerationMode = Field(
        ..., description="manual: voice must be generated per-segment on demand. auto: every "
                          "narration/speech segment is voiced automatically",
    )
    autoplay_in_browser: bool = Field(
        False, description="Whether the frontend should auto-play a turn's segments once generated",
    )
    narrator_voice: Optional[str] = Field(
        None, description="Reference to the narrator's voice, used for narration segments and speech "
                          "with no attributed speaker",
    )
    rvc_narrator_voice: Optional[str] = Field(
        None, description="RVC voice model for the narrator, as 'folder/file.pth', or 'Disabled' to skip RVC",
    )
    rvc_narrator_pitch: Optional[int] = Field(
        None, description="Pitch adjustment applied to the narrator RVC voice",
    )


class ConfigConnectionUpdate(BaseModel):
    """
    DTO model for linking model configs to connection configs
    """

    connection_id: str = Field(..., description="The connection config id")


class SimulationModelConfigUpdate(BaseModel):
    """
    DTO model for linking simulations to model configs
    """

    component: ComponentType = Field(..., description="The simulation component using the config")
    config_id: str = Field(..., description="The model config id")


class ComponentChatConfig(BaseModel):
    """
    DTO model for a component-specific chat config assignment
    """

    component: ComponentType = Field(..., description="The component using the config")
    config: ChatModelConfigUnion = Field(..., description="The assigned chat model config")


class ComponentEmbedConfig(BaseModel):
    """
    DTO model for a component-specific embedding config assignment
    """

    component: ComponentType = Field(..., description="The component using the config")
    config: EmbedModelConfigUnion = Field(..., description="The assigned embedding model config")


class ComponentTtsConfig(BaseModel):
    """
    DTO model for a component-specific TTS config assignment
    """

    component: ComponentType = Field(..., description="The component using the config")
    config: TtsModelConfigUnion = Field(..., description="The assigned TTS model config")


class ComponentImageConfig(BaseModel):
    """
    DTO model for a component-specific image config assignment
    """

    component: ComponentType = Field(..., description="The component using the config")
    config: ImageModelConfigUnion = Field(..., description="The assigned image model config")


class ComponentModelConfigUpdate(BaseModel):
    """
    DTO model for a component-specific optional model config assignment
    """

    component: ComponentType = Field(..., description="The component using the config")
    config_id: Optional[str] = Field(None, description="The model config id")


class ComponentModelConfigBatchUpdate(BaseModel):
    """
    DTO model for replacing model config assignments across multiple components
    """

    assignments: list[ComponentModelConfigUpdate] = Field(
        ..., description="The component assignments to update"
    )


async def _validate_simulation(simulation_id: str, db: db_dep):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


async def _validate_world(world_id: str, db: db_dep):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


async def _apply_chat_assignments(source_id: str, assignments: list[ComponentModelConfigUpdate], db: db_dep):
    for assignment in assignments:
        if assignment.config_id:
            if not await db.config.get_chat(assignment.config_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"LLM config {assignment.config_id} not found",
                )
            await db.config.link_chat(source_id, assignment.config_id, assignment.component)
        else:
            await db.config.unlink_chat(source_id, assignment.component)


async def _apply_embed_assignments(source_id: str, assignments: list[ComponentModelConfigUpdate], db: db_dep):
    for assignment in assignments:
        if assignment.config_id:
            if not await db.config.get_embed(assignment.config_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Embedding config {assignment.config_id} not found",
                )
            await db.config.link_embed(source_id, assignment.config_id, assignment.component)
        else:
            await db.config.unlink_embed(source_id, assignment.component)


async def _apply_tts_assignments(source_id: str, assignments: list[ComponentModelConfigUpdate], db: db_dep):
    for assignment in assignments:
        if assignment.config_id:
            if not await db.config.get_tts(assignment.config_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"TTS config {assignment.config_id} not found",
                )
            await db.config.link_tts(source_id, assignment.config_id, assignment.component)
        else:
            await db.config.unlink_tts(source_id, assignment.component)


async def _list_tts_assignments(source_id: str, db: db_dep) -> list[ComponentTtsConfig]:
    configs = await db.config.list_ttss_by_source(source_id)
    return [
        ComponentTtsConfig(component=component, config=config)
        for component, config in configs.items()
    ]


async def _apply_image_assignments(source_id: str, assignments: list[ComponentModelConfigUpdate], db: db_dep):
    for assignment in assignments:
        if assignment.config_id:
            if not await db.config.get_image(assignment.config_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Image config {assignment.config_id} not found",
                )
            await db.config.link_image(source_id, assignment.config_id, assignment.component)
        else:
            await db.config.unlink_image(source_id, assignment.component)


async def _list_image_assignments(source_id: str, db: db_dep) -> list[ComponentImageConfig]:
    configs = await db.config.list_images_by_source(source_id)
    return [
        ComponentImageConfig(component=component, config=config)
        for component, config in configs.items()
    ]


async def _list_chat_assignments(source_id: str, db: db_dep) -> list[ComponentChatConfig]:
    configs = await db.config.list_chats_by_source(source_id)
    return [
        ComponentChatConfig(component=component, config=config)
        for component, config in configs.items()
    ]


async def _list_embed_assignments(source_id: str, db: db_dep) -> list[ComponentEmbedConfig]:
    configs = await db.config.list_embeds_by_source(source_id)
    return [
        ComponentEmbedConfig(component=component, config=config)
        for component, config in configs.items()
    ]


@config_router.get("/config/connections", response_model=list[ConnectionConfig])
async def list_connections(db: db_dep):
    return await db.config.list_connections()


@config_router.post("/config/connections", response_model=ConnectionConfig)
async def create_connection(connection_config: ConnectionConfig, db: db_dep):
    return await db.config.create_connection(connection_config)


@config_router.get("/config/connections/{connection_id}", response_model=ConnectionConfig)
async def get_connection(connection_id: str, db: db_dep):
    connection = await db.config.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_id} not found",
        )

    return connection


@config_router.patch("/config/connections/{connection_id}", response_model=ConnectionConfig)
async def update_connection(connection_id: str, connection_update: ConnectionUpdate, db: db_dep):
    connection = await db.config.update_connection(
        connection_id,
        connection_update.model_dump(exclude_unset=True),
    )
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_id} not found",
        )

    return connection


@config_router.delete("/config/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: str, db: db_dep):
    deleted = await db.config.delete_connection(connection_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_id} not found",
        )


@config_router.get("/config/connections/{connection_id}/alltalk-status", response_model=AllTalkStatus)
async def get_alltalk_connection_status(connection_id: str, db: db_dep):
    """
    Proxy AllTalk V2's live currently-loaded engine/model, capabilities, and voices for the given
    connection. This app never changes AllTalk's own engine/model configuration - editors use this to know
    which inference-time fields are valid and which voices actually exist on the server, instead of
    guessing from a hardcoded list.
    """
    connection = await db.config.get_connection(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_id} not found",
        )
    if connection.type != ConnectionType.ALLTALK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection {connection_id} is not an AllTalk connection",
        )

    try:
        raw_status = await TtsAllTalkV2(base_url=connection.base_url).get_status()
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to reach AllTalk server: {exc}",
        ) from exc

    return AllTalkStatus(**raw_status)


@config_router.get("/config/llm", response_model=list[ChatModelConfigUnion], response_model_exclude_none=True)
async def list_chat_configs(db: db_dep):
    return await db.config.list_chats()


@config_router.post("/config/llm", response_model=ChatModelConfigUnion, response_model_exclude_none=True)
async def create_chat_config(chat_config: ChatModelConfigUnion, db: db_dep):
    return await db.config.create_chat(chat_config)


@config_router.post("/config/llm/ollama", response_model=OllamaChatModelConfig, response_model_exclude_none=True)
async def create_ollama_chat_config(chat_config: OllamaChatModelConfig, db: db_dep):
    return await db.config.create_chat(chat_config)


@config_router.post("/config/llm/openai", response_model=OpenAiChatModelConfig, response_model_exclude_none=True)
async def create_openai_chat_config(chat_config: OpenAiChatModelConfig, db: db_dep):
    return await db.config.create_chat(chat_config)


@config_router.get("/config/llm/{config_id}", response_model=ChatModelConfigUnion, response_model_exclude_none=True)
async def get_chat_config(config_id: str, db: db_dep):
    chat_config = await db.config.get_chat(config_id)
    if not chat_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )

    return chat_config


@config_router.patch("/config/llm/{config_id}", response_model=ChatModelConfigUnion, response_model_exclude_none=True)
async def update_chat_config(config_id: str, chat_update: ChatConfigUpdate, db: db_dep):
    chat_config = await db.config.update_chat(
        config_id,
        chat_update.model_dump(exclude_unset=True),
    )
    if not chat_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )

    return chat_config


@config_router.delete("/config/llm/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_config(config_id: str, db: db_dep):
    deleted = await db.config.delete_chat(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )


@config_router.put("/config/llm/{config_id}/connection", response_model=ConnectionConfig)
async def set_chat_config_connection(config_id: str, connection_update: ConfigConnectionUpdate, db: db_dep):
    if not await db.config.get_chat(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )
    if not await db.config.get_connection(connection_update.connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_update.connection_id} not found",
        )

    return await db.config.link_connection(config_id, connection_update.connection_id)


@config_router.get("/config/llm/{config_id}/connection", response_model=ConnectionConfig)
async def get_chat_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_chat(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )

    connection = await db.config.get_connection_by_source(config_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection for LLM config {config_id} not found",
        )

    return connection


@config_router.delete("/config/llm/{config_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_chat(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )

    deleted = await db.config.unlink_connection(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )


@config_router.get("/config/embeddings", response_model=list[EmbedModelConfigUnion], response_model_exclude_none=True)
async def list_embed_configs(db: db_dep):
    return await db.config.list_embeds()


@config_router.post("/config/embeddings/ollama", response_model=OllamaEmbedModelConfig, response_model_exclude_none=True)
async def create_ollama_embed_config(embed_config: OllamaEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post("/config/embeddings/openai", response_model=OpenAiEmbedModelConfig, response_model_exclude_none=True)
async def create_openai_embed_config(embed_config: OpenAiEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post(
    "/config/embeddings/google_genai",
    response_model=GoogleGenAiEmbedModelConfig,
    response_model_exclude_none=True,
)
async def create_google_genai_embed_config(embed_config: GoogleGenAiEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post(
    "/config/embeddings/mistralai",
    response_model=MistralAiEmbedModelConfig,
    response_model_exclude_none=True,
)
async def create_mistralai_embed_config(embed_config: MistralAiEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post("/config/embeddings/cohere", response_model=CohereEmbedModelConfig, response_model_exclude_none=True)
async def create_cohere_embed_config(embed_config: CohereEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post(
    "/config/embeddings/perplexity",
    response_model=PerplexityEmbedModelConfig,
    response_model_exclude_none=True,
)
async def create_perplexity_embed_config(embed_config: PerplexityEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post(
    "/config/embeddings/cloudflare",
    response_model=CloudflareEmbedModelConfig,
    response_model_exclude_none=True,
)
async def create_cloudflare_embed_config(embed_config: CloudflareEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.get(
    "/config/embeddings/{config_id}",
    response_model=EmbedModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_embed_config(config_id: str, db: db_dep):
    embed_config = await db.config.get_embed(config_id)
    if not embed_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )

    return embed_config


@config_router.patch(
    "/config/embeddings/{config_id}",
    response_model=EmbedModelConfigUnion,
    response_model_exclude_none=True,
)
async def update_embed_config(config_id: str, embed_update: EmbedConfigUpdate, db: db_dep):
    embed_config = await db.config.update_embed(
        config_id,
        embed_update.model_dump(exclude_unset=True),
    )
    if not embed_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )

    return embed_config


@config_router.delete("/config/embeddings/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_embed_config(config_id: str, db: db_dep):
    deleted = await db.config.delete_embed(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )


@config_router.put("/config/embeddings/{config_id}/connection", response_model=ConnectionConfig)
async def set_embed_config_connection(config_id: str, connection_update: ConfigConnectionUpdate, db: db_dep):
    if not await db.config.get_embed(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )
    if not await db.config.get_connection(connection_update.connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_update.connection_id} not found",
        )

    return await db.config.link_connection(config_id, connection_update.connection_id)


@config_router.get("/config/embeddings/{config_id}/connection", response_model=ConnectionConfig)
async def get_embed_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_embed(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )

    connection = await db.config.get_connection_by_embed_source(config_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection for embedding config {config_id} not found",
        )

    return connection


@config_router.delete("/config/embeddings/{config_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_embed_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_embed(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )

    deleted = await db.config.unlink_connection(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )


@config_router.get("/config/tts", response_model=list[TtsModelConfigUnion], response_model_exclude_none=True)
async def list_tts_configs(db: db_dep):
    return await db.config.list_ttss()


@config_router.post(
    "/config/tts/alltalk/xtts", response_model=AllTalkXttsModelConfig, response_model_exclude_none=True,
)
async def create_alltalk_xtts_config(tts_config: AllTalkXttsModelConfig, db: db_dep):
    return await db.config.create_tts(tts_config)


@config_router.post(
    "/config/tts/alltalk/piper", response_model=AllTalkPiperModelConfig, response_model_exclude_none=True,
)
async def create_alltalk_piper_config(tts_config: AllTalkPiperModelConfig, db: db_dep):
    return await db.config.create_tts(tts_config)


@config_router.post(
    "/config/tts/alltalk/vits", response_model=AllTalkVitsModelConfig, response_model_exclude_none=True,
)
async def create_alltalk_vits_config(tts_config: AllTalkVitsModelConfig, db: db_dep):
    return await db.config.create_tts(tts_config)


@config_router.post(
    "/config/tts/alltalk/parler", response_model=AllTalkParlerModelConfig, response_model_exclude_none=True,
)
async def create_alltalk_parler_config(tts_config: AllTalkParlerModelConfig, db: db_dep):
    return await db.config.create_tts(tts_config)


@config_router.post(
    "/config/tts/alltalk/f5tts", response_model=AllTalkF5ttsModelConfig, response_model_exclude_none=True,
)
async def create_alltalk_f5tts_config(tts_config: AllTalkF5ttsModelConfig, db: db_dep):
    return await db.config.create_tts(tts_config)


@config_router.get("/config/tts/{config_id}", response_model=TtsModelConfigUnion, response_model_exclude_none=True)
async def get_tts_config(config_id: str, db: db_dep):
    tts_config = await db.config.get_tts(config_id)
    if not tts_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )

    return tts_config


@config_router.patch(
    "/config/tts/{config_id}", response_model=TtsModelConfigUnion, response_model_exclude_none=True,
)
async def update_tts_config(config_id: str, tts_update: TtsConfigUpdate, db: db_dep):
    tts_config = await db.config.update_tts(
        config_id,
        tts_update.model_dump(exclude_unset=True),
    )
    if not tts_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )

    return tts_config


@config_router.delete("/config/tts/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tts_config(config_id: str, db: db_dep):
    deleted = await db.config.delete_tts(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )


@config_router.put("/config/tts/{config_id}/connection", response_model=ConnectionConfig)
async def set_tts_config_connection(config_id: str, connection_update: ConfigConnectionUpdate, db: db_dep):
    if not await db.config.get_tts(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )
    if not await db.config.get_connection(connection_update.connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_update.connection_id} not found",
        )

    return await db.config.link_connection(config_id, connection_update.connection_id)


@config_router.get("/config/tts/{config_id}/connection", response_model=ConnectionConfig)
async def get_tts_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_tts(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )

    connection = await db.config.get_connection_by_tts_source(config_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection for TTS config {config_id} not found",
        )

    return connection


@config_router.delete("/config/tts/{config_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tts_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_tts(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )

    deleted = await db.config.unlink_connection(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_id} not found",
        )


@config_router.get("/config/images", response_model=list[ImageModelConfigUnion], response_model_exclude_none=True)
async def list_image_configs(db: db_dep):
    return await db.config.list_images()


@config_router.post(
    "/config/images/comfyui", response_model=ComfyUiImageModelConfig, response_model_exclude_none=True,
)
async def create_comfyui_image_config(image_config: ComfyUiImageModelConfig, db: db_dep):
    return await db.config.create_image(image_config)


@config_router.get(
    "/config/images/{config_id}", response_model=ImageModelConfigUnion, response_model_exclude_none=True,
)
async def get_image_config(config_id: str, db: db_dep):
    image_config = await db.config.get_image(config_id)
    if not image_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )

    return image_config


@config_router.patch(
    "/config/images/{config_id}", response_model=ImageModelConfigUnion, response_model_exclude_none=True,
)
async def update_image_config(config_id: str, image_update: ImageConfigUpdate, db: db_dep):
    image_config = await db.config.update_image(
        config_id,
        image_update.model_dump(exclude_unset=True),
    )
    if not image_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )

    return image_config


@config_router.delete("/config/images/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image_config(config_id: str, db: db_dep):
    deleted = await db.config.delete_image(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )


@config_router.put("/config/images/{config_id}/connection", response_model=ConnectionConfig)
async def set_image_config_connection(config_id: str, connection_update: ConfigConnectionUpdate, db: db_dep):
    if not await db.config.get_image(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )
    if not await db.config.get_connection(connection_update.connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_update.connection_id} not found",
        )

    return await db.config.link_connection(config_id, connection_update.connection_id)


@config_router.get("/config/images/{config_id}/connection", response_model=ConnectionConfig)
async def get_image_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_image(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )

    connection = await db.config.get_connection_by_image_source(config_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection for image config {config_id} not found",
        )

    return connection


@config_router.delete("/config/images/{config_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_image(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )

    deleted = await db.config.unlink_connection(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_id} not found",
        )


@config_router.get("/config/stt", response_model=list[SttModelConfigUnion], response_model_exclude_none=True)
async def list_stt_configs(db: db_dep):
    return await db.config.list_stts()


@config_router.post(
    "/config/stt/whispercpp", response_model=WhisperCppSttModelConfig, response_model_exclude_none=True,
)
async def create_whisper_cpp_stt_config(stt_config: WhisperCppSttModelConfig, db: db_dep):
    return await db.config.create_stt(stt_config)


@config_router.get("/config/stt/{config_id}", response_model=SttModelConfigUnion, response_model_exclude_none=True)
async def get_stt_config(config_id: str, db: db_dep):
    stt_config = await db.config.get_stt(config_id)
    if not stt_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )

    return stt_config


@config_router.patch(
    "/config/stt/{config_id}", response_model=SttModelConfigUnion, response_model_exclude_none=True,
)
async def update_stt_config(config_id: str, stt_update: SttConfigUpdate, db: db_dep):
    stt_config = await db.config.update_stt(
        config_id,
        stt_update.model_dump(exclude_unset=True),
    )
    if not stt_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )

    return stt_config


@config_router.delete("/config/stt/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stt_config(config_id: str, db: db_dep):
    deleted = await db.config.delete_stt(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )


@config_router.put("/config/stt/{config_id}/connection", response_model=ConnectionConfig)
async def set_stt_config_connection(config_id: str, connection_update: ConfigConnectionUpdate, db: db_dep):
    if not await db.config.get_stt(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )
    if not await db.config.get_connection(connection_update.connection_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection config {connection_update.connection_id} not found",
        )

    return await db.config.link_connection(config_id, connection_update.connection_id)


@config_router.get("/config/stt/{config_id}/connection", response_model=ConnectionConfig)
async def get_stt_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_stt(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )

    connection = await db.config.get_connection_by_stt_source(config_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection for STT config {config_id} not found",
        )

    return connection


@config_router.delete("/config/stt/{config_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stt_config_connection(config_id: str, db: db_dep):
    if not await db.config.get_stt(config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )

    deleted = await db.config.unlink_connection(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STT config {config_id} not found",
        )


@config_router.put(
    "/simulations/{simulation_id}/llm-connection",
    response_model=ChatModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_simulation_llm_connection(
        simulation_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    if not await db.config.get_chat(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_update.config_id} not found",
        )

    return await db.config.link_chat(
        simulation_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/simulations/{simulation_id}/llm-connections",
    response_model=list[ComponentChatConfig],
    response_model_exclude_none=True,
)
async def list_simulation_llm_connections(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)
    return await _list_chat_assignments(simulation_id, db)


@config_router.put(
    "/simulations/{simulation_id}/llm-connections",
    response_model=list[ComponentChatConfig],
    response_model_exclude_none=True,
)
async def set_simulation_llm_connections(
        simulation_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)
    await _apply_chat_assignments(simulation_id, config_update.assignments, db)
    return await _list_chat_assignments(simulation_id, db)


@config_router.get(
    "/simulations/{simulation_id}/llm-connection",
    response_model=ChatModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_simulation_llm_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    chat_config = await db.config.get_chat_by_source(simulation_id, component)
    if not chat_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config for simulation {simulation_id} and component {component} not found",
        )

    return chat_config


@config_router.delete("/simulations/{simulation_id}/llm-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation_llm_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    deleted = await db.config.unlink_chat(simulation_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@config_router.put(
    "/simulations/{simulation_id}/embedding-connection",
    response_model=EmbedModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_simulation_embedding_connection(
        simulation_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    if not await db.config.get_embed(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_update.config_id} not found",
        )

    return await db.config.link_embed(
        simulation_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/simulations/{simulation_id}/embedding-connections",
    response_model=list[ComponentEmbedConfig],
    response_model_exclude_none=True,
)
async def list_simulation_embedding_connections(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)
    return await _list_embed_assignments(simulation_id, db)


@config_router.put(
    "/simulations/{simulation_id}/embedding-connections",
    response_model=list[ComponentEmbedConfig],
    response_model_exclude_none=True,
)
async def set_simulation_embedding_connections(
        simulation_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)
    await _apply_embed_assignments(simulation_id, config_update.assignments, db)
    return await _list_embed_assignments(simulation_id, db)


@config_router.get(
    "/simulations/{simulation_id}/embedding-connection",
    response_model=EmbedModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_simulation_embedding_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    embed_config = await db.config.get_embed_by_source(simulation_id, component)
    if not embed_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config for simulation {simulation_id} and component {component} not found",
        )

    return embed_config


@config_router.delete("/simulations/{simulation_id}/embedding-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation_embedding_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    deleted = await db.config.unlink_embed(simulation_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@config_router.put(
    "/simulations/{simulation_id}/tts-connection",
    response_model=TtsModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_simulation_tts_connection(
        simulation_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    if not await db.config.get_tts(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_update.config_id} not found",
        )

    return await db.config.link_tts(
        simulation_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/simulations/{simulation_id}/tts-connections",
    response_model=list[ComponentTtsConfig],
    response_model_exclude_none=True,
)
async def list_simulation_tts_connections(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)
    return await _list_tts_assignments(simulation_id, db)


@config_router.put(
    "/simulations/{simulation_id}/tts-connections",
    response_model=list[ComponentTtsConfig],
    response_model_exclude_none=True,
)
async def set_simulation_tts_connections(
        simulation_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)
    await _apply_tts_assignments(simulation_id, config_update.assignments, db)
    return await _list_tts_assignments(simulation_id, db)


@config_router.get(
    "/simulations/{simulation_id}/tts-connection",
    response_model=TtsModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_simulation_tts_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    tts_config = await db.config.get_tts_by_source(simulation_id, component)
    if not tts_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config for simulation {simulation_id} and component {component} not found",
        )

    return tts_config


@config_router.delete("/simulations/{simulation_id}/tts-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation_tts_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    deleted = await db.config.unlink_tts(simulation_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@config_router.put(
    "/simulations/{simulation_id}/image-connection",
    response_model=ImageModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_simulation_image_connection(
        simulation_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )
    if not await db.config.get_image(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_update.config_id} not found",
        )

    return await db.config.link_image(
        simulation_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/simulations/{simulation_id}/image-connections",
    response_model=list[ComponentImageConfig],
    response_model_exclude_none=True,
)
async def list_simulation_image_connections(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)
    return await _list_image_assignments(simulation_id, db)


@config_router.put(
    "/simulations/{simulation_id}/image-connections",
    response_model=list[ComponentImageConfig],
    response_model_exclude_none=True,
)
async def set_simulation_image_connections(
        simulation_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)
    await _apply_image_assignments(simulation_id, config_update.assignments, db)
    return await _list_image_assignments(simulation_id, db)


@config_router.get(
    "/simulations/{simulation_id}/image-connection",
    response_model=ImageModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_simulation_image_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    image_config = await db.config.get_image_by_source(simulation_id, component)
    if not image_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config for simulation {simulation_id} and component {component} not found",
        )

    return image_config


@config_router.delete("/simulations/{simulation_id}/image-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation_image_connection(
        simulation_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The simulation component using the config"),
):
    if not await db.simulation.get_simulation(simulation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )

    deleted = await db.config.unlink_image(simulation_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found",
        )


@config_router.put(
    "/worlds/{world_id}/llm-connection",
    response_model=ChatModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_world_llm_connection(
        world_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
    if not await db.config.get_chat(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_update.config_id} not found",
        )

    return await db.config.link_chat(
        world_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/worlds/{world_id}/llm-connections",
    response_model=list[ComponentChatConfig],
    response_model_exclude_none=True,
)
async def list_world_llm_connections(world_id: str, db: db_dep):
    await _validate_world(world_id, db)
    return await _list_chat_assignments(world_id, db)


@config_router.put(
    "/worlds/{world_id}/llm-connections",
    response_model=list[ComponentChatConfig],
    response_model_exclude_none=True,
)
async def set_world_llm_connections(
        world_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_world(world_id, db)
    await _apply_chat_assignments(world_id, config_update.assignments, db)
    return await _list_chat_assignments(world_id, db)


@config_router.get(
    "/worlds/{world_id}/llm-connection",
    response_model=ChatModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_world_llm_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    chat_config = await db.config.get_chat_by_source(world_id, component)
    if not chat_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config for world {world_id} and component {component} not found",
        )

    return chat_config


@config_router.delete("/worlds/{world_id}/llm-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_llm_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    deleted = await db.config.unlink_chat(world_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


@config_router.put(
    "/worlds/{world_id}/embedding-connection",
    response_model=EmbedModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_world_embedding_connection(
        world_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
    if not await db.config.get_embed(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_update.config_id} not found",
        )

    return await db.config.link_embed(
        world_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/worlds/{world_id}/embedding-connections",
    response_model=list[ComponentEmbedConfig],
    response_model_exclude_none=True,
)
async def list_world_embedding_connections(world_id: str, db: db_dep):
    await _validate_world(world_id, db)
    return await _list_embed_assignments(world_id, db)


@config_router.put(
    "/worlds/{world_id}/embedding-connections",
    response_model=list[ComponentEmbedConfig],
    response_model_exclude_none=True,
)
async def set_world_embedding_connections(
        world_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_world(world_id, db)
    await _apply_embed_assignments(world_id, config_update.assignments, db)
    return await _list_embed_assignments(world_id, db)


@config_router.get(
    "/worlds/{world_id}/embedding-connection",
    response_model=EmbedModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_world_embedding_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    embed_config = await db.config.get_embed_by_source(world_id, component)
    if not embed_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config for world {world_id} and component {component} not found",
        )

    return embed_config


@config_router.delete("/worlds/{world_id}/embedding-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_embedding_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    deleted = await db.config.unlink_embed(world_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


@config_router.put(
    "/worlds/{world_id}/tts-connection",
    response_model=TtsModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_world_tts_connection(
        world_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
    if not await db.config.get_tts(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config {config_update.config_id} not found",
        )

    return await db.config.link_tts(
        world_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/worlds/{world_id}/tts-connections",
    response_model=list[ComponentTtsConfig],
    response_model_exclude_none=True,
)
async def list_world_tts_connections(world_id: str, db: db_dep):
    await _validate_world(world_id, db)
    return await _list_tts_assignments(world_id, db)


@config_router.put(
    "/worlds/{world_id}/tts-connections",
    response_model=list[ComponentTtsConfig],
    response_model_exclude_none=True,
)
async def set_world_tts_connections(
        world_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_world(world_id, db)
    await _apply_tts_assignments(world_id, config_update.assignments, db)
    return await _list_tts_assignments(world_id, db)


@config_router.get(
    "/worlds/{world_id}/tts-connection",
    response_model=TtsModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_world_tts_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    tts_config = await db.config.get_tts_by_source(world_id, component)
    if not tts_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TTS config for world {world_id} and component {component} not found",
        )

    return tts_config


@config_router.delete("/worlds/{world_id}/tts-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_tts_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    deleted = await db.config.unlink_tts(world_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


@config_router.put(
    "/worlds/{world_id}/image-connection",
    response_model=ImageModelConfigUnion,
    response_model_exclude_none=True,
)
async def set_world_image_connection(
        world_id: str,
        config_update: SimulationModelConfigUpdate,
        db: db_dep,
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )
    if not await db.config.get_image(config_update.config_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config {config_update.config_id} not found",
        )

    return await db.config.link_image(
        world_id,
        config_update.config_id,
        config_update.component,
    )


@config_router.get(
    "/worlds/{world_id}/image-connections",
    response_model=list[ComponentImageConfig],
    response_model_exclude_none=True,
)
async def list_world_image_connections(world_id: str, db: db_dep):
    await _validate_world(world_id, db)
    return await _list_image_assignments(world_id, db)


@config_router.put(
    "/worlds/{world_id}/image-connections",
    response_model=list[ComponentImageConfig],
    response_model_exclude_none=True,
)
async def set_world_image_connections(
        world_id: str,
        config_update: ComponentModelConfigBatchUpdate,
        db: db_dep,
):
    await _validate_world(world_id, db)
    await _apply_image_assignments(world_id, config_update.assignments, db)
    return await _list_image_assignments(world_id, db)


@config_router.get(
    "/worlds/{world_id}/image-connection",
    response_model=ImageModelConfigUnion,
    response_model_exclude_none=True,
)
async def get_world_image_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    image_config = await db.config.get_image_by_source(world_id, component)
    if not image_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image config for world {world_id} and component {component} not found",
        )

    return image_config


@config_router.delete("/worlds/{world_id}/image-connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_image_connection(
        world_id: str,
        db: db_dep,
        component: ComponentType = Query(..., description="The world component using the config"),
):
    if not await db.world.get_world(world_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )

    deleted = await db.config.unlink_image(world_id, component)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} not found",
        )


@config_router.get(
    "/simulations/{simulation_id}/image-generation-config",
    response_model=ImageGenerationConfig,
)
async def get_simulation_image_generation_config(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)

    config = await db.config.get_image_generation_config(simulation_id)
    return config or ImageGenerationConfig()


@config_router.put(
    "/simulations/{simulation_id}/image-generation-config",
    response_model=ImageGenerationConfig,
)
async def set_simulation_image_generation_config(
        simulation_id: str,
        config_update: ImageGenerationConfigUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)

    existing = await db.config.get_image_generation_config(simulation_id)
    config = ImageGenerationConfig(
        id=existing.id if existing else str(uuid4()),
        mode=config_update.mode,
        fallback_turns=config_update.fallback_turns,
    )
    return await db.config.set_image_generation_config(simulation_id, config)


@config_router.get(
    "/simulations/{simulation_id}/tts-generation-config",
    response_model=TtsGenerationConfig,
)
async def get_simulation_tts_generation_config(simulation_id: str, db: db_dep):
    await _validate_simulation(simulation_id, db)

    config = await db.config.get_tts_generation_config(simulation_id)
    return config or TtsGenerationConfig()


@config_router.put(
    "/simulations/{simulation_id}/tts-generation-config",
    response_model=TtsGenerationConfig,
)
async def set_simulation_tts_generation_config(
        simulation_id: str,
        config_update: TtsGenerationConfigUpdate,
        db: db_dep,
):
    await _validate_simulation(simulation_id, db)

    existing = await db.config.get_tts_generation_config(simulation_id)
    config = TtsGenerationConfig(
        id=existing.id if existing else str(uuid4()),
        mode=config_update.mode,
        autoplay_in_browser=config_update.autoplay_in_browser,
        narrator_voice=config_update.narrator_voice,
        rvc_narrator_voice=config_update.rvc_narrator_voice,
        rvc_narrator_pitch=config_update.rvc_narrator_pitch,
    )
    return await db.config.set_tts_generation_config(simulation_id, config)
