"""Typed application settings (env-driven via pydantic-settings).

Loads from `.env` at the repo root; values can be overridden by environment
variables. Phase 1 ships the seven fields the v1 stack will consume; later
phases extend the Settings class additively.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """v1 application settings.

    Fields below are populated from `.env` (gitignored) or process env vars.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # External-service credentials
    FINNHUB_API_KEY: str = ""
    FRED_API_KEY: str = ""
    EDGAR_IDENTITY: str = ""

    # Universe selection
    UNIVERSE: str = "russell1000"

    # Indicator + sizing parameters
    RS_LOOKBACK_DAYS: int = 252
    RISK_PCT_PER_TRADE: float = 0.0075
    ACCOUNT_EQUITY: float = 100_000.0


settings = Settings()
