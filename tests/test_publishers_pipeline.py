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


# --- Phase 6 pipeline DAG tests (D-13b structural + Phase 6 step ordering) ---
#
# Checker B3: these tests are NOT pseudo-code; they ship concrete bodies
# that are run verbatim. The monkeypatch style mirrors Plan 03 Task 3.


import datetime as dt  # noqa: E402


def _make_synthetic_panel_with_vcp(snapshot_date: str = "2026-05-16") -> pd.DataFrame:
    """Build a tiny (1-ticker, 1-date) panel with a pre-baked VCP diagnostics
    string. Saves the executor from rebuilding fixtures across the three tests.
    """
    snap_ts = pd.Timestamp(snapshot_date)
    idx = pd.MultiIndex.from_tuples([("AAPL", snap_ts)], names=["ticker", "date"])
    diag_json = (
        '{"type":"vcp","n_contractions":2,"pivot_price":175.5,'
        '"breakout_vol_multiple":2.1,"breakout_strength":0.73,'
        '"days_in_consolidation":24,"depth_sequence":[0.12,0.06],'
        '"first_leg_depth":0.12,"final_contraction_depth":0.06,'
        '"legs":['
        '{"leg_idx":0,"start_date":"2026-04-01","end_date":"2026-04-10",'
        '"high":180.0,"low":158.4,"depth":0.12,"avg_volume":1250000.0},'
        '{"leg_idx":1,"start_date":"2026-04-15","end_date":"2026-04-25",'
        '"high":178.0,"low":167.32,"depth":0.06,"avg_volume":910000.0}'
        ']}'
    )
    return pd.DataFrame(
        {
            "close": [175.5], "open": [174.0], "high": [176.0], "low": [173.5],
            "volume": [2_100_000.0],
            "vcp_passes": [True], "flag_passes": [False],
            "pivot_price": [175.5], "breakout_strength": [0.73],
            "pattern_diagnostics": [diag_json],
            "high_52w": [175.5],
            "rs_rating": pd.array([92], dtype="Int64"),
            "passes_trend_template": [True],
            "trend_template_score": pd.array([8], dtype="Int64"),
            "adr_pct": [6.0], "atr_14": [3.2],
            "sma_10": [170.0], "sma_20": [168.0], "sma_50": [162.0],
            "sma_150": [150.0], "sma_200": [148.0],
        },
        index=idx,
    )


def _make_regime_row_for_test() -> "pd.Series":
    """Minimal regime row for pipeline tests that don't test regime logic."""
    return pd.Series({
        "regime_state": "Confirmed Uptrend",
        "regime_score": 1.0,
        "spy_above_200d": True,
        "breadth_pct": 67.0,
        "distribution_days": 2,
        "vix_level": 16.4,
    })


