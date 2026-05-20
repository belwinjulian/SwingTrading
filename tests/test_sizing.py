"""tests/test_sizing.py — Phase 7 SIZ-01..05 unit tests (Plan 07-02 bodies)."""

from __future__ import annotations

import math

import pandas as pd

from screener.sizing import (
    EXTENDED_ATR,
    IN_ZONE_ATR,
    STOP_HELPERS,
    _stop_leader_hold,
    _stop_minervini_vcp,
    _stop_qullamaggie,
    _trail_rule_label,
    classify_atr_zone,
    compute_sizing,
)


def _empty_panel(tickers: list[str]) -> pd.DataFrame:
    """Minimal MultiIndex(ticker, date) panel — empty rows; sizing uses it
    only for the leader_hold swing-low lookback fallback path."""
    idx = pd.MultiIndex.from_product(
        [tickers, pd.date_range("2026-01-01", periods=1, freq="D")],
        names=["ticker", "date"],
    )
    return pd.DataFrame({"high": 0.0, "low": 0.0, "close": 0.0}, index=idx)


def test_shares_formula(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-01: shares = floor((eq × risk_pct × regime_score)/(entry − stop)), capped at 25% equity."""
    cross = sized_input_cross
    panel = _empty_panel(list(cross.index))
    out = compute_sizing(cross, panel, account_equity=100_000.0, risk_pct=0.01, regime_score=0.85)
    # QULL: stop=118, entry=120, risk=2; raw = floor(100_000*0.01*0.85 / 2) = 425;
    # cap = floor(100_000 * 0.25 / 120) = 208 → cap binds → 208.
    assert int(out.loc["QULL", "shares"]) == 208
    # VCP1: adr_pct=4.2, close=100 → adr_dollars=4.2; stop=92 → risk=8 > 4.2 → ADR-rejected.
    # Formula test uses a custom single-row cross with wide adr_pct to avoid the ADR reject.
    single = pd.DataFrame(
        {
            "close": [100.0],
            "low": [99.0],
            "high": [101.0],
            "atr_14": [1.5],
            "adr_pct": [10.0],  # wide ADR so risk=8 doesn't trigger rejection
            "playbook_tag": ["minervini_vcp"],
            "pattern_diagnostics": [cross.loc["VCP1", "pattern_diagnostics"]],
            "composite_score": [68.5],
            "regime_state": ["Confirmed Uptrend"],
            "regime_score": [0.85],
            "passes_trend_template": [True],
            "rs_rating": pd.array([88], dtype=pd.Int64Dtype()),
            "trend_template_score": pd.array([7], dtype=pd.Int64Dtype()),
            "volume_component": [0.6],
        },
        index=pd.Index(["VCP1"], name="ticker"),
    )
    out2 = compute_sizing(single, _empty_panel(["VCP1"]), 100_000.0, 0.01, 0.85)
    # stop=92, entry=100, risk=8; raw = floor(850/8) = 106;
    # cap = floor(25_000/100) = 250 → raw binds → 106.
    assert int(out2.loc["VCP1", "shares"]) == 106


def test_zero_regime_score_zero_shares(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-01 / Pitfall 6: regime_score=0 → shares=0 (no div-by-zero)."""
    cross = sized_input_cross
    panel = _empty_panel(list(cross.index))
    out = compute_sizing(cross, panel, account_equity=100_000.0, risk_pct=0.01, regime_score=0.0)
    # Every non-rejected row → shares=0; rejected rows already 0.
    assert (out["shares"] == 0).all()


def test_shares_nonneg_property() -> None:
    """Property: shares ≥ 0 for any valid input."""
    # Hand-crafted edge cases (hypothesis would inflate scope; this satisfies the property).
    rows = []
    for eq, rp, rg in [(100_000, 0.01, 0.5), (50_000, 0.005, 1.0), (1_000_000, 0.02, 0.1)]:
        cross = pd.DataFrame(
            {
                "close": [100.0],
                "low": [99.0],
                "high": [101.0],
                "atr_14": [1.5],
                "adr_pct": [4.0],
                "playbook_tag": ["qullamaggie_continuation"],
                "pattern_diagnostics": ['{"type": "flag"}'],
                "composite_score": [70.0],
                "regime_state": ["Confirmed Uptrend"],
                "regime_score": [rg],
                "passes_trend_template": [True],
                "rs_rating": pd.array([90], dtype=pd.Int64Dtype()),
                "trend_template_score": pd.array([7], dtype=pd.Int64Dtype()),
                "volume_component": [0.5],
            },
            index=pd.Index(["TEST"], name="ticker"),
        )
        out = compute_sizing(cross, _empty_panel(["TEST"]), eq, rp, rg)
        rows.append(int(out.loc["TEST", "shares"]))
    assert all(s >= 0 for s in rows), rows


def test_adr_reject_boundary(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-02: adr_rejected when risk_per_share > adr_dollars."""
    cross = sized_input_cross
    out = compute_sizing(cross, _empty_panel(list(cross.index)), 100_000.0, 0.01, 0.85)
    # REJC: adr_pct=0.3, close=80 → adr_dollars = 0.24; low=79.5 → risk=0.5 > 0.24 → reject.
    assert bool(out.loc["REJC", "adr_rejected"]) is True
    assert str(out.loc["REJC", "rejection_reason"]) == "adr_exceeded"
    assert int(out.loc["REJC", "shares"]) == 0
    # QULL: adr_pct=5.5, close=120 → adr_dollars=6.6; risk=2.0 ≤ 6.6 → not rejected.
    assert bool(out.loc["QULL", "adr_rejected"]) is False


def test_stop_dispatch_per_playbook() -> None:
    """SIZ-03 / SC-2: STOP_HELPERS[tag] is the correct private helper."""
    assert STOP_HELPERS["qullamaggie_continuation"] is _stop_qullamaggie
    assert STOP_HELPERS["minervini_vcp"] is _stop_minervini_vcp
    assert STOP_HELPERS["leader_hold"] is _stop_leader_hold
    assert set(STOP_HELPERS.keys()) == {
        "qullamaggie_continuation",
        "minervini_vcp",
        "leader_hold",
    }


def test_leader_swing_fallback(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-03: leader_hold falls back to 2×ATR when history is too short."""
    cross = sized_input_cross.loc[["LEAD"]].copy()  # leader_hold, atr_14=4
    out = compute_sizing(cross, _empty_panel(["LEAD"]), 100_000.0, 0.01, 0.85)
    # _empty_panel has 1 bar; LEADER_SWING_PIVOT_ORDER=3 → too short → 2×ATR=8 cap
    # entry=200, stop=200-8=192.
    assert math.isclose(float(out.loc["LEAD", "stop_price"]), 192.0, abs_tol=1e-9)


def test_vcp_stop_from_diagnostics(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-03: minervini_vcp stop = pivot_price × (1 − final_contraction_depth)."""
    out = compute_sizing(
        sized_input_cross.loc[["VCP1"]].copy(), _empty_panel(["VCP1"]), 100_000.0, 0.01, 0.85
    )
    # vcp_diag has pivot_price=100.0, final_contraction_depth=0.08 → stop = 92.0
    assert math.isclose(float(out.loc["VCP1", "stop_price"]), 92.0, abs_tol=1e-9)


def test_trail_label_dispatch() -> None:
    """SIZ-04 / D-08: trail label per playbook tag."""
    qull = pd.Series({"playbook_tag": "qullamaggie_continuation", "adr_pct": 5.0})
    vcp = pd.Series({"playbook_tag": "minervini_vcp", "adr_pct": 0.0})
    lead = pd.Series({"playbook_tag": "leader_hold", "adr_pct": 0.0})
    none = pd.Series({"playbook_tag": "none", "adr_pct": 0.0})
    assert _trail_rule_label(qull) == "20d SMA"
    assert _trail_rule_label(vcp) == "21d EMA (then 50d SMA after 15 bars)"
    assert _trail_rule_label(lead) == "50d SMA close"
    assert _trail_rule_label(none) == ""


def test_qull_trail_speed_tiers() -> None:
    """SIZ-04: Qullamaggie ADR%<4 → 50d SMA, 4–6 → 20d SMA, ≥6 → 10d SMA (boundaries inclusive at 4 and 6)."""
    base = {"playbook_tag": "qullamaggie_continuation"}
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 3.99})) == "50d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 4.0})) == "20d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 5.5})) == "20d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 5.99})) == "20d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 6.0})) == "10d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 7.5})) == "10d SMA"


def test_atr_zone_boundaries() -> None:
    """SIZ-05 / D-09: =0.66 → in-zone; =1.0 → extended; >1.0 → chase, skip."""
    assert classify_atr_zone(0.0) == "in-zone"
    assert classify_atr_zone(0.65999) == "in-zone"
    assert classify_atr_zone(IN_ZONE_ATR) == "in-zone"  # exactly 0.66
    assert classify_atr_zone(0.66001) == "extended"
    assert classify_atr_zone(0.85) == "extended"
    assert classify_atr_zone(EXTENDED_ATR) == "extended"  # exactly 1.0
    assert classify_atr_zone(1.0001) == "chase, skip"
    assert classify_atr_zone(2.5) == "chase, skip"


def test_pure_function_no_input_mutation(sized_input_cross: pd.DataFrame) -> None:
    """compute_sizing returns a NEW DataFrame; input is untouched."""
    cross = sized_input_cross.copy()  # snapshot the expected state
    cross_backup = cross.copy(deep=True)
    out = compute_sizing(cross, _empty_panel(list(cross.index)), 100_000.0, 0.01, 0.85)
    # Input columns unchanged.
    assert list(cross.columns) == list(cross_backup.columns)
    for col in cross_backup.columns:
        pd.testing.assert_series_equal(cross[col], cross_backup[col], check_names=False)
    # Output has 9 new columns.
    new_cols = set(out.columns) - set(cross.columns)
    assert new_cols == {
        "stop_price",
        "entry_price",
        "shares",
        "risk_per_share",
        "atr_zone",
        "pivot_distance_atr_breakout",
        "trail_rule_label",
        "adr_rejected",
        "rejection_reason",
    }
