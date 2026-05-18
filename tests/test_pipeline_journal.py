"""tests/test_pipeline_journal.py — Phase 7 pipeline + journal integration (Plan 07-04 bodies)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest


def _make_synthetic_multiindex_panel(
    snapshot_date: str = "2026-05-18",
) -> pd.DataFrame:
    """Build a small MultiIndex(ticker, date) panel with all columns the
    Phase 6 pipeline reads — enough for run_pipeline to chain build_panel ->
    score -> tag_playbook -> apply_regime_gate -> compute_sizing without an
    actual OHLCV cache."""
    snap_ts = pd.Timestamp(snapshot_date)
    tickers = ["AAPL", "MSFT", "NVDA", "REJC"]
    idx = pd.MultiIndex.from_product([tickers, [snap_ts]], names=["ticker", "date"])
    return pd.DataFrame(
        {
            "close": [180.0, 380.0, 950.0, 80.0],
            "low": [178.0, 378.0, 940.0, 79.5],
            "high": [182.0, 382.0, 960.0, 80.5],
            "atr_14": [3.5, 5.0, 22.0, 0.5],
            "adr_pct": [4.2, 3.8, 5.5, 0.3],   # REJC adr_pct=0.3 -> reject
            "rs_rating": pd.array([92, 88, 95, 82], dtype=pd.Int64Dtype()),
            "trend_template_score": pd.array([8, 7, 8, 6], dtype=pd.Int64Dtype()),
            "volume_component": [0.7, 0.6, 0.8, 0.3],
            "pattern_component": [0.7, 0.5, 0.85, 0.3],
            "earnings_component": [0.6, 0.4, 0.7, 0.2],
            "catalyst_component": [0.5, 0.3, 0.6, 0.2],
            "composite_score": [85.0, 70.0, 88.0, 55.0],
            "passes_trend_template": [True, True, True, True],
            "high_52w": [185.0, 385.0, 970.0, 82.0],
            "low_52w": [140.0, 320.0, 700.0, 65.0],
            "sma_50": [175.0, 370.0, 920.0, 78.0],
            "sma_150": [170.0, 365.0, 880.0, 76.0],
            "sma_200": [165.0, 360.0, 850.0, 74.0],
            "dryup_ratio": [0.85, 0.75, 0.90, 0.60],
            "playbook_tag": [
                "minervini_vcp",
                "qullamaggie_continuation",
                "minervini_vcp",
                "qullamaggie_continuation",
            ],
            "qullamaggie_score": pd.array([0, 1, 0, 1], dtype=pd.Int64Dtype()),
            "minervini_score": pd.array([1, 0, 1, 0], dtype=pd.Int64Dtype()),
            "leader_hold_score": pd.array([0, 0, 0, 0], dtype=pd.Int64Dtype()),
            "pattern_diagnostics": [
                '{"type":"vcp","pivot_price":175.5,"final_contraction_depth":0.08,'
                '"depth_sequence":[0.25,0.15,0.08],"n_contractions":3,'
                '"first_leg_depth":0.25,"breakout_vol_multiple":1.7,'
                '"breakout_strength":0.85,"days_in_consolidation":18}',
                '{"type":"flag","pivot_price":378.0,"final_contraction_depth":0.0,'
                '"depth_sequence":[],"n_contractions":0,"first_leg_depth":0.0,'
                '"breakout_vol_multiple":1.6,"breakout_strength":0.72,'
                '"days_in_consolidation":12}',
                '{"type":"vcp","pivot_price":940.0,"final_contraction_depth":0.10,'
                '"depth_sequence":[0.30,0.18,0.10],"n_contractions":3,'
                '"first_leg_depth":0.30,"breakout_vol_multiple":1.8,'
                '"breakout_strength":0.92,"days_in_consolidation":22}',
                '{"type":"flag","pivot_price":79.0,"final_contraction_depth":0.0,'
                '"depth_sequence":[],"n_contractions":0,"first_leg_depth":0.0,'
                '"breakout_vol_multiple":1.5,"breakout_strength":0.65,'
                '"days_in_consolidation":10}',
            ],
            "breakout_strength": [0.85, 0.72, 0.92, 0.65],
            "days_to_next_earnings": pd.array([pd.NA] * 4, dtype=pd.Int64Dtype()),
            "crossed_52w_high_within_60d": [False, False, True, False],
            "insider_cluster_buy": [False, False, False, False],
            "earnings_in_3d_warn": [False, False, False, False],
            "eps_knowable_from": pd.array([None] * 4, dtype=object),
            # Intermediate score-component columns that composite.score() normally
            # produces and that RankingSnapshotSchema.rs_component /
            # trend_component require. Since we mock score() as identity, we must
            # provide them in the raw panel.
            "rs_component": [0.9, 0.85, 0.95, 0.80],
            "trend_component": [1.0, 0.875, 1.0, 0.75],
        },
        index=idx,
    )


def _install_pipeline_mocks(monkeypatch: pytest.MonkeyPatch, panel: pd.DataFrame) -> None:
    """Patch out every external dependency of run_pipeline so it walks the DAG
    using the synthetic panel only.

    Revision iteration 1 Blocker #4 fix: NO try/except AttributeError around
    these monkeypatches. Phase 7 already depends on Phase 6 — if any of these
    symbols are missing, the test MUST fail loud so the breakage is visible
    immediately.

    Revision iteration 1 Blocker #4 fix: DO NOT monkeypatch write_snapshot.
    We want pandera to validate the real FULL frame at the write boundary so
    any future Phase-7 schema break surfaces here.

    Note on import targets: some Phase 6 functions are imported inside
    run_pipeline (not at module level) — e.g. passes_qullamaggie_setup_a,
    canslim_c_overlay, tag_playbook, compute_sizing. For those we patch the
    source module so the local import inside run_pipeline picks up the stub.
    Functions imported at module level (build_panel, passes_trend_template,
    score, compute_for_date, validate_run) are patched on the pipeline module.
    _add_catalyst_columns is defined in pipeline.py itself, so it is patched
    there.
    """
    # Module-level imports in pipeline.py — patch the pipeline module attr.
    monkeypatch.setattr("screener.publishers.pipeline.build_panel", lambda d: panel)
    monkeypatch.setattr("screener.publishers.pipeline.passes_trend_template", lambda p: p)
    monkeypatch.setattr("screener.publishers.pipeline.score", lambda p, w: p)
    monkeypatch.setattr("screener.publishers.pipeline.compute_for_date",
        lambda ts, p: pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82}),
    )
    monkeypatch.setattr("screener.publishers.pipeline.validate_run", lambda *a, **kw: None)
    # _add_catalyst_columns is defined locally in pipeline.py.
    monkeypatch.setattr(
        "screener.publishers.pipeline._add_catalyst_columns", lambda p, f, ts: p
    )

    # Inline-imported inside run_pipeline — patch the source module so the
    # local `from X import Y` inside the function gets the stub.
    monkeypatch.setattr(
        "screener.signals.qullamaggie.passes_qullamaggie_setup_a", lambda p: p
    )
    monkeypatch.setattr("screener.signals.canslim.canslim_c_overlay", lambda p, f, ts: p)
    monkeypatch.setattr("screener.signals.composite.tag_playbook", lambda p: p)
    # compute_sizing is also inline-imported; patch the sizing module.
    import screener.sizing as _sizing
    monkeypatch.setattr(_sizing, "compute_sizing", lambda cross, panel, **kw: _stub_sizing(cross))

    # persistence functions.
    monkeypatch.setattr("screener.persistence.read_fundamentals", lambda ts: pd.DataFrame())
    # Pattern audit writer: if it exists, stub it; otherwise, the pipeline's
    # try/except around step 10 silently catches AttributeError — safe to skip.
    import screener.persistence as _pers
    if hasattr(_pers, "write_pattern_audit_atomic"):
        monkeypatch.setattr(_pers, "write_pattern_audit_atomic", lambda df, d: None)
    # NOTE: write_snapshot is INTENTIONALLY NOT mocked. SNAPSHOT_DIR is pointed
    # at tmp_path by _setup_settings so the write is safe; we want pandera to
    # validate the real FULL frame (Blocker #4 fix + Warning #10 lock).


def _stub_sizing(cross: pd.DataFrame) -> pd.DataFrame:
    """Minimal sizing stub: adds the 9 sizing columns compute_sizing normally
    produces.

    Rejection logic: REJC has adr_pct=0.3 which is well below the 1xADR
    threshold (ADR dollars = 0.3/100 * 80 = $0.24; any risk > $0.24 would
    exceed 1xADR). We use ticker == 'REJC' as the rejection sentinel so the
    test's exact counts (3 actionable, 1 rejected) are deterministic regardless
    of the adr_pct threshold arithmetic in the real compute_sizing.
    """
    out = cross.copy()
    rejected = pd.Series(out.index == "REJC", index=out.index)
    out["adr_rejected"] = rejected
    out["rejection_reason"] = rejected.map({True: "adr_exceeded", False: ""})
    # Minimal sizing values (all rows get numeric defaults; rejected rows are
    # later excluded from the journal/report by the actionable_view filter
    # but remain in the snapshot — Blocker #1 requirement).
    out["entry_price"] = out["close"]
    out["stop_price"] = out["close"] * 0.95
    out["risk_per_share"] = out["close"] * 0.05
    out["shares"] = pd.array([10] * len(out), dtype=pd.Int64Dtype())
    # atr_zone: real value for non-rejected actionable rows; pd.NA for others
    # (the sentinel patch in run_pipeline will convert NaN to "not_applicable").
    out["atr_zone"] = pd.NA
    valid_playbook = out.get("playbook_tag", pd.Series("none", index=out.index)).isin(
        ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
    )
    out.loc[~rejected & valid_playbook, "atr_zone"] = "in-zone"
    out["pivot_distance_atr_breakout"] = out["close"].apply(
        lambda c: round((c - c * 0.95) / 2.0, 2) if pd.notna(c) else None
    )
    out["trail_rule_label"] = "21d EMA (then 50d SMA after 15 bars)"
    return out


def _setup_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point JOURNAL_DB_PATH + SNAPSHOT_DIR at tmp_path; clear Settings cache."""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JOURNAL_DB_PATH", str(tmp_path / "journal.sqlite"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap_dir))
    monkeypatch.setenv("JOURNAL_THRESHOLD", "50.0")
    monkeypatch.setenv("RISK_PCT", "0.01")
    monkeypatch.setenv("ACCOUNT_EQUITY", "100000")
    from screener.config import get_settings
    get_settings.cache_clear()


