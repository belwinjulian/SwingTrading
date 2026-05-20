"""OBV + dryup_ratio tests (IND-01, D-09)."""

from __future__ import annotations

import pandas as pd

from screener.indicators.volume import dryup_ratio_panel, obv_panel


def test_obv_panel_adds_obv_col() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=30)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 30,
            "high": [101.0] * 30,
            "low": [99.0] * 30,
            "close": [100.0] * 30,
            "volume": [1_000_000] * 30,
        },
        index=idx,
    )
    out = obv_panel(panel)
    assert "obv" in out.columns


def test_dryup_ratio_definition() -> None:
    """D-09: dryup_ratio = volume / SMA(volume, 50). For constant volume,
    dryup_ratio == 1.0 after the SMA has warmed up."""
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=100)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 100,
            "high": [101.0] * 100,
            "low": [99.0] * 100,
            "close": [100.0] * 100,
            "volume": [2_000_000] * 100,
        },
        index=idx,
    )
    out = dryup_ratio_panel(panel, length=50)
    assert "dryup_ratio" in out.columns
    # After warmup, ratio should equal 1.0 (constant volume / its own 50d SMA = 1.0)
    last = out["dryup_ratio"].iloc[-1]
    assert abs(last - 1.0) < 1e-6
