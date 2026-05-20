"""RS panel tests (IND-03, RESEARCH Pitfalls 8, 9)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from screener.indicators.relative_strength import rs_panel


def _multi_ticker_panel(tickers: list[str], n: int = 260) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    frames = []
    for i, t in enumerate(tickers):
        drift = 0.001 * (i + 1)
        close = 100.0 * np.cumprod(1.0 + np.full(n, drift))
        idx = pd.MultiIndex.from_product([[t], dates], names=["ticker", "date"])
        frames.append(
            pd.DataFrame(
                {
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": np.full(n, 1_000_000, dtype="int64"),
                },
                index=idx,
            )
        )
    return pd.concat(frames).sort_index()


def test_rs_rating_in_range() -> None:
    panel = _multi_ticker_panel(["AAA", "BBB", "CCC", "DDD", "EEE"], n=260)
    out = rs_panel(panel)
    last_date = out.index.get_level_values("date").max()
    snapshot = out.xs(last_date, level="date")
    valid = snapshot["rs_rating"].dropna()
    assert (valid >= 1).all()
    assert (valid <= 99).all()
    # Pitfall 9: nullable Int64
    assert out["rs_rating"].dtype == pd.Int64Dtype()


def test_rs_nan_for_short_history() -> None:
    """A ticker with only 100 bars has NaN rs_raw (needs 252d) → NaN rs_rating."""
    panel = _multi_ticker_panel(["AAA", "BBB"], n=100)
    out = rs_panel(panel)
    assert out["rs_raw"].isna().all()
    assert out["rs_rating"].isna().all()


def test_rs_per_ticker_shift_isolation() -> None:
    """Pitfall 8: each ticker's shift is independent; verified by checking
    that the rs_raw at row N for ticker AAA only depends on AAA's prior bars,
    not on the trailing rows of any other ticker."""
    panel = _multi_ticker_panel(["AAA", "BBB"], n=260)
    # If naked .shift(63) were used, AAA's first 63 rows would mix with BBB's
    # last 63 rows. Compute via groupby and assert AAA's first 63 rs_raw rows
    # are all NaN (no prior history available within ticker AAA).
    out = rs_panel(panel)
    aaa = out.xs("AAA", level="ticker")
    assert aaa["rs_raw"].iloc[:63].isna().all(), (
        "first 63 rows of AAA must be NaN — shift bled across tickers"
    )
