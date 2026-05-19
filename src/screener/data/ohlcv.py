"""OHLCV — yfinance fetcher + tenacity wrapper + post-fetch invariants
(D-08) + sentinel-bar refetch (D-07) + circuit-breaker orchestration (D-12)
+ splits ledger (D-18).

Layered-DAG contract: imports only stdlib, third-party, screener.persistence,
screener.config, and (intra-layer) screener.data.stooq.

Structured-log event names (Open Question 7 resolution):
- fetch_start: {command, n_universe} OR {ticker, source}
- fetch_success: {ticker, source, n_bars}
- fetch_fail:    {ticker, source, error, attempt}
- breaker_tripped: {probe_n, success_rate, threshold}
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import structlog
import yfinance as yf
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
    make_empty_splits,
    write_ohlcv_atomic,
    write_splits_atomic,
)

log = structlog.get_logger(__name__)
# before_sleep_log requires a stdlib logger (not structlog); tenacity calls
# logger.log(level_int, msg) which is incompatible with structlog's
# make_filtering_bound_logger. Passing a stdlib logger here is the canonical
# tenacity pattern; structlog still handles all other events in this module.
_stdlib_log = logging.getLogger(__name__)


# --- yfinance fetch with tenacity + four-invariant gate (D-08, D-10) -------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Fetch a single ticker's daily OHLCV from Yahoo via yfinance.

    Applies the four D-08 invariants atomically inside the tenacity-retried
    block so silent-empty and stale-data failures retry; only persistent
    failures (5 attempts) propagate as StaleOrEmptyError.

    Returns a DataFrame with lowercase columns and a DatetimeIndex named 'date'.
    """
    df = yf.download(
        ticker,
        start=str(start),
        auto_adjust=True,           # D-17: store adjusted only
        progress=False,
        threads=False,              # D-10: no batch/parallel
        actions=False,              # splits fetched separately via Ticker.actions
        multi_level_index=False,    # Pitfall 9: yf 1.3.x default is True
    )
    if df is None or len(df) == 0:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")

    # Normalize to lowercase columns + named index BEFORE the invariant gate
    # so the four-invariant null-close check reads df["close"] directly. This
    # is the single source of truth for column casing — append_incremental and
    # run_with_breaker MUST NOT rename columns again (issue 2 reconciliation).
    df = df.rename(columns=str.lower)
    if df.index.name is None or df.index.name.lower() != "date":
        df.index.name = "date"
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale: last bar {last}, today {today}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} non-monotonic index")
    if "close" not in df.columns:
        raise StaleOrEmptyError(f"{ticker} no close column; got {list(df.columns)}")
    if df["close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} has null close")

    # Postcondition (enforced contract): returned DataFrame columns are
    # guaranteed lowercase (open, high, low, close, volume) and the
    # DatetimeIndex is named "date". Downstream callers rely on this
    # invariant — do NOT add a defensive rename in callers.
    return df


# --- Pacing wrapper (D-10) -------------------------------------------------


