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

    sillytavern_image_download_max_concurrency: int = Field(
        4,
        description="Maximum number of concurrent outbound HEAD/GET requests when probing or "
                    "downloading image links found in a SillyTavern card."
    )
    sillytavern_image_download_max_bytes: int = Field(
        10 * 1024 * 1024,
        description="Maximum response body size accepted when downloading a candidate image link, "
                    "enforced both against Content-Length and against the actual bytes streamed."
    )
    sillytavern_image_download_connect_timeout: float = Field(
        5.0,
        description="Connect timeout, in seconds, for outbound image link HEAD/GET requests."
    )
    sillytavern_image_download_read_timeout: float = Field(
        10.0,
        description="Read timeout, in seconds, for outbound image link GET requests."
    )
    sillytavern_image_download_head_timeout: float = Field(
        5.0,
        description="Total timeout, in seconds, for the cheaper HEAD probe used to decide whether "
                    "a non-whitelisted image link is worth showing the user for review."
    )
    sillytavern_image_download_max_redirects: int = Field(
        3,
        description="Maximum number of redirect hops followed when downloading a candidate image "
                    "link. Each hop's target is re-validated against the SSRF filter before being "
                    "followed, never just the original URL."
    )


CONFIG = Settings(_env_file=os.getenv('WSE_ENV_FILE', '.env'))      # type: ignore
