"""Indicator purity invariant (IND-05).

Complements tests/test_architecture.py (forbidden-import AST check) with a
behavioral purity check: build_panel called twice on equivalent inputs returns
identical output, and never mutates its input panel.
"""

from __future__ import annotations

import pandas as pd

from screener.indicators.relative_strength import rs_panel
from screener.indicators.trend import sma_panel


def test_rs_panel_does_not_mutate_input() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=300)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [1.0] * 300,
            "high": [1.0] * 300,
            "low": [1.0] * 300,
            "close": [1.0] * 300,
            "volume": [1] * 300,
        },
        index=idx,
    )
    cols_before = list(panel.columns)
    _ = rs_panel(panel)
    assert list(panel.columns) == cols_before, "rs_panel mutated input columns"


def test_sma_panel_idempotent() -> None:
    """Calling sma_panel twice on identical input returns identical output."""
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=300)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [1.0] * 300,
            "high": [1.0] * 300,
            "low": [1.0] * 300,
            "close": [100.0] * 300,
            "volume": [1] * 300,
        },
        index=idx,
    )
    a = sma_panel(panel)
    b = sma_panel(panel)
    pd.testing.assert_frame_equal(a, b)
