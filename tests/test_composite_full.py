"""Composite full activation tests — CMP-01 / D-16.

Plan 06-04 (Wave 2) replaces every pytest.skip with real assertions over the
extended signals/composite.py: PHASE_4_ZEROED shrinks to frozenset(), and the
3 new component helpers (pattern/earnings/catalyst) populate the scoring loop
with non-zero values. D-13 scoring loop body MUST remain bytewise unchanged
(M2 ml_probability extension seam).
"""

# Wave: 2  (body filled by Plan 06-04 — see 06-VALIDATION.md "New test files")

import pytest


def test_phase_4_zeroed_empty() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-16: after Phase 6, PHASE_4_ZEROED == frozenset() — all "
        "six composite components are live; report placeholder lines for "
        "'--(Phase 6)' auto-disappear."
    )


def test_all_components_live() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates CMP-01: composite_score uses non-zero pattern_component "
        "(D-17), earnings_component (D-18 — C only), catalyst_component "
        "(D-11 — 3 boolean flags / 3) on a happy-path panel row."
    )


def test_weights_loop_unchanged() -> None:
    pytest.skip(
        "Phase 6 Wave 2 stub — Plan 06-04 fills body. "
        "Validates D-13 contract: the weights.items() scoring loop body in "
        "signals/composite.py::score is bytewise identical to its Phase 4 "
        "form. Adding new components is ABOVE the loop, never inside (the "
        "M2 ml_probability extension seam)."
    )
