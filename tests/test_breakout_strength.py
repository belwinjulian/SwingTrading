"""Breakout-strength formula tests — D-06 / Pitfall 10.

Plan 06-02 (Wave 1) fills the bodies of these 5 tests over the
indicators/patterns.py::breakout_strength(vol, sma_vol_50) helper. Formula:
clip((vol / sma_vol_50 - 1.0) / 1.5, 0, 1). Pitfall 10: NaN inputs and
divide-by-zero must produce 0.0, not propagate NaN downstream.
"""

# Wave: 1  (bodies filled by Plan 06-02 — see 06-VALIDATION.md "New test files")

import numpy as np
import pandas as pd
import pytest

from screener.indicators.patterns import breakout_strength


def test_breakout_strength_1_5x_sma_returns_033() -> None:
    """D-06: vol/sma=1.5 -> strength = (1.5-1.0)/1.5 = 0.333..."""
    result = breakout_strength(pd.Series([1.5]), pd.Series([1.0]))
    assert result.iloc[0] == pytest.approx(1.0 / 3.0, abs=1e-6)


def test_breakout_strength_3x_sma_returns_1() -> None:
    """D-06: vol/sma=3.0 -> strength clips to 1.0 (max)."""
    result = breakout_strength(pd.Series([3.0]), pd.Series([1.0]))
    assert result.iloc[0] == 1.0


def test_breakout_strength_below_baseline_returns_0() -> None:
    """D-06: vol/sma=1.0 -> strength clips to 0.0 (no breakout)."""
    result = breakout_strength(pd.Series([1.0]), pd.Series([1.0]))
    assert result.iloc[0] == 0.0


def test_breakout_strength_nan_input_returns_0() -> None:
    """Pitfall 10: NaN volume returns 0.0; NaN MUST NOT propagate into composite_score."""
    result = breakout_strength(pd.Series([np.nan]), pd.Series([100.0]))
    assert result.iloc[0] == 0.0


def test_breakout_strength_zero_sma_returns_0() -> None:
    """Pitfall 10: sma_vol_50 == 0 (insufficient history) returns 0.0 without raising."""
    result = breakout_strength(pd.Series([100.0]), pd.Series([0.0]))
    assert result.iloc[0] == 0.0
