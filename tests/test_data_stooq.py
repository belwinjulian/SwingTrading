"""data/stooq.py tests (DAT-03 fallback path).

Covers VALIDATION.md lines 70-72. Uses the synthetic_stooq_descending_df
fixture and patches pandas_datareader.data.DataReader so no live HTTP
reaches Stooq from CI.
"""

from __future__ import annotations

from datetime import date
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from screener.data.stooq import fetch_ohlcv
from screener.persistence import StaleOrEmptyError

REF_DATE = date(2026, 4, 30)


def test_normalize_columns_and_order(synthetic_stooq_descending_df: pd.DataFrame) -> None:
    """Stooq adapter sorts ascending and lowercases columns."""
    with mock.patch(
        "screener.data.stooq.pdr.DataReader", return_value=synthetic_stooq_descending_df
    ):
        df = fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
    assert df.index.is_monotonic_increasing, "Stooq adapter must return ascending index"
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}, (
        f"Columns must be lowercase canonical; got {list(df.columns)}"
    )


def test_empty_raises() -> None:
    """An empty DataFrame from pdr.DataReader raises StaleOrEmptyError."""
    empty = pd.DataFrame(
        {"Open": [], "High": [], "Low": [], "Close": [], "Volume": []},
        index=pd.DatetimeIndex([]),
    )
    with mock.patch("screener.data.stooq.pdr.DataReader", return_value=empty):
        with pytest.raises(StaleOrEmptyError, match="empty"):
            fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)


def test_stooq_stale_fails() -> None:
    """A Stooq fetch whose last bar is > 4 business days old fails the recency invariant."""
    end_stale = REF_DATE - pd.tseries.offsets.BDay(10)
    idx = pd.bdate_range(end=end_stale, periods=20)
    stale = pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            "Low": np.full(len(idx), 99.0),
            "Close": np.full(len(idx), 100.5),
            "Volume": np.full(len(idx), 1_000_000, dtype="int64"),
        },
        index=idx,
    )
    with mock.patch("screener.data.stooq.pdr.DataReader", return_value=stale):
        with pytest.raises(StaleOrEmptyError, match="stale"):
            fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
