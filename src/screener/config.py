"""Typed application settings (env-driven via pydantic-settings).

Loads from `.env` at the repo root; values can be overridden by environment
variables. Phase 1 ships the seven fields the v1 stack will consume; Phase 2
adds eight data-layer fields per D-20. Later phases extend the Settings class
additively.

Settings are constructed lazily via :func:`get_settings` so that importing
``screener.config`` does not eagerly read ``.env`` or trigger pydantic
validation. Tests can override env vars and call ``get_settings.cache_clear()``
to force re-evaluation.
"""

from functools import lru_cache
from pathlib import Path

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

    # Phase 2 (D-20) — data-layer paths and policy
    OHLCV_CACHE_DIR: Path = Path("data/ohlcv")
    UNIVERSE_CACHE_DIR: Path = Path("data/universe")
    OHLCV_BACKFILL_START: str = "2005-01-01"
    UNIVERSE_HEALTH_THRESHOLD: float = 0.95
    STOOQ_BREAKER_PROBE_N: int = 50
    STOOQ_BREAKER_THRESHOLD: float = 0.80
    OHLCV_FETCH_SLEEP_MIN_S: float = 0.5
    OHLCV_FETCH_SLEEP_MAX_S: float = 1.5

    # Phase 3 (D-12) — macro + RS snapshot paths and regime thresholds
    MACRO_CACHE_DIR: Path = Path("data/macro")
    RS_SNAPSHOT_DIR: Path = Path("data/rs_snapshots")
    MACRO_BACKFILL_START: str = "2005-01-01"
    REGIME_BREADTH_THRESHOLD: float = 0.60
    REGIME_DIST_DAYS_PRESSURE: int = 5
    REGIME_DIST_DAYS_CORRECTION: int = 9
    REGIME_VIX_CORRECTION: float = 30.0
    REGIME_VIX_CONFIRMED: float = 20.0

    # Phase 4 (D-07/D-08, CONTEXT.md "Claude's Discretion") — report + trend-template gate config
    SNAPSHOT_DIR: Path = Path("data/snapshots")
    REPORT_DIR: Path = Path("reports")
    REPORT_TOP_N: int = 15
    TREND_TEMPLATE_PASS_RATE_WARN: float = 0.25
    TREND_TEMPLATE_PASS_RATE_HARD_FAIL: float = 0.25


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` instance (cached).

    Defers ``.env`` reads and pydantic validation until first call. In tests,
    use ``get_settings.cache_clear()`` after monkey-patching env vars to force
    re-evaluation.
    """
    return Settings()
