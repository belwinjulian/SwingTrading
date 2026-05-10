"""macro — Phase 3 macro data layer (DAT-04).

Fetches 5 macro series and writes each to data/macro/<series>.parquet:
- SPY  : yfinance OHLCV
- QQQ  : yfinance OHLCV
- ^VIX : yfinance close-only (Volume=0 always per RESEARCH Pitfall 4)
- $NYAD: Stooq primary, R1000 breadth fallback (D-05; Stooq broken per Pitfall 1)
- yields: FRED DGS2/DGS10/T10Y2Y in single Parquet (NaN-as-received per Pitfall 5)

Layered-DAG contract (Phase 1 D-16 / tests/test_architecture.py): imports only
stdlib, third-party (yfinance, fredapi, pandas-datareader via stooq_module,
pandas, structlog, tenacity), screener.persistence, screener.config, and
intra-layer screener.data.stooq.

Structured-log event names:
- macro_fetch_start: {series, source}
- macro_fetch_success: {series, source, n_bars}
- macro_fetch_fail: {series, source, error_type, attempt}
- nyad_source: {source: stooq | r1000_proxy}
- skipping_yields_no_key: {}
- macro_snapshot_written: emitted by persistence.write_macro_atomic
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import structlog
import yfinance as yf
from fredapi import Fred
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from screener.config import get_settings
from screener.data import stooq as stooq_module
from screener.persistence import (
    StaleOrEmptyError,
    read_panel,
    write_macro_atomic,
)

log = structlog.get_logger(__name__)
# before_sleep_log requires a stdlib logger (not structlog); tenacity calls
# logger.log(level_int, msg) which is incompatible with structlog's
# make_filtering_bound_logger. Passing a stdlib logger here is the canonical
# tenacity pattern; structlog still handles all other events in this module.
_stdlib_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# yfinance fetcher (mirrors data/ohlcv.py:fetch_ohlcv lines 54-104)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def _fetch_yf_macro(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Phase 2 D-10 idiom retargeted for SPY/QQQ/^VIX. Returns lowercase columns
    + index.name='date' (RESEARCH Pitfall 7)."""
    df = yf.download(
        ticker,
        start=str(start),
        auto_adjust=True,
        progress=False,
        threads=False,
        actions=False,
        multi_level_index=False,
    )
    if df is None or len(df) == 0:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")
    df = df.rename(columns=str.lower)
    if df.index.name is None or df.index.name.lower() != "date":
        df.index.name = "date"
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale: last bar {last}, today {today}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} non-monotonic index")
    if "close" not in df.columns:
        raise StaleOrEmptyError(f"{ticker} no close column; got {list(df.columns)}")
    if df["close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} has null close")
    return df


