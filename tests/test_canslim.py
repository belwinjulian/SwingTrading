"""CANSLIM C component overlay tests — SIG-03 / D-18.

Plan 06-04 (Wave 2) replaces every pytest.skip with a real assertion against
the canslim_c_overlay(panel, fundamentals, as_of_date) signal. D-18 ensures
L (RS) and M (regime) are NOT double-counted in earnings_component.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from screener.signals.canslim import (
    CANSLIM_C_MIN_EPS_YOY,
    canslim_c_overlay,
)


def _make_minimal_panel(ticker: str = "AAPL", date: str = "2024-06-01") -> pd.DataFrame:
    """One-row MultiIndex panel for unit testing."""
    idx = pd.MultiIndex.from_tuples([(ticker, pd.Timestamp(date))], names=["ticker", "date"])
    return pd.DataFrame(
        {"close": [150.0], "volume": [1_000_000.0], "adr_pct": [5.0]},
        index=idx,
    )


def _make_fundamentals(
    ticker: str,
    eps_yoy_growth: float,
    quarter_end: str = "2024-02-29",
    knowable_from: str = "2024-04-14",  # quarter_end + 45d
) -> pd.DataFrame:
    """Minimal FundamentalsSchema-compatible DataFrame for testing."""
    return pd.DataFrame(
        {
            "ticker": [ticker],
            "fiscal_quarter_end": [pd.Timestamp(quarter_end)],
            "eps_actual": [2.50],
            "eps_yoy_growth": [eps_yoy_growth],
            "knowable_from": [pd.Timestamp(knowable_from)],
            "next_earnings_date": [pd.NaT],
            "earnings_hour": ["unknown"],
        }
    )


def test_c_component_eps_yoy_25pct_passes() -> None:
    """SIG-03 C component: EPS YoY >= 25% => canslim_c_passes=True."""
    panel = _make_minimal_panel("AAPL", "2024-06-01")
    fundamentals = _make_fundamentals("AAPL", eps_yoy_growth=0.30)
    as_of = pd.Timestamp("2024-06-01")

    out = canslim_c_overlay(panel, fundamentals, as_of)

    assert "canslim_c_passes" in out.columns
    assert out["canslim_c_passes"].iloc[0] is True or out["canslim_c_passes"].iloc[0] == True, (
        f"Expected canslim_c_passes=True for eps_yoy_growth=0.30, "
        f"got {out['canslim_c_passes'].iloc[0]}"
    )


def test_c_component_eps_yoy_below_25pct_fails() -> None:
    """SIG-03 boundary: EPS YoY = 0.10 (below 25%) => canslim_c_passes=False."""
    panel = _make_minimal_panel("AAPL", "2024-06-01")
    fundamentals = _make_fundamentals("AAPL", eps_yoy_growth=0.10)
    as_of = pd.Timestamp("2024-06-01")

    out = canslim_c_overlay(panel, fundamentals, as_of)

    assert not out["canslim_c_passes"].iloc[0], (
        f"Expected canslim_c_passes=False for eps_yoy_growth=0.10, "
        f"got {out['canslim_c_passes'].iloc[0]}"
    )


def test_no_double_count() -> None:
    """D-18 de-duplication: canslim.py source must NOT reference rs_rating, regime_state,
    or regime_score (those are already counted in rs_component and regime soft gate).
    """
    # Use __file__ to locate the source regardless of working directory
    tests_dir = Path(__file__).resolve().parent
    src_path = tests_dir.parent / "src" / "screener" / "signals" / "canslim.py"
    src = src_path.read_text()

    assert "rs_rating" not in src, (
        "D-18 violation: canslim.py references rs_rating (L double-count). "
        "L is already captured in rs_component (rs_rating / 99)."
    )
    assert "regime_state" not in src, (
        "D-18 violation: canslim.py references regime_state (M double-count). "
        "M is already captured in the regime soft gate."
    )
    assert "regime_score" not in src, (
        "D-18 violation: canslim.py references regime_score (M double-count). "
        "M is already captured in the regime soft gate."
    )