def test_run_pipeline_includes_phase_6_steps(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Assert the new step ordering: patterns -> qull -> read_fundamentals
    -> canslim -> _add_catalyst_columns -> score -> tag_playbook -> snapshot.
    """
    from screener.publishers import pipeline as pl
    from screener import persistence
    import screener.signals.qullamaggie as q
    import screener.signals.canslim as c
    import screener.signals.composite as comp

    snap_ts = pd.Timestamp("2026-05-16")
    idx = pd.MultiIndex.from_tuples([("AAPL", snap_ts)], names=["ticker", "date"])
    # Panel must have composite_score for apply_regime_gate to work when not patched.
    panel = _make_synthetic_panel_with_vcp("2026-05-16")
    # Add composite_score and passes_trend_template so downstream phases don't fail.
    panel = panel.assign(
        composite_score=pd.Series([50.0], index=panel.index),
        passes_trend_template=pd.Series([True], index=panel.index),
    )
    cross_panel = panel.xs(snap_ts, level="date")

    empty_fund = pd.DataFrame(columns=[
        "ticker", "fiscal_quarter_end", "eps_actual", "eps_yoy_growth",
        "knowable_from", "next_earnings_date", "next_earnings_hour",
        "source", "ingested_at",
    ])
    calls: list[str] = []

    def _trace(name: str, ret: object):  # type: ignore[no-untyped-def]
        def _f(*a: object, **kw: object) -> object:  # type: ignore[no-untyped-def]
            calls.append(name)
            return ret
        return _f

    # Patch the cross-section step helpers that come after tag_playbook.
    import screener.publishers.report as report_mod
    monkeypatch.setattr(pl, "compute_for_date", _trace("compute_for_date", _make_regime_row_for_test()))
    monkeypatch.setattr(pl, "apply_regime_gate", _trace("apply_regime_gate", cross_panel))
    monkeypatch.setattr(pl, "validate_run", _trace("validate_run", None))

    monkeypatch.setattr(pl, "build_panel", _trace("build_panel", panel))
    monkeypatch.setattr(pl, "passes_trend_template", _trace("passes_trend_template", panel))
    monkeypatch.setattr(q, "passes_qullamaggie_setup_a", _trace("qull", panel))
    monkeypatch.setattr(persistence, "read_fundamentals", _trace("read_fundamentals", empty_fund))
    monkeypatch.setattr(c, "canslim_c_overlay", _trace("canslim", panel))
    monkeypatch.setattr(pl, "_add_catalyst_columns", _trace("catalyst_cols", panel))
    monkeypatch.setattr(pl, "score", _trace("score", panel))
    monkeypatch.setattr(comp, "tag_playbook", _trace("tag_playbook", panel))
    # Patch _add_publisher_columns (imported from report inside run_pipeline)
    monkeypatch.setattr(report_mod, "_add_publisher_columns",
                        _trace("add_pub_cols", cross_panel.assign(
                            ticker="AAPL", rank=pd.array([1], dtype="Int64"),
                            composite_score=pd.Series([50.0], index=cross_panel.index),
                        )))
    monkeypatch.setattr(pl, "write_snapshot", _trace("write_snapshot", tmp_path / "snap.parquet"))
    monkeypatch.setattr(persistence, "write_pattern_audit_atomic",
                        _trace("write_pattern_audit", tmp_path / "audit.parquet"))
    monkeypatch.setattr(persistence, "read_insider_cluster_buy",
                        _trace("cluster", set()))

    pl.run_pipeline(snapshot_date="2026-05-16", write_report=False)

    # Order assertions — every later call follows its prerequisite
    for prereq, follower in [
        ("read_fundamentals", "canslim"),
        ("canslim", "catalyst_cols"),
        ("catalyst_cols", "score"),
        ("score", "tag_playbook"),
        ("tag_playbook", "write_snapshot"),
    ]:
        assert prereq in calls and follower in calls, f"missing {prereq}/{follower}: {calls}"
        assert calls.index(prereq) < calls.index(follower), \
            f"{prereq} must precede {follower}: {calls}"


def test_run_pipeline_writes_pattern_audit(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """When the cross-section has a VCP pick with a real `legs` sub-field,
    pipeline.run_pipeline must call persistence.write_pattern_audit_atomic
    with a non-empty DataFrame conforming to PatternAuditSchema.
    """
    from screener.publishers import pipeline as pl
    from screener import persistence
    import screener.signals.qullamaggie as q
    import screener.signals.canslim as c
    import screener.signals.composite as comp

    panel = _make_synthetic_panel_with_vcp("2026-05-16")
    empty_fund = pd.DataFrame(columns=[
        "ticker", "fiscal_quarter_end", "eps_actual", "eps_yoy_growth",
        "knowable_from", "next_earnings_date", "next_earnings_hour",
        "source", "ingested_at",
    ])
    captured: dict = {}

    def _fake_write_audit(df: pd.DataFrame, snapshot_date: str) -> object:
        captured["df"] = df.copy()
        captured["snapshot_date"] = snapshot_date
        return tmp_path / f"{snapshot_date}.parquet"

    snap_ts2 = pd.Timestamp("2026-05-16")
    cross2 = panel.xs(snap_ts2, level="date") if snap_ts2 in panel.index.get_level_values("date") else panel.iloc[:0]
    import screener.publishers.report as report_mod2
    monkeypatch.setattr(pl, "compute_for_date", lambda *a, **kw: _make_regime_row_for_test())
    monkeypatch.setattr(pl, "apply_regime_gate", lambda p, r: p)
    monkeypatch.setattr(pl, "validate_run", lambda *a, **kw: None)
    monkeypatch.setattr(report_mod2, "_add_publisher_columns", lambda cross, row: cross.assign(
        ticker="AAPL", rank=pd.array([1], dtype="Int64"),
        composite_score=pd.Series([50.0], index=cross.index) if len(cross) > 0 else cross.get("composite_score", pd.Series([50.0])),
    ))
    monkeypatch.setattr(pl, "build_panel", lambda *a, **kw: panel)
    monkeypatch.setattr(pl, "passes_trend_template", lambda p: panel)
    monkeypatch.setattr(q, "passes_qullamaggie_setup_a", lambda p: panel)
    monkeypatch.setattr(persistence, "read_fundamentals", lambda d: empty_fund)
    monkeypatch.setattr(c, "canslim_c_overlay", lambda p, f, d: panel)
    monkeypatch.setattr(pl, "_add_catalyst_columns", lambda p, f, d: panel)
    monkeypatch.setattr(pl, "score", lambda p, w=None: panel)
    monkeypatch.setattr(comp, "tag_playbook", lambda p: panel)
    monkeypatch.setattr(pl, "write_snapshot", lambda p, d: tmp_path / "snap.parquet")
    monkeypatch.setattr(persistence, "write_pattern_audit_atomic", _fake_write_audit)
    monkeypatch.setattr(persistence, "read_insider_cluster_buy", lambda **kw: set())

    pl.run_pipeline(snapshot_date="2026-05-16", write_report=False)

    assert "df" in captured, "pattern_audit write was never invoked"
    audit_df = captured["df"]
    assert not audit_df.empty
    assert set(audit_df["pattern_type"].unique()) == {"vcp"}
    assert audit_df["leg_idx"].tolist() == [0, 1]
    # B2 regression: dates are REAL fixture dates, not zero-filled to as_of
    assert str(audit_df["start_date"].iloc[0].date()) == "2026-04-01"
    assert audit_df["avg_volume"].iloc[0] > 0
    # PatternAuditSchema acceptance
    persistence.validate_at_write(persistence.PatternAuditSchema, audit_df)


def test_run_pipeline_lag_d13b_applied(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Assert pipeline.run_pipeline calls persistence.read_fundamentals
    with the snapshot date so the 45-day lag is applied (D-13b structural).
    """
    from screener.publishers import pipeline as pl
    from screener import persistence
    import screener.signals.qullamaggie as q
    import screener.signals.canslim as c
    import screener.signals.composite as comp

    panel = _make_synthetic_panel_with_vcp("2026-05-16")
    empty_fund = pd.DataFrame(columns=[
        "ticker", "fiscal_quarter_end", "eps_actual", "eps_yoy_growth",
        "knowable_from", "next_earnings_date", "next_earnings_hour",
        "source", "ingested_at",
    ])
    seen: list = []

    def _spy_read_fund(as_of_date: object) -> pd.DataFrame:
        seen.append(as_of_date)
        return empty_fund

    import screener.publishers.report as report_mod3
    monkeypatch.setattr(pl, "compute_for_date", lambda *a, **kw: _make_regime_row_for_test())
    monkeypatch.setattr(pl, "apply_regime_gate", lambda p, r: p)
    monkeypatch.setattr(pl, "validate_run", lambda *a, **kw: None)
    monkeypatch.setattr(report_mod3, "_add_publisher_columns", lambda cross, row: cross.assign(
        ticker="AAPL", rank=pd.array([1], dtype="Int64"),
    ))
    monkeypatch.setattr(pl, "build_panel", lambda *a, **kw: panel)
    monkeypatch.setattr(pl, "passes_trend_template", lambda p: panel)
    monkeypatch.setattr(q, "passes_qullamaggie_setup_a", lambda p: panel)
    monkeypatch.setattr(persistence, "read_fundamentals", _spy_read_fund)
    monkeypatch.setattr(c, "canslim_c_overlay", lambda p, f, d: panel)
    monkeypatch.setattr(pl, "_add_catalyst_columns", lambda p, f, d: panel)
    monkeypatch.setattr(pl, "score", lambda p, w=None: panel)
    monkeypatch.setattr(comp, "tag_playbook", lambda p: panel)
    monkeypatch.setattr(pl, "write_snapshot", lambda p, d: tmp_path / "snap.parquet")
    monkeypatch.setattr(persistence, "write_pattern_audit_atomic",
                        lambda df, d: tmp_path / f"{d}.parquet")
    monkeypatch.setattr(persistence, "read_insider_cluster_buy", lambda **kw: set())

    pl.run_pipeline(snapshot_date="2026-05-16", write_report=False)

    assert seen, "read_fundamentals was never called"
    as_of = seen[0]
    # The lag application happens because pipeline passes snapshot_date through.
    assert pd.Timestamp(as_of).date() == dt.date(2026, 5, 16)


def test_snapshot_strict_accepts_full_pipeline_panel(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """W-Plan05-1 regression: pipeline panel with pipeline-only extras
    (vcp_passes, flag_passes, post_gap_continuation, pivot_price,
    canslim_c_passes, eps_knowable_from) MUST project cleanly to
    RankingSnapshotSchema (strict=True). Without the projection step in
    run_pipeline, write_snapshot raises pandera.SchemaError on the first
    real `make rank` invocation. This test captures the projected frame
    from the in-pipeline write_snapshot call and asserts:
      (a) no SchemaError raised during run_pipeline
      (b) projected columns are exactly RankingSnapshotSchema's column set
          intersected with the input panel (no pipeline-only extras leak through)
    """
    from screener.publishers import pipeline as pl
    from screener import persistence
    from screener.persistence import RankingSnapshotSchema
    import screener.signals.qullamaggie as q
    import screener.signals.canslim as c
    import screener.signals.composite as comp

    snap_ts = pd.Timestamp("2026-05-16")
    idx = pd.MultiIndex.from_tuples([("AAPL", snap_ts)], names=["ticker", "date"])

    # Build a panel that satisfies EVERY RankingSnapshotSchema field PLUS
    # pipeline-only extras that would trigger SchemaError under strict=True.
    full_panel = pd.DataFrame(
        {
            # --- RankingSnapshotSchema columns (ALL required by strict=True schema) ---
            "rank": pd.array([1], dtype="Int64"),
            "composite_score": [75.0],
            "rs_component": [0.92],
            "trend_component": [1.0],
            "volume_component": [0.7],
            "pattern_component": [0.67],
            "earnings_component": [1.0],
            "catalyst_component": [0.67],
            "passes_trend_template": [True],
            "trend_template_score": pd.array([8], dtype="Int64"),
            "rs_rating": pd.array([92], dtype="Int64"),
            "dryup_ratio": [0.85],
            "pivot_distance_atr": [0.5],
            "pivot_zone": ["in-zone"],
            "regime_state": ["Confirmed Uptrend"],
            "regime_score": [1.0],
            # Phase 6 schema columns (also required by strict=True)
            "playbook_tag": ["qullamaggie_continuation"],
            "qullamaggie_score": pd.array([1], dtype="Int64"),
            "minervini_score": pd.array([0], dtype="Int64"),
            "leader_hold_score": pd.array([0], dtype="Int64"),
            "pattern_diagnostics": ['{"type":"vcp"}'],
            "breakout_strength": [0.73],
            "days_to_next_earnings": pd.array([pd.NA], dtype="Int64"),
            "crossed_52w_high_within_60d": [True],
            "insider_cluster_buy": [False],
            "earnings_in_3d_warn": [False],
            "eps_knowable_from": pd.array(["2026-05-30"], dtype="string"),
            # --- PIPELINE-ONLY extras (would break strict=True without projection) ---
            "vcp_passes": [True],
            "flag_passes": [False],
            "post_gap_continuation": [False],
            "pivot_price": [175.5],
            "canslim_c_passes": [True],
            "high_52w": [175.5],
            "close": [175.5],
        },
        index=idx,
    )

    empty_fund = pd.DataFrame(columns=[
        "ticker", "fiscal_quarter_end", "eps_actual", "eps_yoy_growth",
        "knowable_from", "next_earnings_date", "next_earnings_hour",
        "source", "ingested_at",
    ])
    captured: dict = {}

    def _fake_write_snapshot(df: pd.DataFrame, snapshot_date: str) -> object:
        captured["snapshot_df"] = df.copy()
        captured["snapshot_date"] = snapshot_date
        # Re-run schema validation here to assert the projection succeeded.
        persistence.validate_at_write(RankingSnapshotSchema, df)
        return tmp_path / f"{snapshot_date}.parquet"

    import screener.publishers.report as report_mod4
    cross4 = full_panel.xs(snap_ts, level="date")
    monkeypatch.setattr(pl, "compute_for_date", lambda *a, **kw: _make_regime_row_for_test())
    monkeypatch.setattr(pl, "apply_regime_gate", lambda p, r: p)
    monkeypatch.setattr(pl, "validate_run", lambda *a, **kw: None)
    # _add_publisher_columns must return the full cross-section WITH ticker as a column
    # (the real function calls reset_index()). Include all pipeline-only extras so
    # the projection step actually has something to project/exclude.
    def _fake_pub_cols(cross: pd.DataFrame, row: object) -> pd.DataFrame:
        out = cross.copy()
        if out.index.name == "ticker":
            out = out.reset_index()
        elif "ticker" not in out.columns:
            out.index.name = "ticker"
            out = out.reset_index()
        return out
    monkeypatch.setattr(report_mod4, "_add_publisher_columns", _fake_pub_cols)
    monkeypatch.setattr(pl, "build_panel", lambda *a, **kw: full_panel)
    monkeypatch.setattr(pl, "passes_trend_template", lambda p: full_panel)
    monkeypatch.setattr(q, "passes_qullamaggie_setup_a", lambda p: full_panel)
    monkeypatch.setattr(persistence, "read_fundamentals", lambda d: empty_fund)
    monkeypatch.setattr(c, "canslim_c_overlay", lambda p, f, d: full_panel)
    monkeypatch.setattr(pl, "_add_catalyst_columns", lambda p, f, d: full_panel)
    monkeypatch.setattr(pl, "score", lambda p, w=None: full_panel)
    monkeypatch.setattr(comp, "tag_playbook", lambda p: full_panel)
    monkeypatch.setattr(pl, "write_snapshot", _fake_write_snapshot)
    monkeypatch.setattr(persistence, "write_pattern_audit_atomic",
                        lambda df, d: tmp_path / f"{d}.parquet")
    monkeypatch.setattr(persistence, "read_insider_cluster_buy", lambda **kw: set())

    # Pre-condition: full panel itself would FAIL strict-mode schema validation
    # (pipeline-only columns are not in the schema). This proves the projection
    # is doing real work; without it, write_snapshot would raise SchemaError.
    with pytest.raises(Exception):  # pandera.errors.SchemaError
        persistence.validate_at_write(RankingSnapshotSchema, full_panel)

    # Act: run_pipeline must NOT raise.
    pl.run_pipeline(snapshot_date="2026-05-16", write_report=False)

    # Assert: the snapshot received by write_snapshot has ONLY schema columns
    assert "snapshot_df" in captured, "write_snapshot was never invoked"
    snap_cols = set(captured["snapshot_df"].columns)
    schema_cols = set(RankingSnapshotSchema.to_schema().columns.keys())
    # Projected columns are a subset of schema columns (only those present in panel)
    assert snap_cols.issubset(schema_cols), \
        f"Pipeline-only columns leaked to snapshot: {snap_cols - schema_cols}"
    # None of the known pipeline-only extras should appear in the snapshot
    forbidden = {"vcp_passes", "flag_passes", "post_gap_continuation",
                 "pivot_price", "canslim_c_passes",
                 "high_52w", "close"}
    assert not (snap_cols & forbidden), \
        f"Pipeline-only columns leaked to snapshot: {snap_cols & forbidden}"
