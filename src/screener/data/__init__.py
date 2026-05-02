"""data — the ONLY layer permitted to make network I/O.

Owns yfinance, Finnhub, FRED, EDGAR, Stooq, Wikipedia/iShares fetches; writes
Parquet/SQLite via `persistence`. Downstream layers consume DataFrames and
never call back into `data/` from inside indicators/signals/regime/sizing.
"""
