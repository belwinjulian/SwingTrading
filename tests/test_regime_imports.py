"""RED gate: regime module imports and public API surface (Task 1 TDD gate).

These tests MUST fail until regime.py is replaced with its full body.
All symbols below are currently not defined in the 7-line stub.
"""

from __future__ import annotations


def test_regime_public_api_importable() -> None:
    """All public symbols from the plan's artifact spec must be importable."""
    from screener.regime import (  # noqa: F401
        RegimeState,
        _classify_state,
        _compute_distribution_days,
        _regime_score,
        build_history,
        compute_for_date,
    )