def fetch_ohlcv_with_pacing(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Wraps fetch_ohlcv with the inter-ticker random sleep (D-10).

    The sleep is OUTSIDE the tenacity retry decorator: backoff between
    attempts is governed by tenacity's wait_exponential, while inter-ticker
    pacing is governed by OHLCV_FETCH_SLEEP_MIN_S/MAX_S.
    """
    settings = get_settings()
    df = fetch_ohlcv(ticker, start, today)
    time.sleep(random.uniform(settings.OHLCV_FETCH_SLEEP_MIN_S, settings.OHLCV_FETCH_SLEEP_MAX_S))
    return df


# --- Sentinel-bar refetch for incremental append (D-07) --------------------


def _approx_equal(a: float, b: float, rtol: float = 0.005) -> bool:
    """Relative-tolerance comparison; 0.5% rtol catches splits without
    false-positive on dividend re-adjustment drift (RESEARCH.md Pattern 3).
    """
    if b == 0:
        return abs(a - b) < rtol
    return abs(a - b) / abs(b) <= rtol


def append_incremental(ticker: str, today: date) -> tuple[pd.DataFrame, bool]:
    """Read cache (if exists), fetch incremental, sentinel-check, append OR full-refetch.

    Returns (df, full_refetched). On a clean cache, returns (full backfill, True).
    On a stale-but-current cache, returns (cached, False).
    On sentinel mismatch, returns (full re-fetch, True).
    """
    settings = get_settings()
    cache_path = Path(settings.OHLCV_CACHE_DIR) / ticker / "prices.parquet"

    if not cache_path.exists():
        df = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
        return df, True

    cached = pd.read_parquet(cache_path)
    # Lowercase invariant: cached panels are written through write_ohlcv_atomic
    # which validates against OhlcvPanelSchema (lowercase columns required), so
    # any cached file MUST have lowercase columns. fetch_ohlcv ALSO returns
    # lowercase. No dual-case branching needed below.
    assert "close" in cached.columns, (
        f"cached panel for {ticker} violates lowercase invariant; "
        f"got columns {list(cached.columns)!r}"
    )
    last_cached_date = cached.index[-1].date()
    if last_cached_date >= today - timedelta(days=1):
        return cached, False

    # Re-fetch starting at the SAME cached date so the response includes the
    # sentinel bar we can compare against the cache. fetch_ohlcv guarantees
    # lowercase columns on its return, so we read "close" directly here.
    new = fetch_ohlcv(ticker, last_cached_date, today)

    matching = new[new.index.date == last_cached_date]
    if len(matching) == 0:
        log.warning("sentinel_missing", ticker=ticker, last_cached=str(last_cached_date))
        full = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
        return full, True

    sentinel_new = float(matching["close"].iloc[0])
    sentinel_old = float(cached["close"].iloc[-1])
    if not _approx_equal(sentinel_new, sentinel_old, rtol=0.005):
        log.warning(
            "sentinel_mismatch",
            ticker=ticker,
            cached=sentinel_old,
            refetched=sentinel_new,
        )
        full = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
        return full, True

    new_bars = new[new.index.date > last_cached_date]
    return pd.concat([cached, new_bars]), False


# --- Splits ledger (D-18) --------------------------------------------------


def fetch_splits(ticker: str) -> pd.DataFrame:
    """Pull yfinance.Ticker(t).actions, normalize to SplitsSchema shape.

    Returns make_empty_splits() when the ticker has no corporate actions in
    the cached window (Open Question 3 resolution).
    """
    actions = yf.Ticker(ticker).actions
    if actions is None or len(actions) == 0:
        return make_empty_splits()

    # yfinance returns columns like ["Dividends", "Stock Splits"] indexed by
    # event date; some splits return as ratios (10.0 for a 10:1) and some
    # tickers may have only dividends. Normalize to {ratio, dividend}.
    df = pd.DataFrame(
        {
            "ratio": actions.get("Stock Splits", pd.Series(0.0, index=actions.index)).astype(float).values,
            "dividend": actions.get("Dividends", pd.Series(0.0, index=actions.index)).astype(float).values,
        },
        index=pd.DatetimeIndex(actions.index, name="date"),
    )
    # Keep only rows where at least one of ratio/dividend is non-zero.
    keep = (df["ratio"] > 0) | (df["dividend"] > 0)
    df = df[keep]
    if len(df) == 0:
        return make_empty_splits()
    return df


# --- Circuit-breaker orchestration (D-12, D-13) ----------------------------


def run_with_breaker(tickers: list[str], today: date) -> tuple[int, int, list[str]]:
    """Run the yfinance loop with the first-N circuit-breaker.

    Returns (yf_ok, stooq_ok, failed). The CLI (Plan 02-05) computes the
    95% combined gate from these counters and decides exit code.

    Side effects: writes per-ticker prices.parquet + splits.parquet via
    persistence.write_ohlcv_atomic and persistence.write_splits_atomic.
    """
    settings = get_settings()
    yf_ok = 0
    stooq_ok = 0
    failed: list[str] = []
    breaker_tripped = False

    log.info("fetch_start", command="refresh-ohlcv", n_universe=len(tickers))

    for i, ticker in enumerate(tickers):
        if not breaker_tripped:
            try:
                df, _full = append_incremental(ticker, today)
                # fetch_ohlcv (and append_incremental's cached read) both
                # guarantee lowercase columns + index.name == "date". No
                # rename needed here — write_ohlcv_atomic accepts the panel
                # as-is.
                write_ohlcv_atomic(ticker, df)
                splits_df = fetch_splits(ticker)
                write_splits_atomic(ticker, splits_df)
                # Pacing: pause inside the success branch only (we already
                # paid the retry budget on failure).
                time.sleep(
                    random.uniform(settings.OHLCV_FETCH_SLEEP_MIN_S, settings.OHLCV_FETCH_SLEEP_MAX_S)
                )
                yf_ok += 1
                log.info("fetch_success", ticker=ticker, source="yfinance", n_bars=len(df))
            except Exception as e:
                failed.append(ticker)
                log.warning("fetch_fail", ticker=ticker, source="yfinance", error=str(e), attempt=5)

            # Circuit-breaker probe at exactly i+1 == STOOQ_BREAKER_PROBE_N.
            if i + 1 == settings.STOOQ_BREAKER_PROBE_N:
                rate = yf_ok / settings.STOOQ_BREAKER_PROBE_N
                if rate < settings.STOOQ_BREAKER_THRESHOLD:
                    breaker_tripped = True
                    log.warning(
                        "breaker_tripped",
                        probe_n=settings.STOOQ_BREAKER_PROBE_N,
                        success_rate=rate,
                        threshold=settings.STOOQ_BREAKER_THRESHOLD,
                    )
        else:
            # Stooq fallback path. The Stooq adapter normalizes to lowercase
            # + ascending and is responsible for naming its index "date";
            # persistence.write_ohlcv_atomic accepts that shape directly.
            try:
                df = stooq_module.fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
                write_ohlcv_atomic(ticker, df)
                splits_df = fetch_splits(ticker)
                write_splits_atomic(ticker, splits_df)
                stooq_ok += 1
                log.info("fetch_success", ticker=ticker, source="stooq", n_bars=len(df))
            except Exception as e:
                failed.append(ticker)
                log.warning("fetch_fail", ticker=ticker, source="stooq", error=str(e), attempt=1)

    return yf_ok, stooq_ok, failed
