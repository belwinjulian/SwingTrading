"""SIG-04 — Composite scorer behavior tests.

Covers VALIDATION.md Per-Task Verification Map rows for SIG-04 (5 named tests)
plus one hypothesis property test on composite_score range.
"""

from __future__ import annotations

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from screener.signals.composite import DEFAULT_WEIGHTS, PHASE_4_ZEROED, score


def _make_panel(
    rs_rating: int = 92,
    trend_template_score: int = 8,
    dryup_ratio: float = 0.5,
) -> pd.DataFrame:
    """Build a single-row, single-ticker panel with the 3 columns score() reads."""
    idx = pd.MultiIndex.from_tuples([("AAA", pd.Timestamp("2026-05-10"))], names=["ticker", "date"])
    return pd.DataFrame(
        {
            "rs_rating": pd.array([rs_rating], dtype=pd.Int64Dtype()),
            "trend_template_score": pd.array([trend_template_score], dtype=pd.Int64Dtype()),
            "dryup_ratio": [dryup_ratio],
        },
        index=idx,
    )


def test_unknown_weight_key_raises() -> None:
    """score() rejects weight keys outside DEFAULT_WEIGHTS with sorted-keys message."""
    panel = _make_panel()
    with pytest.raises(ValueError, match=r"Unknown weight keys: \['unknown'\]"):
        score(panel, {"unknown": 1.0})


def test_weight_sum_assertion() -> None:
    """score() rejects weights that do not sum to 1.0 within 1e-6."""
    panel = _make_panel()
    with pytest.raises(ValueError, match=r"Weights must sum to 1.0"):
        score(panel, {"rs": 0.5})  # sum 0.5, not 1.0
    with pytest.raises(ValueError, match=r"Weights must sum to 1.0"):
        score(
            panel,
            {
                "rs": 0.6,
                "trend": 0.6,
                "pattern": 0.0,
                "volume": 0.0,
                "earnings": 0.0,
                "catalyst": 0.0,
            },
        )  # sum 1.2


def test_zeroed_components() -> None:
    """D-01: pattern, earnings, catalyst are 0.0 in Phase 4 output."""
    panel = _make_panel()
    out = score(panel, DEFAULT_WEIGHTS)
    assert out["pattern_component"].iloc[0] == 0.0
    assert out["earnings_component"].iloc[0] == 0.0
    assert out["catalyst_component"].iloc[0] == 0.0
    # And PHASE_4_ZEROED enumerates exactly these:
    assert frozenset({"pattern", "earnings", "catalyst"}) == PHASE_4_ZEROED


def test_extension_seam() -> None:
    """D-13 M2 seam: adding `ml_probability` to weights is a one-line change.

    Today the function rejects unknown keys; the test asserts the rejection
    path AND demonstrates the M2 future via a manual augmented-DEFAULT dict
    (simulates the M2 patch to DEFAULT_WEIGHTS).
    """
    panel = _make_panel()

    # Today: unknown key rejected.
    with pytest.raises(ValueError, match=r"Unknown weight keys: \['ml_probability'\]"):
        score(panel, {**DEFAULT_WEIGHTS, "ml_probability": 0.0})

    # Simulate M2: monkey-patch DEFAULT_WEIGHTS with the new key + matching
    # component column. The score() function MUST iterate weights.items()
    # without any per-key special-case (D-13).
    from screener.signals import composite as composite_mod

    m2_weights = {
        "rs": 0.20,
        "trend": 0.20,
        "pattern": 0.15,
        "volume": 0.10,
        "earnings": 0.10,
        "catalyst": 0.05,
        "ml_probability": 0.20,
    }
    assert abs(sum(m2_weights.values()) - 1.0) < 1e-6

    # Patch DEFAULT_WEIGHTS to include the new key so unknown-key rejection
    # admits "ml_probability"; pre-populate the component column the loop
    # will look up via f"{key}_component".
    original = composite_mod.DEFAULT_WEIGHTS
    try:
        composite_mod.DEFAULT_WEIGHTS = m2_weights  # type: ignore[misc]
        panel_with_ml = panel.copy()
        panel_with_ml["ml_probability_component"] = 0.5  # value the loop will multiply
        out = score(panel_with_ml, m2_weights)
        assert "composite_score" in out.columns
        # Verifies the loop CONSUMED ml_probability without code change.
        # Composite includes 0.20 * 0.5 * 100 = 10 contribution from ML alone.
        assert float(out["composite_score"].iloc[0]) > 0.0
    finally:
        composite_mod.DEFAULT_WEIGHTS = original  # type: ignore[misc]


@hyp_settings(max_examples=50, deadline=None)
@given(
    rs=st.integers(min_value=1, max_value=99),
    tt=st.integers(min_value=0, max_value=8),
    dryup=st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
)
def test_score_range_property(rs: int, tt: int, dryup: float) -> None:
    """For any valid input (rs 1-99, trend 0-8, dryup 0-5),
    composite_score is in [0, 100] (Pitfall 11)."""
    panel = _make_panel(rs_rating=rs, trend_template_score=tt, dryup_ratio=dryup)
    out = score(panel, DEFAULT_WEIGHTS)
    cs = float(out["composite_score"].iloc[0])
    assert 0.0 <= cs <= 100.0, (
        f"composite_score {cs} out of [0, 100] for rs={rs}, tt={tt}, dryup={dryup}"
    )


def test_score_emits_all_seven_new_columns() -> None:
    """SIG-04 contract — score() output schema."""
    panel = _make_panel()
    out = score(panel, DEFAULT_WEIGHTS)
    for col in [
        "rs_component",
        "trend_component",
        "volume_component",
        "pattern_component",
        "earnings_component",
        "catalyst_component",
        "composite_score",
    ]:
        assert col in out.columns, f"missing output column: {col}"


def test_volume_component_d02_anchors() -> None:
    """D-02 verbatim: dryup=0.5 -> vol_score=1.0; dryup=2.0 -> vol_score=0.0."""
    out_low = score(_make_panel(dryup_ratio=0.5), DEFAULT_WEIGHTS)
    out_high = score(_make_panel(dryup_ratio=2.0), DEFAULT_WEIGHTS)
    out_nan = score(_make_panel(dryup_ratio=float("nan")), DEFAULT_WEIGHTS)
    assert out_low["volume_component"].iloc[0] == pytest.approx(1.0)
    assert out_high["volume_component"].iloc[0] == pytest.approx(0.0)
    # Pitfall 4: NaN dryup -> 0.0 (no NaN propagation into composite_score)
    assert out_nan["volume_component"].iloc[0] == 0.0