def test_pipeline_writes_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OUT-04: run_pipeline(..., write_journal=True) appends rows to data/journal.sqlite."""
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    db = tmp_path / "journal.sqlite"
    assert db.exists()
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT ticker, composite_score FROM picks").fetchall()
    tickers = sorted(r[0] for r in rows)
    # AAPL (85), MSFT (70), NVDA (88) all >= 50; REJC (55) >= 50 but adr-rejected.
    assert "AAPL" in tickers and "NVDA" in tickers, tickers
    assert "REJC" not in tickers, "REJC should be ADR-rejected, not in journal"


def test_journal_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-01: run_pipeline(..., write_journal=False) writes ZERO journal rows."""
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=False)

    db = tmp_path / "journal.sqlite"
    # The contract is: zero rows in the picks table, NOT no file. (The file
    # may or may not exist depending on whether _ensure_picks_schema ran.)
    if db.exists():
        with sqlite3.connect(db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        assert count == 0, f"write_journal=False should not append; got {count} rows"


def test_rejected_picks_not_in_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SIZ-02 / D-06: ADR-rejected picks excluded from journal BUT present in snapshot.

    Revision iteration 1 Blocker #1 regression check: the snapshot retains the
    FULL universe (including rejected picks); only the journal/report top-N
    filters them out.
    """
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    # Journal: REJC must NOT appear.
    db = tmp_path / "journal.sqlite"
    with sqlite3.connect(db) as conn:
        journal_tickers = [r[0] for r in conn.execute("SELECT ticker FROM picks").fetchall()]
    assert "REJC" not in journal_tickers
    assert len(journal_tickers) >= 1

    # Snapshot: REJC MUST appear (full universe preserved — Blocker #1).
    snap_path = tmp_path / "snapshots" / "2026-05-18.parquet"
    assert snap_path.exists(), f"snapshot not written: {snap_path}"
    snap_df = pd.read_parquet(snap_path)
    snap_tickers = set(snap_df["ticker"]) if "ticker" in snap_df.columns else set(snap_df.index)
    assert "REJC" in snap_tickers, (
        f"Blocker #1 regression: REJC missing from snapshot (snap has: {snap_tickers})"
    )


def test_golden_pipeline_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-1 + Warning #10: full integration round-trip — deterministic row count +
    features_json structure + snapshot-row-count regression assertion.

    The snapshot row count MUST equal the input universe row count (4 here).
    This locks revision iteration 1 Blocker #1 in place: any future regression
    that filters today_panel by adr_rejected before write_snapshot will fail
    here loudly.
    """
    _setup_settings(tmp_path, monkeypatch)
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline
    run_pipeline("2026-05-18", write_report=False, write_journal=True)

    # 1. Snapshot row-count regression (Warning #10 / Blocker #1 lock).
    snap_path = tmp_path / "snapshots" / "2026-05-18.parquet"
    snap_df = pd.read_parquet(snap_path)
    universe_size = len(_make_synthetic_multiindex_panel())  # 4 tickers
    assert len(snap_df) == universe_size, (
        f"Blocker #1 regression: snapshot has {len(snap_df)} rows; "
        f"expected {universe_size} (full universe). "
        f"Did today_panel get filtered by adr_rejected before write_snapshot?"
    )

    # 2. Journal row-count + features_json structure.
    db = tmp_path / "journal.sqlite"
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT ticker, features_json FROM picks ORDER BY ticker"
        ).fetchall()
    # Exact count: 3 actionable tickers (AAPL, MSFT, NVDA — composite >= 50, not rejected).
    assert len(rows) == 3, [r[0] for r in rows]
    # features_json structure check on the first row.
    feat = json.loads(rows[0][1])
    required_top_keys = {
        "features_json_version", "rs_rating", "trend_template_score",
        "composite_score", "composite_score_raw", "regime_score", "regime_state",
        "playbook_tag", "atr_14", "adr_pct", "entry_price", "stop_price",
        "shares", "risk_per_share", "atr_zone", "pattern_diagnostics",
        "account_equity_used", "risk_pct_used", "entry_price_semantics",
        "pivot_distance_atr_breakout",  # Warning #5 -- renamed column present
    }
    missing = required_top_keys - set(feat.keys())
    assert not missing, f"features_json missing keys: {missing}"
    assert feat["features_json_version"] == "v1.0"
    # pattern_diagnostics is inlined as a dict (not a string).
    assert isinstance(feat["pattern_diagnostics"], dict)
    assert "type" in feat["pattern_diagnostics"]
