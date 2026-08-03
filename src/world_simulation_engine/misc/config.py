import os
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WSE_",
        env_file_encoding="utf-8",
    )

    app_host: str = Field(
        "127.0.0.1",
        description="Host for the local server. Only relevant if using the start script."
    )
    app_port: int = Field(
        9797,
        description="Port for the local server. Only relevant if using the start script."
    )
    logging_level: Literal['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'] = Field(
        "INFO",
        description="Logging level for the application"
    )

    neo4j_uri: str = Field(
        "bolt://localhost:7687",
        description="URI for the Neo4j server"
    )
    neo4j_username: str = Field(
        "neo4j",
        description="Username for the Neo4j server"
    )
    neo4j_password: str = Field(
        ...,
        description="Password for the Neo4j server"
    )

    data_folder: str = Field(
        "data/storage",
        description="Folder where the media data is stored"
    )

    tts_max_concurrency: int = Field(
        3,
        description="Maximum number of concurrent outbound TTS generation requests to the backend"
    )
    tts_media_retention_turns: int = Field(
        50,
        description="How many most-recent turns' generated voice media to keep per simulation, "
                    "before older ones are automatically pruned"
    )

    sillytavern_import_max_concurrency: int = Field(
        4,
        description="Maximum number of concurrent LLM calls within one stage of the SillyTavern "
                    "card import pipeline (e.g. classifying many lorebook entries at once). "
                    "Passed as LangGraph's own `max_concurrency` run config, so it throttles "
                    "Send-dispatched fan-out directly rather than via a separate semaphore."
    )


CONFIG = Settings(_env_file=os.getenv('WSE_ENV_FILE', '.env'))      # type: ignore
