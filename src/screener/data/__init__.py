"""data — the ONLY layer permitted to make network I/O.

Owns yfinance, Finnhub, FRED, EDGAR, Stooq, Wikipedia/iShares fetches; writes
Parquet/SQLite via `persistence`. Downstream layers consume DataFrames and
never call back into `data/` from inside indicators/signals/regime/sizing.
"""

from screener.data.ohlcv import (
    append_incremental,
    fetch_ohlcv,
    fetch_ohlcv_with_pacing,
    fetch_splits,
    run_with_breaker,
)
from screener.data.stooq import fetch_ohlcv as fetch_stooq_ohlcv
from screener.data.universe import (
    fetch_ishares_iwb_csv,
    iso_week_monday,
    normalize_ticker,
    parse_ishares_iwb_csv,
    refresh_universe,
    sanity_check,
)

__all__ = [
    "append_incremental",
    "fetch_ishares_iwb_csv",
    "fetch_ohlcv",
    "fetch_ohlcv_with_pacing",
    "fetch_splits",
    "fetch_stooq_ohlcv",
    "iso_week_monday",
    "normalize_ticker",
    "parse_ishares_iwb_csv",
    "refresh_universe",
    "run_with_breaker",
    "sanity_check",
]
