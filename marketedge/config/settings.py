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

    # Matched case-insensitively against each connector's own catalogue
    # names, not a private taxonomy — Betfair's eventType.name and The Odds
    # API's sport `group` both say "Soccer"/"Tennis", not "football"/"tennis".
    # Override via env as a JSON array, e.g. SPORTS_ENABLED=["Soccer"].
    sports_enabled: tuple[str, ...] = Field(default=("Soccer", "Tennis"), alias="SPORTS_ENABLED")

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

    # --- Bookmaker odds provider (The Odds API — see spec section 41.1) ---
    # Pricing/plan sizes are external, configurable facts, never hard-coded
    # product assumptions (spec section 41.1).
    odds_provider_api_key: str = Field(default="", alias="ODDS_PROVIDER_API_KEY")
    odds_provider_base_url: str = Field(
        default="https://api.the-odds-api.com/v4", alias="ODDS_PROVIDER_BASE_URL"
    )
    odds_provider_regions: str = Field(default="uk", alias="ODDS_PROVIDER_REGIONS")
    odds_provider_markets: str = Field(default="h2h", alias="ODDS_PROVIDER_MARKETS")

    @property
    def odds_provider_configured(self) -> bool:
        return bool(self.odds_provider_api_key)

    # --- API-credit budget (spec section 41.2/41.6) ---
    # Both are monthly caps; the scheduler degrades polling cadence as the
    # soft cap approaches and stops discovery calls entirely at the hard cap.
    odds_provider_soft_monthly_budget: int = Field(
        default=18_000, alias="ODDS_PROVIDER_SOFT_MONTHLY_BUDGET"
    )
    odds_provider_hard_monthly_budget: int = Field(
        default=20_000, alias="ODDS_PROVIDER_HARD_MONTHLY_BUDGET"
    )

    # --- Adaptive discovery polling (spec section 41.3 defaults) ---
    discovery_poll_seconds_gt_24h: int = Field(default=1800, alias="DISCOVERY_POLL_SECONDS_GT_24H")
    discovery_poll_seconds_6h_24h: int = Field(default=600, alias="DISCOVERY_POLL_SECONDS_6H_24H")
    discovery_poll_seconds_1h_6h: int = Field(default=180, alias="DISCOVERY_POLL_SECONDS_1H_6H")
    discovery_poll_seconds_lt_1h: int = Field(default=60, alias="DISCOVERY_POLL_SECONDS_LT_1H")


@lru_cache
def get_settings() -> Settings:
    return Settings()
