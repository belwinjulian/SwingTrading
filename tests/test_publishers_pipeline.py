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
