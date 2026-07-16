from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType, ConnectionType
from world_simulation_engine.model import ConnectionConfig, OllamaChatModelConfig, OpenAiChatModelConfig, \
    ChatModelConfigUnion, OllamaEmbedModelConfig, OpenAiEmbedModelConfig, EmbedModelConfigUnion
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

    name: Optional[str] = Field(None, description="The name of the chat config")
    model: Optional[str] = Field(None, description="The model to use for the chat")
    temperature: Optional[float] = Field(None, description="The temperature to use for the chat")
    context_window: Optional[int] = Field(None, description="The context window to use for the chat")
    seed: Optional[int] = Field(None, description="The seed to use for the chat")
    reasoning: Optional[str | bool] = Field(None, description="Whether to enable reasoning for the chat")
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

    model: Optional[str] = Field(None, description="The model to use for embedding")
    dimension: Optional[int] = Field(None, description="The dimensionality of the model")
    context_window: Optional[int] = Field(None, description="The context window to use for embedding")


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


@config_router.get("/config/llm", response_model=list[ChatModelConfigUnion])
async def list_chat_configs(db: db_dep):
    return await db.config.list_chats()


@config_router.post("/config/llm/ollama", response_model=OllamaChatModelConfig)
async def create_ollama_chat_config(chat_config: OllamaChatModelConfig, db: db_dep):
    return await db.config.create_chat(chat_config)


@config_router.post("/config/llm/openai", response_model=OpenAiChatModelConfig)
async def create_openai_chat_config(chat_config: OpenAiChatModelConfig, db: db_dep):
    return await db.config.create_chat(chat_config)


@config_router.get("/config/llm/{config_id}", response_model=ChatModelConfigUnion)
async def get_chat_config(config_id: str, db: db_dep):
    chat_config = await db.config.get_chat(config_id)
    if not chat_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM config {config_id} not found",
        )

    return chat_config


@config_router.patch("/config/llm/{config_id}", response_model=ChatModelConfigUnion)
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


@config_router.get("/config/embeddings", response_model=list[EmbedModelConfigUnion])
async def list_embed_configs(db: db_dep):
    return await db.config.list_embeds()


@config_router.post("/config/embeddings/ollama", response_model=OllamaEmbedModelConfig)
async def create_ollama_embed_config(embed_config: OllamaEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.post("/config/embeddings/openai", response_model=OpenAiEmbedModelConfig)
async def create_openai_embed_config(embed_config: OpenAiEmbedModelConfig, db: db_dep):
    return await db.config.create_embed(embed_config)


@config_router.get("/config/embeddings/{config_id}", response_model=EmbedModelConfigUnion)
async def get_embed_config(config_id: str, db: db_dep):
    embed_config = await db.config.get_embed(config_id)
    if not embed_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Embedding config {config_id} not found",
        )

    return embed_config


@config_router.patch("/config/embeddings/{config_id}", response_model=EmbedModelConfigUnion)
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


@config_router.put("/simulations/{simulation_id}/llm-connection", response_model=ChatModelConfigUnion)
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


@config_router.get("/simulations/{simulation_id}/llm-connection", response_model=ChatModelConfigUnion)
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


@config_router.put("/simulations/{simulation_id}/embedding-connection", response_model=EmbedModelConfigUnion)
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


@config_router.get("/simulations/{simulation_id}/embedding-connection", response_model=EmbedModelConfigUnion)
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
