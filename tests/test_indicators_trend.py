"""SMA + _safe_sma tests (IND-01, RESEARCH Pitfall 2)."""

from __future__ import annotations

import pandas as pd
import pytest

from screener.indicators.trend import _safe_sma, sma_panel


def test_safe_sma_short_series_returns_nan_series() -> None:
    """Pitfall 2: ta.sma returns None on input shorter than length; the wrapper
    must return a NaN-filled Series of the same index, never None."""
    short = pd.Series([1.0, 2.0, 3.0], name="close")
    result = _safe_sma(short, length=200)
    assert result is not None
    assert isinstance(result, pd.Series)
    assert len(result) == 3
    assert result.isna().all()


def test_sma_panel_adds_5_columns() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=300)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 300,
            "high": [101.0] * 300,
            "low": [99.0] * 300,
            "close": [100.0] * 300,
            "volume": [1_000_000] * 300,
        },
        index=idx,
    )
    out = sma_panel(panel)
    for L in (10, 20, 50, 150, 200):
        assert f"sma_{L}" in out.columns
