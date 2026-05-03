"""Stooq adapter — pandas-datareader wrapper that normalizes Stooq's
PascalCase + descending-index returns into the canonical lowercase +
ascending-index OHLCV shape used by data/ohlcv.py and persistence.

Stooq is the circuit-breaker fallback (D-12, D-14). pandas-datareader 0.10.0
has been frozen since July 2021; community issue #955 reports intermittent
blank-DataFrame returns. We treat empty as failure and apply the same D-08
four-invariant gate as the yfinance path.

Layered-DAG contract: imports only stdlib, third-party, screener.persistence,
screener.config. tests/test_architecture.py enforces this.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pandas_datareader.data as pdr
import structlog

from screener.persistence import StaleOrEmptyError

log = structlog.get_logger(__name__)


def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Fetch a single ticker's daily OHLCV from Stooq.

    Returns a DataFrame indexed by ascending DatetimeIndex with lowercase
    columns ['open','high','low','close','volume']. Raises StaleOrEmptyError
    on any of the four invariant violations.
    """
    log.info("fetch_start", ticker=ticker, source="stooq")
    try:
        df = pdr.DataReader(ticker, "stooq", start=str(start))
    except Exception as e:  # RemoteDataError, OSError, etc.
        raise StaleOrEmptyError(f"stooq raised for {ticker}: {e}") from e

    if df is None or df.empty:
        raise StaleOrEmptyError(f"stooq returned empty for {ticker}")

    # Pitfall 4: Stooq returns descending date order; sort ascending.
    df = df.sort_index(ascending=True)

    # Pitfall to Pattern 5: lowercase columns to satisfy OhlcvPanelSchema.
    df = df.rename(columns=str.lower)

    # D-08 invariants (re-applied for the Stooq path).
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale via stooq: last bar {last}, today {today}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} stooq non-monotonic index")
    if "close" not in df.columns:
        raise StaleOrEmptyError(f"{ticker} stooq missing close column; got {list(df.columns)}")
    if df["close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} stooq has null close")
    return df
