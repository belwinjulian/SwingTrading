"""Typed application settings (env-driven via pydantic-settings).

Loads from `.env` at the repo root; values can be overridden by environment
variables. Phase 1 ships the seven fields the v1 stack will consume; later
phases extend the Settings class additively.

Settings are constructed lazily via :func:`get_settings` so that importing
``screener.config`` does not eagerly read ``.env`` or trigger pydantic
validation. Tests can override env vars and call ``get_settings.cache_clear()``
to force re-evaluation.
"""

from functools import lru_cache

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` instance (cached).

    Defers ``.env`` reads and pydantic validation until first call. In tests,
    use ``get_settings.cache_clear()`` after monkey-patching env vars to force
    re-evaluation.
    """
    return Settings()
