"""SIG-04 + D-03 + D-07 + D-08 — publisher pipeline behavior tests."""

from __future__ import annotations

import pandas as pd
import pytest
import typer

from screener.publishers.pipeline import apply_regime_gate, validate_run


def test_soft_regime_gate_multiplies() -> None:
    """D-03: composite_score *= regime_score on the cross-section frame."""
    panel = pd.DataFrame(
        {"composite_score": [50.0, 80.0, 30.0]},
        index=pd.Index(["AAA", "BBB", "CCC"], name="ticker"),
    )
    out = apply_regime_gate(panel, regime_score=0.5)
    assert out.loc["AAA", "composite_score"] == 25.0
    assert out.loc["BBB", "composite_score"] == 40.0
    assert out.loc["CCC", "composite_score"] == 15.0
    # Original frame is untouched (.copy() inside apply_regime_gate).
    assert panel.loc["AAA", "composite_score"] == 50.0


def test_apply_regime_gate_rejects_out_of_range_pitfall_6() -> None:
    """Pitfall 6: regime_score must be in [0, 1] — defensive assertion."""
    panel = pd.DataFrame(
        {"composite_score": [50.0]}, index=pd.Index(["AAA"], name="ticker")
    )
    with pytest.raises(AssertionError, match="regime_score out of range"):
        apply_regime_gate(panel, regime_score=1.5)
    with pytest.raises(AssertionError, match="regime_score out of range"):
        apply_regime_gate(panel, regime_score=-0.1)


def test_pass_rate_warns_d07() -> None:
    """D-07: pass_rate > warn_threshold emits a structlog warning event but
    does NOT raise typer.Exit (no Correction state)."""
    # No exception expected.
    validate_run(
        pass_rate=0.30,
        regime_state="Confirmed Uptrend",
        warn_threshold=0.25,
        fail_threshold_with_correction=0.25,
    )
    validate_run(
        pass_rate=0.30,
        regime_state="Uptrend Under Pressure",
        warn_threshold=0.25,
        fail_threshold_with_correction=0.25,
    )


def test_data_quality_gate_failed_in_correction_d08() -> None:
    """D-08: pass_rate > fail_threshold AND regime_state == 'Correction'
    → typer.Exit(code=1)."""
    with pytest.raises(typer.Exit) as exc:
        validate_run(
            pass_rate=0.30,
            regime_state="Correction",
            warn_threshold=0.25,
            fail_threshold_with_correction=0.25,
        )
    assert exc.value.exit_code == 1


def test_validate_run_silent_below_threshold() -> None:
    """Below warn threshold → no warning, no error, no exit (silent pass)."""
    # No exception expected.
    validate_run(
        pass_rate=0.10,
        regime_state="Correction",  # even Correction is fine if rate is low
        warn_threshold=0.25,
        fail_threshold_with_correction=0.25,
    )
    validate_run(
        pass_rate=0.05,
        regime_state="Confirmed Uptrend",
        warn_threshold=0.25,
        fail_threshold_with_correction=0.25,
    )


def test_validate_run_correction_with_low_rate_does_not_fail() -> None:
    """D-08 ANDs the conditions: Correction + low pass_rate is acceptable."""
    validate_run(
        pass_rate=0.20,
        regime_state="Correction",
        warn_threshold=0.25,
        fail_threshold_with_correction=0.25,
    )  # No exception.


# --- REVIEW IN-02 (iter 3): independent-threshold regression tests ---------
#
# CR-01 (iter 1) flattened validate_run so warn_threshold and
# fail_threshold_with_correction are independent control surfaces. All the
# tests above pass warn==fail==0.25, which cannot distinguish the flattened
# form from a re-nested form (hard-fail check nested inside the warn check).
# These two tests lock in the independent-control-surface semantic so a
# future re-nest is caught by the suite.


def test_validate_run_distinct_thresholds_warn_only() -> None:
    """REVIEW IN-02 regression: warn=0.10 < fail=0.30, pass_rate=0.20.

    pass_rate (0.20) > warn (0.10) -> warning fires (no exception).
    pass_rate (0.20) <= fail (0.30) -> no hard-fail even in Correction.

    Exercises the documented healthy two-tier configuration where the warn
    threshold is BELOW the hard-fail threshold (production defaults: 0.15
    warn, 0.25 hard-fail). Locks in CR-01's flatten — would still pass if
    the inner `if` were re-nested, but pairs with the hard_fail_only test
    below which would NOT pass if re-nested.
    """
    # Confirmed Uptrend: warn fires, no exit.
    validate_run(
        pass_rate=0.20,
        regime_state="Confirmed Uptrend",
        warn_threshold=0.10,
        fail_threshold_with_correction=0.30,
    )
    # Correction with same numbers: warn fires, still no exit (below fail).
    validate_run(
        pass_rate=0.20,
        regime_state="Correction",
        warn_threshold=0.10,
        fail_threshold_with_correction=0.30,
    )


def test_validate_run_distinct_thresholds_hard_fail_only() -> None:
    """REVIEW IN-02 regression: warn=0.30 > fail=0.20, pass_rate=0.25 in
    Correction MUST hard-fail even though pass_rate is BELOW warn.

    This is the test that catches a CR-01 regression. If the inner
    Correction-check were re-nested inside `if pass_rate > warn_threshold`,
    pass_rate=0.25 would not enter the outer block (0.25 < 0.30) and the
    typer.Exit would never fire. The flattened form raises correctly
    because the two checks are independent.
    """
    with pytest.raises(typer.Exit) as exc:
        validate_run(
            pass_rate=0.25,
            regime_state="Correction",
            warn_threshold=0.30,
            fail_threshold_with_correction=0.20,
        )
    assert exc.value.exit_code == 1

    # Sanity: same numbers but non-Correction state must NOT raise (D-08
    # requires Correction AND pass_rate > fail).
    validate_run(
        pass_rate=0.25,
        regime_state="Confirmed Uptrend",
        warn_threshold=0.30,
        fail_threshold_with_correction=0.20,
    )
