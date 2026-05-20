"""fundamentals — Finnhub earnings calendar + yfinance EPS history (DAT-05 / CAT-01).

Fetches two complementary fundamentals streams and writes per-ticker Parquet
files to ``data/fundamentals/<TICKER>.parquet`` via
``persistence.write_fundamentals_atomic``:

1. **Finnhub** ``/calendar/earnings`` — upcoming earnings dates + BMO/AMC hour.
   Single date-range query covers the entire universe (Pitfall 4: never
   per-ticker). Cache 24h via ``requests_cache``.

2. **yfinance** ``Ticker.quarterly_income_stmt`` — historical quarterly EPS.
   Per-ticker with inter-ticker random sleep (Pitfall 10 / D-10 carry-forward
   from data/ohlcv.py). ``Diluted EPS`` row extracted; ``Basic EPS`` as
   fallback; missing data returns empty DataFrame (Pitfall 5 honest-failure).

D-13b structural defense: every row written here carries
``knowable_from = fiscal_quarter_end + 45 days`` (calendar days).
``persistence.read_fundamentals(as_of_date)`` then filters on this column so
``signals/canslim.py`` cannot accidentally consume not-yet-knowable EPS data
(architecture test enforces: ``signals/`` cannot import ``data/``).

Layered-DAG contract (Phase 1 D-16 / tests/test_architecture.py):
imports only stdlib, third-party, ``screener.persistence``,
``screener.config``. DOES NOT import ``screener.indicators`` or
``screener.signals``.

Structured-log event names:
- fundamentals_fetch_start: {source, today}
- fundamentals_fetch_success: {n_tickers, n_written}
- fundamentals_fetch_fail: {source, error_type}
- fundamentals_eps_unavailable: {ticker}
- fundamentals_eps_empty: {ticker}
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, timedelta
from pathlib import Path

import finnhub
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

from screener import persistence
from screener.config import get_settings

log = structlog.get_logger(__name__)
# tenacity's before_sleep_log requires a stdlib logger — structlog's
# make_filtering_bound_logger is incompatible with tenacity's .log() call.
_stdlib_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Finnhub earnings calendar (date-range, single API call per run)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def fetch_earnings_calendar(start: date, end: date) -> pd.DataFrame:
    """Finnhub /calendar/earnings — date-range query (Pitfall 4).

    Returns a DataFrame with columns: symbol, date (Timestamp), hour
    (normalized to {bmo, amc, dmh, unknown}), quarter, year,
    epsActual, epsEstimate.

    Raises ConnectionError / TimeoutError (tenacity-retried) on network
    failure. Never raises on empty payload — returns empty DataFrame.

    Security note (T-06-11): Finnhub URLs may contain the API key in
    query-string fragments. Every ``except`` block uses
    ``error_type=type(e).__name__`` only, NEVER ``error=str(e)``.
    """
    settings = get_settings()
    client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)
    try:
        payload = client.earnings_calendar(
            _from=start.isoformat(),
            to=end.isoformat(),
            symbol="",
            international=False,
        )
    except Exception as e:
        log.error("fundamentals_fetch_fail", source="finnhub", error_type=type(e).__name__)
        raise

    rows = payload.get("earningsCalendar", []) if payload else []
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # Normalize hour to the canonical four values
    df["hour"] = df["hour"].fillna("unknown").astype(str)
    df.loc[~df["hour"].isin(["bmo", "amc", "dmh"]), "hour"] = "unknown"
    return df


# ---------------------------------------------------------------------------
# yfinance EPS history (per-ticker with throttle)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def fetch_eps_history(ticker: str) -> pd.DataFrame:
    """yfinance Ticker.quarterly_income_stmt — Pitfall 5 migration target.

    Extracts the "Diluted EPS" row; falls back to "Basic EPS"; returns an
    empty DataFrame (no exception) if neither row is present or all values
    are NaN. Does NOT call ``time.sleep`` — the pacing wrapper does that.

    Returns DataFrame with columns: fiscal_quarter_end (Timestamp),
    eps_actual (float), eps_yoy_growth (float).
    """
    try:
        stmt = yf.Ticker(ticker).quarterly_income_stmt
    except Exception as e:
        log.error(
            "fundamentals_fetch_fail",
            source="yfinance",
            ticker=ticker,
            error_type=type(e).__name__,
        )
        return pd.DataFrame()

    if stmt is None or stmt.empty:
        log.warning("fundamentals_eps_unavailable", ticker=ticker)
        return pd.DataFrame()

    for row_name in ("Diluted EPS", "Basic EPS"):
        if row_name in stmt.index:
            series = stmt.loc[row_name].dropna()
            if series.empty:
                continue
            df = (
                pd.DataFrame(
                    {
                        "fiscal_quarter_end": pd.to_datetime(series.index),
                        "eps_actual": series.astype(float).to_numpy(),
                    }
                )
                .sort_values("fiscal_quarter_end")
                .reset_index(drop=True)
            )
            # YoY growth = current / 4-quarters-ago - 1
            df["eps_yoy_growth"] = df["eps_actual"] / df["eps_actual"].shift(4) - 1.0
            return df

    log.warning("fundamentals_eps_no_diluted_or_basic_row", ticker=ticker)
    return pd.DataFrame()


def fetch_eps_history_with_pacing(ticker: str) -> pd.DataFrame:
    """Wraps fetch_eps_history with inter-ticker random sleep (Pitfall 10).

    The sleep is BEFORE the fetch (not inside the tenacity retry) to avoid
    rate-limit errors from the first request of a new ticker sequence.
    Sleep duration mirrors OHLCV_FETCH_SLEEP_MIN_S/MAX_S from config.
    """
    settings = get_settings()
    time.sleep(random.uniform(settings.OHLCV_FETCH_SLEEP_MIN_S, settings.OHLCV_FETCH_SLEEP_MAX_S))
    return fetch_eps_history(ticker)


# ---------------------------------------------------------------------------
# Orchestrator: refresh_fundamentals
# ---------------------------------------------------------------------------


def refresh_fundamentals(
    today: date,
    force: bool = False,
    tickers: list[str] | None = None,
) -> dict[str, Path]:
    """Orchestrate Finnhub calendar + per-ticker yfinance EPS refresh (D-07/D-09).

    Steps:
    1. Fetch upcoming earnings calendar for today..today+60d (single Finnhub call).
    2. Determine ticker universe: ``tickers`` arg or ``persistence.read_universe_latest()``.
    3. For each ticker: fetch EPS history (throttled) -> compute knowable_from
       -> merge upcoming earnings date -> write via ``write_fundamentals_atomic``.
    4. Return dict mapping ticker -> Path written.

    The ``force`` parameter is reserved for future full-refresh semantics and
    has no effect in this implementation (incremental is always safe because
    ``write_fundamentals_atomic`` is idempotent).

    Structured log events:
    - ``fundamentals_fetch_start``: emitted before the Finnhub call.
    - ``fundamentals_fetch_success``: emitted after all tickers processed.
    - ``fundamentals_fetch_fail``: emitted for Finnhub or per-ticker failures.
    """
    log.info("fundamentals_fetch_start", source="fundamentals", today=str(today))

    # Step 1: Fetch upcoming earnings calendar
    start = today
    end = today + timedelta(days=60)
    try:
        calendar = fetch_earnings_calendar(start, end)
    except Exception as e:
        log.warning(
            "fundamentals_fetch_fail",
            source="finnhub",
            error_type=type(e).__name__,
        )
        calendar = pd.DataFrame()

    # Step 2: Determine ticker universe
    if tickers is None:
        tickers = persistence.read_universe_latest()

    # Step 3: Per-ticker EPS fetch + write
    written: dict[str, Path] = {}
    for ticker in tickers:
        try:
            eps = fetch_eps_history_with_pacing(ticker)
        except Exception as e:
            log.warning(
                "fundamentals_fetch_fail",
                source="yfinance",
                ticker=ticker,
                error_type=type(e).__name__,
            )
            continue

        if eps.empty:
            log.warning("fundamentals_eps_empty", ticker=ticker)
            continue

        # D-13b: knowable_from = fiscal_quarter_end + 45 days
        eps["knowable_from"] = eps["fiscal_quarter_end"] + pd.Timedelta(days=45)
        eps["ticker"] = ticker
        eps["source"] = "yfinance"
        eps["ingested_at"] = pd.Timestamp.now()

        # Merge upcoming earnings from Finnhub calendar
        if not calendar.empty and "symbol" in calendar.columns:
            cal_ticker = calendar[calendar["symbol"] == ticker].copy()
            if not cal_ticker.empty and "date" in cal_ticker.columns:
                # Use the earliest future date
                future = cal_ticker[cal_ticker["date"] >= pd.Timestamp(today)]
                if not future.empty:
                    next_row = future.sort_values("date").iloc[0]
                    eps["next_earnings_date"] = next_row["date"]
                    eps["next_earnings_hour"] = str(next_row.get("hour", "unknown"))
                else:
                    eps["next_earnings_date"] = pd.NaT
                    eps["next_earnings_hour"] = "unknown"
            else:
                eps["next_earnings_date"] = pd.NaT
                eps["next_earnings_hour"] = "unknown"
        else:
            eps["next_earnings_date"] = pd.NaT
            eps["next_earnings_hour"] = "unknown"

        try:
            path = persistence.write_fundamentals_atomic(eps, ticker)
            written[ticker] = path
        except Exception as e:
            log.warning(
                "fundamentals_fetch_fail",
                source="write",
                ticker=ticker,
                error_type=type(e).__name__,
            )
            continue

    log.info(
        "fundamentals_fetch_success",
        n_tickers=len(tickers),
        n_written=len(written),
        today=str(today),
    )
    return written
