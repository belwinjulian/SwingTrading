"""ATR + ADR% tests (IND-01, IND-04)."""

from __future__ import annotations

import pandas as pd

from screener.indicators.volatility import adr_pct_panel, atr_panel


def test_adr_pct_canonical_value() -> None:
    """RESEARCH Pattern 3: ADR%(20) for high=105/low=95 = 100*(1.10526-1) ≈ 10.526."""
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=30)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 30, "high": [105.0] * 30, "low": [95.0] * 30,
            "close": [100.0] * 30, "volume": [1] * 30,
        },
        index=idx,
    )
    out = adr_pct_panel(panel, length=20)
    assert "adr_pct" in out.columns
    last_adr = out["adr_pct"].iloc[-1]
    assert abs(last_adr - 10.526) < 0.01, f"expected ~10.526; got {last_adr}"


def test_atr_panel_adds_atr_14() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=30)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 30, "high": [101.0] * 30, "low": [99.0] * 30,
            "close": [100.0] * 30, "volume": [1] * 30,
        },
        index=idx,
    )
    out = atr_panel(panel, length=14)
    assert "atr_14" in out.columns
