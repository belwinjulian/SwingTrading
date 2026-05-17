"""Playbook tagger tie-breaker tests — CMP-02 / CMP-03 / D-13 / D-14 / D-15.

Plan 06-04 (Wave 2): real assertions over the co-located
signals/composite.py::tag_playbook(panel) function. Emits one
playbook_tag per pick PLUS three diagnostic binary scores. D-14 says
Qullamaggie wins over Minervini when both fire. Final-constant tie-breaker
thresholds are LOCKED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from screener.signals.composite import (
    LEADER_MIN_RS,
    MINERVINI_MAX_FINAL_CONTRACTION_PCT,
    MINERVINI_MIN_BARS,
    QULL_MAX_BARS,
    QULL_MIN_ADR_PCT,
    tag_playbook,
)
from screener.indicators.patterns import encode_pattern_diagnostics


def _make_tag_panel(
    ticker: str = "AAPL",
    date: str = "2024-06-01",
    pattern_type: str = "none",
    pattern_bars: int = 0,
    final_contraction_depth: float = 1.0,
    adr_pct: float = 3.0,
    rs_rating: int = 60,
    passes_trend_template: bool = False,
    breakout_strength: float = 0.5,
) -> pd.DataFrame:
    """Build a 1-ticker, 1-date panel for tag_playbook unit testing."""
    if pattern_type == "vcp":
        diag = encode_pattern_diagnostics(
            {
                "type": "vcp",
                "n_contractions": 2,
                "depth_sequence": [0.25, final_contraction_depth],
                "first_leg_depth": 0.25,
                "final_contraction_depth": final_contraction_depth,
                "breakout_vol_multiple": 2.0,
                "breakout_strength": breakout_strength,
                "pivot_price": 150.0,
                "days_in_consolidation": pattern_bars,
            }
        )
    elif pattern_type == "flag":
        diag = encode_pattern_diagnostics(
            {
                "type": "flag",
                "flag_bars": pattern_bars,
                "range_tightness": 0.5,
                "vol_contraction_ratio": 0.7,
                "ma_anchor": "10/20/50",
                "breakout_strength": breakout_strength,
                "pivot_price": 150.0,
            }
        )
    else:
        diag = encode_pattern_diagnostics({"type": "none"})

    idx = pd.MultiIndex.from_tuples(
        [(ticker, pd.Timestamp(date))], names=["ticker", "date"]
    )
    vcp_passes = pattern_type == "vcp"
    flag_passes = pattern_type == "flag"
    return pd.DataFrame(
        {
            "close": [150.0],
            "adr_pct": [float(adr_pct)],
            "rs_rating": pd.array([rs_rating], dtype="Int64"),
            "passes_trend_template": [passes_trend_template],
            "vcp_passes": [vcp_passes],
            "flag_passes": [flag_passes],
            "breakout_strength": [float(breakout_strength)],
            "pattern_diagnostics": [diag],
            # Catalyst columns (not used by tag_playbook but must be present)
            "days_to_next_earnings": [30],
            "crossed_52w_high_within_60d": [False],
            "insider_cluster_buy": [False],
            "canslim_c_passes": [False],
        },
        index=idx,
    )


VALID_TAGS = frozenset(
    {"qullamaggie_continuation", "minervini_vcp", "leader_hold", "none"}
)


def test_tag_values_valid() -> None:
    """CMP-02 / RankingSnapshotSchema isin: every emitted playbook_tag is in the 4-value set."""
    panels = [
        _make_tag_panel(
            pattern_type="vcp",
            pattern_bars=12,
            final_contraction_depth=0.05,
            adr_pct=6.0,
            rs_rating=85,
            passes_trend_template=True,
        ),
        _make_tag_panel(
            pattern_type="flag",
            pattern_bars=30,  # > QULL_MAX_BARS=25, so Minervini wins if applicable
            adr_pct=6.0,
            rs_rating=55,
        ),
        _make_tag_panel(
            pattern_type="none",
            rs_rating=92,
            passes_trend_template=True,
        ),
        _make_tag_panel(
            pattern_type="none",
            rs_rating=40,
            passes_trend_template=False,
        ),
    ]
    combined = pd.concat(panels)
    out = tag_playbook(combined)

    tags = set(out["playbook_tag"].unique())
    assert tags <= VALID_TAGS, (
        f"Emitted playbook_tag values {tags} contain invalid values "
        f"(expected subset of {VALID_TAGS})"
    )


def test_d14_tiebreaker() -> None:
    """D-14: pick satisfying BOTH Qullamaggie AND Minervini gets qullamaggie_continuation.

    VCP with pattern_bars=12 (< QULL_MAX_BARS=25) AND adr_pct=6.0 (>= QULL_MIN_ADR_PCT=5.0)
    AND final_contraction_depth=0.05 (5% <= MINERVINI_MAX_FINAL_CONTRACTION_PCT=8.0%)
    => both conditions fire; Qullamaggie must win (D-14).

    Checker W8 regression: verify composite.py uses np.select with qull_mask FIRST.
    """
    panel = _make_tag_panel(
        ticker="NVDA",
        date="2024-06-01",
        pattern_type="vcp",
        pattern_bars=12,                    # < QULL_MAX_BARS=25 -> Qull fires
        final_contraction_depth=0.05,       # 5% <= MINERVINI_MAX_FINAL_CONTRACTION_PCT=8% -> MVP fires
        adr_pct=6.0,                        # >= QULL_MIN_ADR_PCT=5.0 -> Qull fires
        rs_rating=85,
        passes_trend_template=True,
    )
    out = tag_playbook(panel)
    ticker, dt = "NVDA", pd.Timestamp("2024-06-01")

    tag = out.loc[(ticker, dt), "playbook_tag"]
    assert tag == "qullamaggie_continuation", (
        f"D-14 violation: expected qullamaggie_continuation on overlap, got {tag!r}"
    )
    assert out.loc[(ticker, dt), "qullamaggie_score"] == 1, (
        "Expected qullamaggie_score=1 for D-14 overlap pick"
    )
    assert out.loc[(ticker, dt), "minervini_score"] == 1, (
        "Expected minervini_score=1 for D-14 overlap pick (both signals fired)"
    )

    # Checker W8 regression: verify np.select with Qullamaggie first in conditions list
    tests_dir = Path(__file__).resolve().parent
    src = (tests_dir.parent / "src" / "screener" / "signals" / "composite.py").read_text()
    assert "np.select(conditions, choices" in src, (
        "Checker W8: expected np.select(conditions, choices in composite.py"
    )
    assert "conditions = [qull_mask, mvp_mask, ldr_only]" in src, (
        "Checker W8: qull_mask must be FIRST in the conditions list for D-14 precedence"
    )


def test_d15_leader_hold() -> None:
    """D-15: passes_trend_template=True AND rs_rating=92 AND pattern_type='none' => leader_hold."""
    panel = _make_tag_panel(
        pattern_type="none",
        adr_pct=3.0,        # below QULL_MIN_ADR_PCT -> Qull does not fire
        rs_rating=92,       # >= LEADER_MIN_RS=90
        passes_trend_template=True,
    )
    out = tag_playbook(panel)
    ticker, dt = "AAPL", pd.Timestamp("2024-06-01")

    assert out.loc[(ticker, dt), "playbook_tag"] == "leader_hold", (
        f"Expected playbook_tag=leader_hold, got {out.loc[(ticker, dt), 'playbook_tag']!r}"
    )
    assert out.loc[(ticker, dt), "leader_hold_score"] == 1, (
        "Expected leader_hold_score=1"
    )
    assert out.loc[(ticker, dt), "qullamaggie_score"] == 0, (
        "Expected qullamaggie_score=0 for leader_hold pick"
    )
    assert out.loc[(ticker, dt), "minervini_score"] == 0, (
        "Expected minervini_score=0 for leader_hold pick"
    )


def test_d15_none_tag_excluded_from_report() -> None:
    """D-15: pick failing all three playbook scores gets playbook_tag='none'."""
    panel = _make_tag_panel(
        pattern_type="none",
        adr_pct=3.0,
        rs_rating=50,        # below LEADER_MIN_RS=90
        passes_trend_template=False,
    )
    out = tag_playbook(panel)
    ticker, dt = "AAPL", pd.Timestamp("2024-06-01")

    assert out.loc[(ticker, dt), "playbook_tag"] == "none", (
        f"Expected playbook_tag=none for failing pick, got {out.loc[(ticker, dt), 'playbook_tag']!r}"
    )
    assert out.loc[(ticker, dt), "qullamaggie_score"] == 0
    assert out.loc[(ticker, dt), "minervini_score"] == 0
    assert out.loc[(ticker, dt), "leader_hold_score"] == 0


def test_final_constants_locked() -> None:
    """D-13: all 5 tie-breaker constants have verbatim values and Final[...] annotation."""
    assert QULL_MAX_BARS == 25, f"Expected QULL_MAX_BARS=25, got {QULL_MAX_BARS}"
    assert QULL_MIN_ADR_PCT == 5.0, f"Expected QULL_MIN_ADR_PCT=5.0, got {QULL_MIN_ADR_PCT}"
    assert MINERVINI_MIN_BARS == 25, f"Expected MINERVINI_MIN_BARS=25, got {MINERVINI_MIN_BARS}"
    assert MINERVINI_MAX_FINAL_CONTRACTION_PCT == 8.0, (
        f"Expected MINERVINI_MAX_FINAL_CONTRACTION_PCT=8.0, "
        f"got {MINERVINI_MAX_FINAL_CONTRACTION_PCT}"
    )
    assert LEADER_MIN_RS == 90, f"Expected LEADER_MIN_RS=90, got {LEADER_MIN_RS}"

    # Verify Final[...] annotation via source scan
    tests_dir = Path(__file__).resolve().parent
    src = (tests_dir.parent / "src" / "screener" / "signals" / "composite.py").read_text()

    for const_name in [
        "QULL_MAX_BARS",
        "QULL_MIN_ADR_PCT",
        "MINERVINI_MIN_BARS",
        "MINERVINI_MAX_FINAL_CONTRACTION_PCT",
        "LEADER_MIN_RS",
    ]:
        # Check that the constant appears with Final[ annotation
        assert f"{const_name}: Final[" in src, (
            f"D-13: constant {const_name} must be annotated Final[...] in composite.py"
        )
