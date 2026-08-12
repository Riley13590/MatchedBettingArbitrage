"""Application configuration.

Single source of truth for environment-derived config. Nothing outside this
module should call `os.environ` directly (spec section 29 discourages
scattering config access).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_mode: str = Field(default="PAPER", alias="APP_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+asyncpg://marketedge:marketedge@localhost:5432/marketedge",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    sports_enabled: tuple[str, ...] = ("football", "tennis")

    # --- Betfair ---
    betfair_app_key: str = Field(default="", alias="BETFAIR_APP_KEY")
    betfair_username: str = Field(default="", alias="BETFAIR_USERNAME")
    betfair_password: str = Field(default="", alias="BETFAIR_PASSWORD")
    betfair_cert_path: str = Field(default="", alias="BETFAIR_CERT_PATH")
    betfair_key_path: str = Field(default="", alias="BETFAIR_KEY_PATH")
    betfair_identity_url: str = Field(
        default="https://identitysso-cert.betfair.com/api/certlogin",
        alias="BETFAIR_IDENTITY_URL",
    )
    betfair_api_url: str = Field(
        default="https://api.betfair.com/exchange/betting/json-rpc/v1",
        alias="BETFAIR_API_URL",
    )
    betfair_stream_host: str = Field(default="stream-api.betfair.com", alias="BETFAIR_STREAM_HOST")
    betfair_stream_port: int = Field(default=443, alias="BETFAIR_STREAM_PORT")
    betfair_execution_allowed: bool = Field(default=False, alias="BETFAIR_EXECUTION_ALLOWED")

    @property
    def betfair_credentials_configured(self) -> bool:
        return bool(
            self.betfair_app_key
            and self.betfair_username
            and self.betfair_password
            and self.betfair_cert_path
            and self.betfair_key_path
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
