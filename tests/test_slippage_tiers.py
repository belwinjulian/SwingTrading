"""BCK-03: ADV-tiered slippage panel construction unit tests.

Phase 5 Wave 1 - body filled (Wave 0 stub replaced).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from screener.backtest.vbt_runner import _build_slippage_panel


def _make_ohlcv_panel(close: float, volume: int, n_bars: int = 60) -> pd.DataFrame:
    """Build a deterministic single-ticker OHLCV panel in read_panel() shape."""
    dates = pd.bdate_range("2024-01-01", periods=n_bars)
    df = pd.DataFrame(
        {
            "open": np.full(n_bars, close),
            "high": np.full(n_bars, close * 1.01),
            "low": np.full(n_bars, close * 0.99),
            "close": np.full(n_bars, close),
            "volume": np.full(n_bars, volume, dtype="int64"),
        },
        index=dates,
    )
    df.index.name = "date"
    df["ticker"] = "TST"
    return df.set_index("ticker", append=True).reorder_levels(["ticker", "date"])


def test_adv_above_50m_gets_5bps() -> None:
    """ADV = $100 x 600,000 = $60M (> $50M) -> 5 bps post-warmup."""
    panel = _make_ohlcv_panel(close=100.0, volume=600_000)
    slip = _build_slippage_panel(panel)
    # Post-warmup (bars 20+) should all be 5 bps.
    assert (slip.iloc[20:] == 0.0005).all().all(), "expected 5 bps for ADV > $50M post-warmup"


def test_adv_below_5m_gets_30bps() -> None:
    """ADV = $100 x 40,000 = $4M (< $5M) -> 30 bps post-warmup."""
    panel = _make_ohlcv_panel(close=100.0, volume=40_000)
    slip = _build_slippage_panel(panel)
    assert (slip.iloc[20:] == 0.0030).all().all(), "expected 30 bps for ADV < $5M post-warmup"


def test_warmup_nan_filled_with_worst_tier() -> None:
    """First 19 bars (NaN ADV) get 30 bps default - even when post-warmup is 5 bps."""
    panel = _make_ohlcv_panel(close=100.0, volume=600_000)  # post-warmup will be 5 bps
    slip = _build_slippage_panel(panel)
    assert (slip.iloc[:19] == 0.0030).all().all(), "expected 30 bps default on NaN warmup bars"
