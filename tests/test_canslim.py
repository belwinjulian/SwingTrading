"""CANSLIM C component overlay tests — SIG-03 / D-18.

Plan 06-04 (Wave 2) replaces every pytest.skip with a real assertion against
the canslim_c_overlay(panel, fundamentals, as_of_date) signal. D-18 ensures
L (RS) and M (regime) are NOT double-counted in earnings_component.
"""

# Wave: 2  (body filled by Plan 06-04 — see 06-VALIDATION.md "New test files")

import pytest


def test_c_component_eps_yoy_25pct_passes() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates SIG-03 C component: ticker with quarterly EPS YoY >= 25% "
        "AND knowable_from <= as_of_date emits canslim_c_passes=True."
    )


def test_c_component_eps_yoy_below_25pct_fails() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates SIG-03 boundary: ticker with EPS YoY = 24.9% emits "
        "canslim_c_passes=False; 25.0% boundary passes."
    )


def test_no_double_count() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-18 de-duplication: earnings_component reads ONLY the "
        "C component (canslim_c_passes); rs_rating (L) and regime_state "
        "(M) MUST NOT contribute to earnings_component (already counted "
        "in rs_component and the regime soft gate respectively)."
    )
