import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='WSE_',
        env_file_encoding='utf-8',
    )

    app_host: str = Field(
        '127.0.0.1',
        description='Host for the local server. Only relevant if using the start script.'
    )
    app_port: int = Field(
        9797,
        description='Port for the local server. Only relevant if using the start script.'
    )

    database_path: str = Field(
        "data/database.db",
        description='Path to the SQLite database file.'
    )


CONFIG = Settings(_env_file=os.getenv('WSE_ENV_FILE', '.env'))      # type: ignore
