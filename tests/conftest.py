"""Shared pytest configuration and fixtures.

Phase 1 ships only the fixtures Phase 1 tests need. Phase 2 adds 10 synthetic
fixtures consumed by tests/test_data_universe.py, tests/test_data_ohlcv.py,
tests/test_data_stooq.py, tests/test_persistence.py, and the extended
tests/test_cli_smoke.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# --- Reference date used by the OHLCV fixtures (deterministic) --------------

# Pinned to a recent weekday so business-day arithmetic is stable across
# CI runs. A fixed value also makes the fixtures hashable for session scope.
_REF_DATE = pd.Timestamp("2026-04-30")


# --- Phase 1 fixtures (KEEP unchanged) --------------------------------------


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repo root (parent of `tests/`)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_screener(repo_root: Path) -> Path:
    """Absolute path to src/screener/."""
    return repo_root / "src" / "screener"


# --- Phase 2 OHLCV fixtures -------------------------------------------------


@pytest.fixture(scope="session")
def synthetic_ohlcv_valid_df() -> pd.DataFrame:
    """252 daily bars passing all 4 D-08 invariants.

    Invariants: non-empty, recent, monotonic, no null close.
    """
    idx = pd.bdate_range(end=_REF_DATE, periods=252)
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_empty_df() -> pd.DataFrame:
    """Empty OHLCV frame — the silent-empty-from-yfinance simulation."""
    return pd.DataFrame(
        {"Open": [], "High": [], "Low": [], "Close": [], "Volume": []},
        index=pd.DatetimeIndex([], name="Date"),
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_stale_df() -> pd.DataFrame:
    """Last bar 10 business days before _REF_DATE — fails the recency invariant."""
    end_stale = _REF_DATE - pd.tseries.offsets.BDay(10)
    idx = pd.bdate_range(end=end_stale, periods=252)
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_null_close_df() -> pd.DataFrame:
    """One NaN in Close — fails the null-close invariant."""
    idx = pd.bdate_range(end=_REF_DATE, periods=252)
    close = np.full(len(idx), 100.5)
    close[5] = np.nan
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": close,
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_ohlcv_non_monotonic_df() -> pd.DataFrame:
    """DatetimeIndex with the last 5 bars in random order — fails monotonicity."""
    idx = list(pd.bdate_range(end=_REF_DATE, periods=252))
    # Shuffle the last 5 bars deterministically.
    idx[-5:] = [idx[-1], idx[-3], idx[-5], idx[-2], idx[-4]]
    didx = pd.DatetimeIndex(idx)
    return pd.DataFrame(
        {
            "Open": np.full(len(didx), 100.0),
            "High": np.full(len(didx), 101.0),
            "Low": np.full(len(didx), 99.0),
            "Close": np.full(len(didx), 100.5),
            "Volume": np.full(len(didx), 1_000_000, dtype="int64"),
        },
        index=didx,
    )


# --- Phase 2 iShares CSV fixtures (BYTES, encoded UTF-8 with BOM) ----------


def _make_ishares_csv_bytes(
    n_equity_rows: int,
    sector_override_for_first: str | None = None,
) -> bytes:
    """Build an iShares-shaped CSV. Replicates the verified live structure:
    9 metadata lines, blank, header, then `n_equity_rows` equity rows, then
    a couple of cash/derivative rows, then trailer text.
    """
    metadata = "\n".join(f"Field {i},Value {i}" for i in range(9))
    blank = ""
    header = (
        "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,"
        "Quantity,Price,Location,Exchange,Currency"
    )
    sectors = [
        "Information Technology",
        "Health Care",
        "Financials",
        "Consumer Discretionary",
        "Communication",
        "Industrials",
        "Consumer Staples",
        "Energy",
        "Utilities",
        "Real Estate",
        "Materials",
    ]
    rows: list[str] = []
    for i in range(n_equity_rows):
        ticker = f"AA{i:04d}"
        sector = sectors[i % len(sectors)]
        if i == 0 and sector_override_for_first is not None:
            sector = sector_override_for_first
        rows.append(
            f"{ticker},Company {i},{sector},Equity,1000.00,0.10,1000.00,10,100.00,US,NASDAQ,USD"
        )
    cash_rows = [
        "XTSLA,BLK CSH,-,Cash,500.00,0.05,500.00,500,1.00,US,-,USD",
        "USD,USD CASH,-,Cash,250.00,0.03,250.00,250,1.00,US,-,USD",
    ]
    trailer = 'The content of this CSV is provided "as is".'
    body = (
        metadata
        + "\n"
        + blank
        + "\n"
        + header
        + "\n"
        + "\n".join(rows)
        + "\n"
        + "\n".join(cash_rows)
        + "\n"
        + trailer
        + "\n"
    )
    # UTF-8 with BOM (matches utf-8-sig encoding the live feed uses).
    bom = bytes([0xEF, 0xBB, 0xBF])  # UTF-8 BOM matches utf-8-sig encoding
    return bom + body.encode("utf-8")  # UTF-8 BOM prefix matches utf-8-sig


@pytest.fixture(scope="session")
def synthetic_ishares_csv_bytes() -> bytes:
    """1010-row valid iShares-shaped CSV that passes parse + sanity_check."""
    return _make_ishares_csv_bytes(n_equity_rows=1005)


@pytest.fixture(scope="session")
def synthetic_ishares_csv_undersized_bytes() -> bytes:
    """500-row variant — sanity_check raises ValueError (count outside [800, 1100])."""
    return _make_ishares_csv_bytes(n_equity_rows=500)


@pytest.fixture(scope="session")
def synthetic_ishares_csv_bad_sector_bytes() -> bytes:
    """First row has Sector='Bogus Sector' — sanity_check raises ValueError."""
    return _make_ishares_csv_bytes(n_equity_rows=1005, sector_override_for_first="Bogus Sector")


# --- Phase 2 sentinel-mismatch fixture --------------------------------------


@pytest.fixture(scope="session")
def synthetic_split_mismatch_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A (cached, refetched) pair where the sentinel close differs by ~50%.

    Cached has Close[-1] = 200.0; refetched has the same date but Close = 100.0
    (simulating a 2:1 split that retroactively halved historical adjusted prices).
    """
    idx = pd.bdate_range(end=_REF_DATE, periods=10)
    cached = pd.DataFrame(
        {
            "Open": np.full(len(idx), 199.0),
            "High": np.full(len(idx), 201.0),
            "Low": np.full(len(idx), 198.0),
            "Close": np.full(len(idx), 200.0),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )
    # Refetched starts at the same last_cached_date and goes 5 bars forward.
    new_idx = pd.bdate_range(start=idx[-1], periods=5)
    refetched = pd.DataFrame(
        {
            "Open": np.full(len(new_idx), 99.0),
            "High": np.full(len(new_idx), 101.0),
            "Low": np.full(len(new_idx), 98.0),
            "Close": np.full(len(new_idx), 100.0),  # half of cached — sentinel mismatch
            "Volume": np.full(len(new_idx), 2_000_000, dtype="int64"),
        },
        index=new_idx,
    )
    return cached, refetched


# --- Phase 2 Stooq-shaped fixture -------------------------------------------


@pytest.fixture(scope="session")
def synthetic_stooq_descending_df() -> pd.DataFrame:
    """Stooq-shape DataFrame: descending DatetimeIndex + PascalCase columns."""
    idx = pd.bdate_range(end=_REF_DATE, periods=20)
    df = pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )
    return df.sort_index(ascending=False)


# --- Phase 3 indicator + regime fixtures -----------------------------------
# Populated by Plans 03-03, 03-04, 03-05. This section header is a Wave 0
# anchor; downstream plans add fixtures (synthetic_short_history_panel,
# synthetic_multi_ticker_panel, synthetic_spy_2008q4, synthetic_vix_panic)
# without re-touching the prior phase blocks.
