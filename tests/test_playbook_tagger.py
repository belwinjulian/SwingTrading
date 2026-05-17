"""Playbook tagger tie-breaker tests — CMP-02 / CMP-03 / D-13 / D-14 / D-15.

Plan 06-04 (Wave 2) replaces every pytest.skip with real assertions over the
co-located signals/composite.py::tag_playbook(panel) function. Emits one
playbook_tag per pick PLUS three diagnostic binary scores. D-14 says
Qullamaggie wins over Minervini when both fire. Final-constant tie-breaker
thresholds are LOCKED.
"""

# Wave: 2  (body filled by Plan 06-04 — see 06-VALIDATION.md "New test files")

import pytest


def test_tag_values_valid() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates CMP-02 / RankingSnapshotSchema isin: every emitted "
        "playbook_tag is in {qullamaggie_continuation, minervini_vcp, "
        "leader_hold, none}; pandera rejects anything else."
    )


def test_d14_tiebreaker() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-14: pick satisfying BOTH Qullamaggie AND Minervini "
        "(pattern_bars < QULL_MAX_BARS AND adr_pct >= QULL_MIN_ADR_PCT AND "
        "final_contraction_pct <= MINERVINI_MAX_FINAL_CONTRACTION_PCT) "
        "gets primary tag = qullamaggie_continuation (momentum-bias default)."
    )


def test_d15_leader_hold() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-15: passes_trend_template=True AND rs_rating=92 AND "
        "pattern_diagnostics={'type':'none'} => leader_hold_score=1, "
        "playbook_tag='leader_hold' (routed to the separate report section)."
    )


def test_d15_none_tag_excluded_from_report() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-15: pick failing all three playbook scores gets "
        "playbook_tag='none' (documented as excluded; actual report "
        "exclusion test lands in Plan 06-05 wire-up)."
    )


def test_final_constants_locked() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-13: QULL_MAX_BARS=25, QULL_MIN_ADR_PCT=5.0, "
        "MINERVINI_MIN_BARS=25, MINERVINI_MAX_FINAL_CONTRACTION_PCT=8.0, "
        "LEADER_MIN_RS=90 are Final[...]-annotated in signals/composite.py."
    )
