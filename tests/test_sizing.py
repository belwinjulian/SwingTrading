"""tests/test_sizing.py — Phase 7 SIZ-01..05 unit tests.

Skeletons land in Plan 07-01 (Wave 0). Bodies land in Plan 07-02 (Wave 1).
Every test name comes from RESEARCH §Validation Architecture Test Map verbatim.
"""
from __future__ import annotations

import pytest


def test_shares_formula() -> None:
    """SIZ-01: shares = floor((eq × risk_pct × regime_score) / (entry − stop)), capped at 25% equity."""
    pytest.skip("Plan 07-02")


def test_zero_regime_score_zero_shares() -> None:
    """SIZ-01 / Pitfall 6: regime_score=0 → shares=0 (no div-by-zero)."""
    pytest.skip("Plan 07-02")


def test_shares_nonneg_property() -> None:
    """Property: shares ≥ 0 for any valid input (hypothesis-driven)."""
    pytest.skip("Plan 07-02")


def test_adr_reject_boundary() -> None:
    """SIZ-02: adr_rejected when risk_per_share > adr_dollars (boundary semantics)."""
    pytest.skip("Plan 07-02")


def test_stop_dispatch_per_playbook() -> None:
    """SIZ-03 / SC-2: STOP_HELPERS[tag] is the correct private helper for each playbook tag."""
    pytest.skip("Plan 07-02")


def test_leader_swing_fallback() -> None:
    """SIZ-03: leader_hold falls back to 2×ATR when find_pivots returns empty."""
    pytest.skip("Plan 07-02")


def test_vcp_stop_from_diagnostics() -> None:
    """SIZ-03: minervini_vcp stop = pivot_price × (1 - final_contraction_depth) from pattern_diagnostics."""
    pytest.skip("Plan 07-02")


def test_trail_label_dispatch() -> None:
    """SIZ-04 / D-08: trail label per playbook tag (Qull / VCP / leader)."""
    pytest.skip("Plan 07-02")


def test_qull_trail_speed_tiers() -> None:
    """SIZ-04: Qullamaggie ADR%<4 → 50d SMA, 4–6 → 20d SMA, ≥6 → 10d SMA (boundaries inclusive at 4 and 6)."""
    pytest.skip("Plan 07-02")


def test_atr_zone_boundaries() -> None:
    """SIZ-05 / D-09: pivot_distance_atr=0.66 → in-zone; =1.0 → extended; >1.0 → chase, skip."""
    pytest.skip("Plan 07-02")


def test_pure_function_no_input_mutation() -> None:
    """compute_sizing returns a NEW DataFrame; input is untouched (CLAUDE.md pure-fn rule)."""
    pytest.skip("Plan 07-02")