def _project_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Project to MacroOhlcvSchema columns (open/high/low/close/volume) +
    int volume cast. Volume from yfinance is float — cast to int for schema."""
    out = df[["open", "high", "low", "close", "volume"]].copy()
    out["volume"] = out["volume"].fillna(0).astype("int64")
    return out


# ---------------------------------------------------------------------------
# Per-series refresh functions (D-04)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Incremental-append helper (D-06; mirrors Phase 2 D-07 OHLCV idiom).
#
# Each refresh_<series>() inspects the cached Parquet via
# persistence.read_macro_<series>() (which returns an empty schema-shaped frame
# when the file does not yet exist), computes start = max(date)+1d, and only
# fetches newer bars. On first run start = MACRO_BACKFILL_START. force=True
# bypasses the cache and refetches the full backfill.
# ---------------------------------------------------------------------------


def _incremental_start(existing: pd.DataFrame, settings_start: str) -> str | None:
    """Return the next-day start date for an incremental fetch, or None if
    the cache is already up-to-date as of today.

    - Empty cache → backfill start.
    - Non-empty cache → max(date)+1d, unless that's already in the future.
    """
    if existing is None or existing.empty:
        return settings_start
    last = pd.Timestamp(existing.index.max()).normalize()
    next_start = last + pd.Timedelta(days=1)
    if next_start > pd.Timestamp.now().normalize():
        return None  # nothing to do — cache is current
    return next_start.strftime("%Y-%m-%d")


def _append_new_bars(existing: pd.DataFrame | None, new_bars: pd.DataFrame) -> pd.DataFrame:
    """Concat existing + new_bars, dedupe on the date index keeping the new
    value (Phase 2 D-07 sentinel-bar refetch parity)."""
    if existing is None or existing.empty:
        return new_bars
    combined = pd.concat([existing, new_bars])
    combined = combined.loc[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()
    return combined


def _macro_dir_for_log() -> Path:
    """Local helper to surface the canonical macro path for skip-log return values."""
    from screener import persistence  # late import; avoids circular concerns
    return persistence._macro_dir()


def refresh_spy(force: bool, today: date) -> Path:
    """Idempotent + incremental (D-06). Subsequent runs append only newer bars
    after the existing max(date); first run backfills from MACRO_BACKFILL_START.
    """
    from screener import persistence  # late import; avoids circular concerns

    settings = get_settings()
    existing = persistence.read_macro_spy() if not force else None
    start = (
        settings.MACRO_BACKFILL_START
        if (existing is None or existing.empty)
        else _incremental_start(existing, settings.MACRO_BACKFILL_START)
    )
    if start is None:
        log.info(
            "macro_refresh_skip_up_to_date",
            series="spy",
            last_date=str(existing.index.max().date()),  # type: ignore[union-attr]
        )
        return _macro_dir_for_log() / "spy.parquet"
    log.info("macro_fetch_start", series="spy", source="yfinance", start=start)
    new_bars = _fetch_yf_macro("SPY", start, today)
    new_bars = _project_ohlcv(new_bars)
    combined = _append_new_bars(existing, new_bars)
    log.info(
        "macro_fetch_success",
        series="spy",
        source="yfinance",
        n_bars=len(combined),
        n_new=len(new_bars),
    )
    return write_macro_atomic(combined, "spy")


def refresh_qqq(force: bool, today: date) -> Path:
    """Idempotent + incremental (D-06). Mirrors refresh_spy for QQQ."""
    from screener import persistence

    settings = get_settings()
    existing = persistence.read_macro_qqq() if not force else None
    start = (
        settings.MACRO_BACKFILL_START
        if (existing is None or existing.empty)
        else _incremental_start(existing, settings.MACRO_BACKFILL_START)
    )
    if start is None:
        log.info(
            "macro_refresh_skip_up_to_date",
            series="qqq",
            last_date=str(existing.index.max().date()),  # type: ignore[union-attr]
        )
        return _macro_dir_for_log() / "qqq.parquet"
    log.info("macro_fetch_start", series="qqq", source="yfinance", start=start)
    new_bars = _fetch_yf_macro("QQQ", start, today)
    new_bars = _project_ohlcv(new_bars)
    combined = _append_new_bars(existing, new_bars)
    log.info(
        "macro_fetch_success",
        series="qqq",
        source="yfinance",
        n_bars=len(combined),
        n_new=len(new_bars),
    )
    return write_macro_atomic(combined, "qqq")


def refresh_vix(force: bool, today: date) -> Path:
    """^VIX is close-only (Pitfall 4 — Volume=0 always). Incremental per D-06."""
    from screener import persistence

    settings = get_settings()
    existing = persistence.read_macro_vix() if not force else None
    start = (
        settings.MACRO_BACKFILL_START
        if (existing is None or existing.empty)
        else _incremental_start(existing, settings.MACRO_BACKFILL_START)
    )
    if start is None:
        log.info(
            "macro_refresh_skip_up_to_date",
            series="vix",
            last_date=str(existing.index.max().date()),  # type: ignore[union-attr]
        )
        return _macro_dir_for_log() / "vix.parquet"
    log.info("macro_fetch_start", series="vix", source="yfinance", start=start)
    new_bars = _fetch_yf_macro("^VIX", start, today)
    new_bars = new_bars[["close"]].copy()  # project to close-only per VixSchema
    combined = _append_new_bars(existing, new_bars)
    log.info(
        "macro_fetch_success",
        series="vix",
        source="yfinance",
        n_bars=len(combined),
        n_new=len(new_bars),
    )
    return write_macro_atomic(combined, "vix")


def refresh_nyad(force: bool, today: date) -> Path:
    """Stooq $NYAD primary; R1000-breadth fallback (D-05). Incremental per D-06.
    Per RESEARCH Pitfall 1, Stooq is currently broken — fallback is operative
    primary today. Structured event nyad_source distinguishes the path used.
    Both branches honor existing.index.max() — neither path issues a full
    re-derivation when the cache is current.
    """
    from screener import persistence

    settings = get_settings()
    existing = persistence.read_macro_nyad() if not force else None
    start = (
        settings.MACRO_BACKFILL_START
        if (existing is None or existing.empty)
        else _incremental_start(existing, settings.MACRO_BACKFILL_START)
    )
    if start is None:
        log.info(
            "macro_refresh_skip_up_to_date",
            series="nyad",
            last_date=str(existing.index.max().date()),  # type: ignore[union-attr]
        )
        return _macro_dir_for_log() / "nyad.parquet"
    log.info("macro_fetch_start", series="nyad", source="stooq", start=start)
    new_bars: pd.DataFrame
    try:
        stooq_df = stooq_module.fetch_ohlcv("$NYAD", start, today)
        # D-05 thin-data heuristic: > 5% missing values triggers fallback
        if "close" in stooq_df.columns and stooq_df["close"].isna().mean() > 0.05:
            raise StaleOrEmptyError("$NYAD > 5% missing — falling back to r1000_proxy")
        # If Stooq ever recovers and returns valid OHLCV, derive advances/declines
        # from close.diff() — same shape as fallback.
        new_bars = _stooq_to_breadth(stooq_df)
        log.info("nyad_source", source="stooq")
    except Exception as e:
        log.warning(
            "macro_fetch_fail",
            series="nyad",
            source="stooq",
            error_type=type(e).__name__,
        )
        # Fallback also honors the incremental window — only re-derive from `start`.
        new_bars = _compute_breadth_fallback(start, today)
        log.info("nyad_source", source="r1000_proxy")
    combined = _append_new_bars(existing, new_bars)
    log.info(
        "macro_fetch_success",
        series="nyad",
        source="resolved",
        n_bars=len(combined),
        n_new=len(new_bars),
    )
    return write_macro_atomic(combined, "nyad")


def refresh_yields(force: bool, today: date) -> Path:
    """FRED DGS2/DGS10/T10Y2Y. Stored as-received with NaN gaps (Pitfall 5).
    Empty Parquet on missing FRED_API_KEY (graceful — yields not in D-03 score).
    Incremental per D-06.
    """
    from screener import persistence

    settings = get_settings()
    if not settings.FRED_API_KEY:
        log.warning("skipping_yields_no_key")
        empty = pd.DataFrame(
            {
                "dgs2": pd.Series([], dtype="float64"),
                "dgs10": pd.Series([], dtype="float64"),
                "t10y2y": pd.Series([], dtype="float64"),
            },
            index=pd.DatetimeIndex([], name="date"),
        )
        return write_macro_atomic(empty, "yields")
    existing = persistence.read_macro_yields() if not force else None
    start = (
        settings.MACRO_BACKFILL_START
        if (existing is None or existing.empty)
        else _incremental_start(existing, settings.MACRO_BACKFILL_START)
    )
    if start is None:
        log.info(
            "macro_refresh_skip_up_to_date",
            series="yields",
            last_date=str(existing.index.max().date()),  # type: ignore[union-attr]
        )
        return _macro_dir_for_log() / "yields.parquet"
    log.info("macro_fetch_start", series="yields", source="fred", start=start)
    try:
        new_bars = _fetch_fred_yields(start, today)
    except Exception as e:
        # T-3-02: NEVER pass `error=str(e)` — FRED exceptions may include the
        # request URL with `?api_key=...` querystring. Log only error_type and
        # series; let typer surface the traceback to stderr after re-raise.
        log.error(
            "macro_fetch_fail",
            series="yields",
            source="fred",
            error_type=type(e).__name__,
        )
        raise
    combined = _append_new_bars(existing, new_bars)
    log.info(
        "macro_fetch_success",
        series="yields",
        source="fred",
        n_bars=len(combined),
        n_new=len(new_bars),
    )
    return write_macro_atomic(combined, "yields")


# ---------------------------------------------------------------------------
# FRED fetcher (NEW idiom; tenacity wrapper + key sanitization)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def _fetch_fred_yields(start: str | date, today: date) -> pd.DataFrame:
    """Fetch DGS2, DGS10, T10Y2Y from FRED. T-3-02: never log api_key."""
    settings = get_settings()
    fred = Fred(api_key=settings.FRED_API_KEY)
    s2 = fred.get_series("DGS2", observation_start=str(start), observation_end=str(today))
    s10 = fred.get_series("DGS10", observation_start=str(start), observation_end=str(today))
    spread = fred.get_series("T10Y2Y", observation_start=str(start), observation_end=str(today))
    df = pd.DataFrame({"dgs2": s2, "dgs10": s10, "t10y2y": spread})
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# R1000 breadth fallback (RESEARCH Pattern 6, D-05)
# ---------------------------------------------------------------------------


def _stooq_to_breadth(stooq_df: pd.DataFrame) -> pd.DataFrame:
    """If Stooq returns valid $NYAD OHLCV, derive advances/declines from close.diff().
    Schema-shape compatible with NyadMacroSchema."""
    deltas = stooq_df["close"].diff()
    advances = (deltas > 0).astype("int64")
    declines = (deltas < 0).astype("int64")
    ad_line = (advances - declines).cumsum().astype("int64")
    out = pd.DataFrame({"advances": advances, "declines": declines, "ad_line": ad_line})
    out.index = stooq_df.index
    out.index.name = "date"
    return out


def _compute_breadth_fallback(start: str | date, today: date) -> pd.DataFrame:
    """R1000-derived advance-decline line (RESEARCH Pattern 6).
    Reads the most-recent universe snapshot, joins per-ticker prices,
    computes daily advances - declines.
    """
    settings = get_settings()
    universe_dir = Path(str(settings.UNIVERSE_CACHE_DIR))
    snaps = sorted(universe_dir.glob("*.parquet"))
    if not snaps:
        raise StaleOrEmptyError(
            "no universe snapshot available for r1000_proxy fallback"
        )
    snapshot_date = snaps[-1].stem
    panel = read_panel(snapshot_date)  # MultiIndex (ticker, date) panel
    closes = panel["close"].unstack(level="ticker")  # date x ticker wide frame  # noqa: PD010
    deltas = closes.diff()
    advances = (deltas > 0).sum(axis=1).astype("int64")
    declines = (deltas < 0).sum(axis=1).astype("int64")
    ad_line = (advances - declines).cumsum().astype("int64")
    out = pd.DataFrame({"advances": advances, "declines": declines, "ad_line": ad_line})
    out.index.name = "date"
    # Slice to the requested window
    start_str = str(start)
    today_str = str(today)
    out = out.loc[start_str:today_str]
    return out
