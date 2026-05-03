"""data — the ONLY layer permitted to make network I/O.

Owns yfinance, Finnhub, FRED, EDGAR, Stooq, Wikipedia/iShares fetches; writes
Parquet/SQLite via `persistence`. Downstream layers consume DataFrames and
never call back into `data/` from inside indicators/signals/regime/sizing.
"""

from screener.data.universe import (
    fetch_ishares_iwb_csv,
    iso_week_monday,
    normalize_ticker,
    parse_ishares_iwb_csv,
    refresh_universe,
    sanity_check,
)

__all__ = [
    "fetch_ishares_iwb_csv",
    "iso_week_monday",
    "normalize_ticker",
    "parse_ishares_iwb_csv",
    "refresh_universe",
    "sanity_check",
]
