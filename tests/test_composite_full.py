"""Composite full activation tests — CMP-01 / D-16.

Plan 06-04 (Wave 2): real assertions over the extended signals/composite.py.
PHASE_4_ZEROED shrinks to frozenset(), and the 3 new component helpers
(pattern/earnings/catalyst) populate the scoring loop with non-zero values.
D-13 scoring loop body MUST remain bytewise unchanged (M2 ml_probability
extension seam).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from screener.signals.composite import PHASE_4_ZEROED, score


def _make_full_panel() -> pd.DataFrame:
    """Build a synthetic 1-ticker panel with all required columns for score()."""
    dates = pd.bdate_range("2024-01-01", periods=260)
    ticker = "AAPL"
    idx = pd.MultiIndex.from_tuples([(ticker, d) for d in dates], names=["ticker", "date"])
    n = len(dates)
    # Minimum required columns for score()
    df = pd.DataFrame(
        {
            "close": [150.0] * n,
            "rs_rating": pd.array([85] * n, dtype="Int64"),
            "trend_template_score": pd.array([8] * n, dtype="Int64"),
            "dryup_ratio": [0.8] * n,
            # Phase 6 pattern component inputs
            "vcp_passes": [True] * n,
            "flag_passes": [False] * n,
            "breakout_strength": [0.7] * n,
            # Phase 6 earnings component input
            "canslim_c_passes": [True] * n,
            # Phase 6 catalyst component inputs
            "days_to_next_earnings": [10] * n,
            "crossed_52w_high_within_60d": [True] * n,
            "insider_cluster_buy": [False] * n,
        },
        index=idx,
    )
    return df


def test_phase_4_zeroed_empty() -> None:
    """D-16: after Phase 6, PHASE_4_ZEROED == frozenset() — all six components are live."""
    assert frozenset() == PHASE_4_ZEROED, (
        f"Expected PHASE_4_ZEROED == frozenset() after Phase 6 D-16 activation, "
        f"got {PHASE_4_ZEROED!r}"
    )


def test_all_components_live() -> None:
    """CMP-01: composite_score uses non-zero pattern/earnings/catalyst components."""
    panel = _make_full_panel()
    out = score(panel)

    # Verify all three previously-zeroed components are non-zero
    last_row = out.iloc[-1]

    assert last_row["pattern_component"] > 0, (
        f"Expected non-zero pattern_component, got {last_row['pattern_component']}"
    )
    assert last_row["earnings_component"] > 0, (
        f"Expected non-zero earnings_component, got {last_row['earnings_component']}"
    )
    assert last_row["catalyst_component"] > 0, (
        f"Expected non-zero catalyst_component, got {last_row['catalyst_component']}"
    )
    assert last_row["composite_score"] > 0, (
        f"Expected non-zero composite_score, got {last_row['composite_score']}"
    )


def test_weights_loop_unchanged() -> None:
    """D-13 contract: the weights.items() scoring loop body is verbatim from Phase 4.

    The M2 ml_probability extension seam requires that the loop body never be
    modified — adding a new component is done ABOVE the loop only.
    """
    tests_dir = Path(__file__).resolve().parent
    src_path = tests_dir.parent / "src" / "screener" / "signals" / "composite.py"
    src = src_path.read_text()

    assert "for key, w in weights.items():" in src, (
        "D-13 violation: 'for key, w in weights.items():' loop header not found in composite.py"
    )
    assert 'composite = composite + w * out[f"{key}_component"]' in src, (
        "D-13 violation: scoring loop body changed — "
        "'composite = composite + w * out[f\"{key}_component\"]' not found"
    )
