"""Qullamaggie Setup A scan — SIG-02 / D-13.

Plan 06-04 (Wave 2) replaces every pytest.skip with a real assertion that
exercises the qullamaggie_setup_a(panel) signal. Until then the stubs lock
the canonical test names so 06-VALIDATION.md per-task map stays stable.
"""

# Wave: 2  (body filled by Plan 06-04 — see 06-VALIDATION.md "New test files")

import pytest


def test_setup_a_top_2pct_filter() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates SIG-02 percentile gate: ticker with rs_rating in top 1-2% "
        "passes; ticker at rs_rating=50 fails."
    )


def test_setup_a_dollar_volume_filter() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates SIG-02 liquidity gate: avg_dollar_volume_50d > $1.5M "
        "passes; < $1.5M fails."
    )


def test_setup_a_adr_pct_filter() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates SIG-02 ADR%(20) >= 4 gate: liquid + range-active passes; "
        "low-ADR tight names fail."
    )


def test_setup_a_combined_and_gate() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates SIG-02 AND-gate: qullamaggie_score=1 ONLY when all three "
        "conditions (RS top 1-2%, ADV > $1.5M, ADR% >= 4) fire."
    )
