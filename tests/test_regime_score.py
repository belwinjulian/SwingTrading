"""regime_score property test (REG-02): regime_score ∈ [0, 1] for any input."""

from __future__ import annotations

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from screener.regime import _regime_score


@given(
    spy_above=st.booleans(),
    breadth=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    dist=st.integers(min_value=0, max_value=20),
    vix=st.floats(min_value=10.0, max_value=80.0, allow_nan=False, allow_infinity=False),
)
def test_regime_score_in_unit_interval(
    spy_above: bool, breadth: float, dist: int, vix: float
) -> None:
    df = pd.DataFrame(
        {
            "spy_above_200d": [spy_above],
            "breadth_pct": [breadth],
            "distribution_days": [dist],
            "vix_level": [vix],
        }
    )
    score = _regime_score(df).iloc[0]
    assert 0.0 <= float(score) <= 1.0
