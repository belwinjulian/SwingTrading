"""publishers.pipeline — orchestrator for the daily report run.

Composes the Phase 4/6 DAG (D-03 + D-07 + D-08 + Phase 6 extensions):
    build_panel -> passes_trend_template
        -> passes_qullamaggie_setup_a (Phase 6)
        -> read_fundamentals (Phase 6, D-13b lag applied at read)
        -> canslim_c_overlay (Phase 6)
        -> _add_catalyst_columns (Phase 6)
        -> composite.score
        -> tag_playbook (Phase 6)
        -> apply_regime_gate (soft, D-03)
        -> validate_run (D-07 warn / D-08 hard fail)
        -> [project today_panel to RankingSnapshotSchema columns — W-Plan05-1]
        -> write_snapshot (receives projected frame)
        -> write_report (receives full today_panel — for D-19 per-pick detail)
        -> write_pattern_audit_atomic (Phase 6, D-05)

apply_regime_gate is intentionally a SEPARATE function (not embedded in
composite.score) so Phase 7's potential hard-gate transition (zero composite
in Correction) is a swap, not a destructive edit to a strict-mypy-locked
pure function. See RESEARCH.md §4.

validate_run mirrors the cli.refresh_ohlcv health-gate pattern (lines 130-144)
— typer.Exit(1) BEFORE writing any artifact, so a failed run leaves no
partial report and no partial snapshot on disk (Pitfall 7).

Architecture (D-16): publishers/ may import {signals, sizing, regime,
persistence, config, obs}. No data/, no network.
"""

from __future__ import annotations

import pandas as pd
import structlog
import typer

from screener.config import get_settings
from screener.publishers.snapshot import write_snapshot
from screener.regime import compute_for_date
from screener.signals import build_panel
from screener.signals.composite import DEFAULT_WEIGHTS, score
from screener.signals.minervini import passes_trend_template

log = structlog.get_logger(__name__)


# --- D-03 soft regime gate (separate-function design per RESEARCH §4) -----


def apply_regime_gate(scored_panel: pd.DataFrame, regime_score: float) -> pd.DataFrame:
    """Soft gate: composite_score *= regime_score (D-03).

    Picks remain visible during Correction; scores compress because
    regime_score is low. Phase 7 may swap to a hard gate (zero composite
    when state == 'Correction') — keeping this as a separate function makes
    that swap a single import-replacement.

    Pitfall 6 defensive: regime_score is asserted in [0, 1]. Phase 3 D-03
    formula naturally produces [0, 1] but a future bug could allow > 1.0
    and bloat composite_score past 100.
    """
    assert 0.0 <= regime_score <= 1.0, (
        f"regime_score out of range: {regime_score} (expected [0, 1])"
    )
    out = scored_panel.copy()
    out["composite_score"] = out["composite_score"] * regime_score
    return out


# --- D-07 / D-08 dual-channel data-quality gate ---------------------------


def validate_run(
    pass_rate: float,
    regime_state: str,
    warn_threshold: float,
    fail_threshold_with_correction: float,
) -> None:
    """Emit D-07 warning + raise D-08 typer.Exit(1) on the data-quality combo.

    D-07: pass_rate > warn_threshold (default 0.15, top of the documented
          healthy 5-15% range) -> structlog warning, no exit. The publisher
          report.py renders a banner in the data-quality footer.

    D-08: pass_rate > fail_threshold_with_correction (default 0.25) AND
          regime_state == 'Correction' -> typer.Exit(code=1). Caller (the
          CLI body in Plan 04-05) MUST allow typer.Exit to propagate so
          the process exit code reflects the failure (Pitfall 7).

    Per REVIEW IN-01 / WR-01 the two defaults are now distinct so the
    warn fires earlier than the Correction-only hard fail.

    Mirrors the refresh_ohlcv health-gate pattern (cli.py:130-144).
    """
    if pass_rate > warn_threshold:
        log.warning(
            "trend_template_pass_rate_high",
            pass_rate=pass_rate,
            expected_range="0.05-0.15",
            warn_threshold=warn_threshold,
        )
    # Independent check — does NOT require pass_rate > warn_threshold first.
    # Flattened from a previously-nested if (see REVIEW CR-01): the two
    # thresholds are independent control surfaces so an operator can set
    # warn_threshold lower than fail_threshold_with_correction without the
    # hard-fail being suppressed by the outer warn gate.
    if (
        regime_state == "Correction"
        and pass_rate > fail_threshold_with_correction
    ):
        log.error(
            "data_quality_gate_failed",
            pass_rate=pass_rate,
            regime_state=regime_state,
            message=(
                f"Pass rate {pass_rate * 100:.1f}% in Correction regime — "
                f"data quality gate failed"
            ),
        )
        raise typer.Exit(code=1)


# --- Phase 6 private helpers (placed before run_pipeline per D-23) --------


def _add_catalyst_columns(panel: pd.DataFrame, fundamentals: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Add catalyst input columns the composite/snapshot/report all consume.

    New columns added:
      - days_to_next_earnings (Int64, nullable)
      - earnings_in_3d_warn (bool; True when 0 <= days_to_next_earnings <= 3)
      - eps_knowable_from (str ISO date; W11 report hint for EPS-pending picks)
      - crossed_52w_high_within_60d (bool; rolling-60 lookback on high_52w column)
      - insider_cluster_buy (bool; per-ticker cluster detection via persistence)

    Called BEFORE score() so catalyst_component has the flags it needs.
    No network I/O — insider data was already fetched by data/insider.py.
    """
    out = panel.copy()
    # 1. Earnings proximity from fundamentals (lag-filtered by caller)
    latest_by_ticker: pd.DataFrame = pd.DataFrame()
    if not fundamentals.empty and "ticker" in fundamentals.columns:
        latest_by_ticker = (
            fundamentals.sort_values("fiscal_quarter_end")
            .groupby("ticker")
            .tail(1)
            .set_index("ticker")
        )
    next_earn_by_ticker: pd.Series = (
        latest_by_ticker["next_earnings_date"]
        if "next_earnings_date" in latest_by_ticker.columns
        else pd.Series(dtype="datetime64[ns]")
    )
    knowable_by_ticker: pd.Series = (
        latest_by_ticker["knowable_from"]
        if "knowable_from" in latest_by_ticker.columns
        else pd.Series(dtype="datetime64[ns]")
    )
    tickers = out.index.get_level_values("ticker")

    def _days_to(t: str) -> object:
        if t in next_earn_by_ticker.index and pd.notna(next_earn_by_ticker.get(t)):
            delta = (pd.Timestamp(next_earn_by_ticker.get(t)) - as_of).days
            return delta
        return pd.NA

    days_to = [_days_to(t) for t in tickers]
    out["days_to_next_earnings"] = pd.array(days_to, dtype="Int64")
    out["earnings_in_3d_warn"] = (
        (out["days_to_next_earnings"].fillna(999) <= 3)
        & (out["days_to_next_earnings"].fillna(-1) >= 0)
    )

    # 1b. eps_knowable_from — ISO date string per ticker (W11)
    def _knowable(t: str) -> str:
        if t in knowable_by_ticker.index and pd.notna(knowable_by_ticker.get(t)):
            return pd.Timestamp(knowable_by_ticker.get(t)).date().isoformat()
        return ""

    out["eps_knowable_from"] = pd.array([_knowable(t) for t in tickers], dtype="string")

    # 2. crossed_52w_high_within_60d: True if close hit >= high_52w within last 60 bars
    # high_52w is already in panel (Phase 4 04-01)
    if "high_52w" in out.columns and "close" in out.columns:
        near_52w = (out["close"] >= out["high_52w"] * 0.999).fillna(False)
        crossed = (
            near_52w.groupby(level="ticker")
            .rolling(60, min_periods=1)
            .max()
            .droplevel(0)
            .astype(bool)
        )
        out["crossed_52w_high_within_60d"] = crossed.reindex(out.index).fillna(False)
    elif "crossed_52w_high_within_60d" not in out.columns:
        out["crossed_52w_high_within_60d"] = False

    # 3. insider_cluster_buy from persistence (SQL or Python rolling fallback)
    from screener import persistence
    cluster_tickers = persistence.read_insider_cluster_buy(window_days=30, cluster_size=2, dt=5)
    out["insider_cluster_buy"] = pd.array(
        [t in cluster_tickers for t in tickers], dtype=bool
    )
    return out


def _build_pattern_audit_df(panel: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Construct per-leg pattern audit DataFrame for the current cross-section.

    Per D-05: VCP picks emit per-leg rows from diag["legs"]; flag picks emit a
    single row with leg_idx=0. Conforms to PatternAuditSchema (Plan 01).

    Checker B2: VCP rows now read diag["legs"] (added in Plan 02 Task 2) — each
    leg carries real (start_date, end_date, high, low, depth, avg_volume). Older
    zero-filled placeholder version is removed.
    """
    rows: list[dict] = []
    cross = (
        panel.xs(as_of, level="date")
        if as_of in panel.index.get_level_values("date")
        else pd.DataFrame()
    )
    if cross.empty or "pattern_diagnostics" not in cross.columns:
        return pd.DataFrame(
            columns=["ticker", "snapshot_date", "pattern_type", "leg_idx",
                     "start_date", "end_date", "high", "low", "depth", "avg_volume"]
        )
    import json as _json
    as_of_ts = pd.Timestamp(as_of)

    def _decode_diag(s: str) -> dict:
        """JSON-decode the diagnostics string. Malformed -> {'type': 'none'} (Pitfall 8)."""
        try:
            d = _json.loads(s)
            if not isinstance(d, dict) or d.get("type") not in ("vcp", "flag", "none"):
                return {"type": "none"}
            return d
        except (_json.JSONDecodeError, TypeError):
            return {"type": "none"}

    for ticker, row in cross.iterrows():
        diag = _decode_diag(row["pattern_diagnostics"])
        if diag["type"] == "vcp":
            legs = diag.get("legs") or []
            if not legs:
                log.warning("pattern_audit_vcp_missing_legs", ticker=ticker, snapshot_date=str(as_of))
                continue
            for leg in legs:
                rows.append({
                    "ticker": str(ticker),
                    "snapshot_date": as_of_ts,
                    "pattern_type": "vcp",
                    "leg_idx": int(leg["leg_idx"]),
                    "start_date": pd.Timestamp(leg["start_date"]),
                    "end_date": pd.Timestamp(leg["end_date"]),
                    "high": float(leg["high"]),
                    "low": float(leg["low"]),
                    "depth": float(leg["depth"]),
                    "avg_volume": float(leg["avg_volume"]),
                })
        elif diag["type"] == "flag":
            pivot = float(diag.get("pivot_price", 0.0))
            range_tightness = float(diag.get("range_tightness", 0.0))
            rows.append({
                "ticker": str(ticker),
                "snapshot_date": as_of_ts,
                "pattern_type": "flag",
                "leg_idx": 0,
                "start_date": as_of_ts,
                "end_date": as_of_ts,
                "high": pivot,
                "low": pivot * (1.0 - range_tightness) if range_tightness > 0 else pivot * 0.95,
                "depth": range_tightness if range_tightness > 0 else 0.05,
                "avg_volume": 0.0,
            })
    if not rows:
        return pd.DataFrame(
            columns=["ticker", "snapshot_date", "pattern_type", "leg_idx",
                     "start_date", "end_date", "high", "low", "depth", "avg_volume"]
        )
    return pd.DataFrame(rows)


# --- run_pipeline orchestrator --------------------------------------------


def run_pipeline(snapshot_date: str, write_report: bool = True) -> None:
    """Compose the full daily pipeline.

    Args:
        snapshot_date: ISO YYYY-MM-DD string (e.g., '2026-05-10').
        write_report: if True, render Markdown to reports/<date>.md.
                      If False (`screener score` path), only the Parquet
                      snapshot is written.

    Raises:
        typer.Exit: from validate_run on D-08 data-quality combination.
    """
    settings = get_settings()
    snap_ts = pd.Timestamp(snapshot_date)

    # 1. Build the indicator panel for the snapshot date.
    panel = build_panel(snapshot_date)

    # 2. Compute Trend Template gate + score columns.
    panel = passes_trend_template(panel)

    # 2a. Phase 6: Qullamaggie Setup A scan (SIG-02).
    from screener.signals.qullamaggie import passes_qullamaggie_setup_a

    panel = passes_qullamaggie_setup_a(panel)

    # 2b. Phase 6: Read fundamentals with 45-day lag applied at read (D-13b).
    # signals/canslim.py receives the pre-filtered view and structurally cannot
    # violate the lag (architecture test D-23).
    from screener import persistence

    fundamentals = persistence.read_fundamentals(snap_ts)

    # 2c. Phase 6: CANSLIM C overlay (SIG-03 / D-18).
    from screener.signals.canslim import canslim_c_overlay

    panel = canslim_c_overlay(panel, fundamentals, snap_ts)

    # 2d. Phase 6: Catalyst input columns (days_to_next_earnings,
    # earnings_in_3d_warn, eps_knowable_from, crossed_52w_high_within_60d,
    # insider_cluster_buy). Must run BEFORE score() so catalyst_component
    # has the flags it needs.
    panel = _add_catalyst_columns(panel, fundamentals, snap_ts)

    # 3. Compute composite scores via weights-dict (D-13).
    panel = score(panel, DEFAULT_WEIGHTS)

    # 3a. Phase 6: Playbook tagger (CMP-02..04 / D-14 / D-15).
    from screener.signals.composite import tag_playbook

    panel = tag_playbook(panel)

    # 4. Cross-section the panel to the snapshot date (one row per ticker).
    today_panel = panel.xs(snap_ts, level="date")

    # 5. Apply soft regime gate (D-03).
    regime_row = compute_for_date(snap_ts, panel)
    regime_score_value = float(regime_row["regime_score"])
    regime_state_value = str(regime_row["regime_state"])
    today_panel = apply_regime_gate(today_panel, regime_score_value)

    # 6. Compute pass rate and run the data-quality gate (D-07/D-08).
    pass_rate = float(today_panel["passes_trend_template"].mean())
    validate_run(
        pass_rate,
        regime_state_value,
        settings.TREND_TEMPLATE_PASS_RATE_WARN,
        settings.TREND_TEMPLATE_PASS_RATE_HARD_FAIL,
    )

    # 7. Add publisher-derived columns (pivot zone) and rank.
    # REVIEW WR-03 sequencing note: this step MUST run AFTER step 5
    # (apply_regime_gate) because _add_publisher_columns ranks rows by
    # `composite_score`, which the regime gate has already multiplied by
    # regime_score. Reordering so ranking precedes the regime gate would
    # silently produce a pre-regime ranking — a hard-to-spot logic bug.
    from screener.publishers.report import _add_publisher_columns

    today_panel = _add_publisher_columns(today_panel, regime_row)

    # 7a. W-Plan05-1: Project today_panel to RankingSnapshotSchema columns
    # BEFORE write_snapshot. RankingSnapshotSchema has strict=True; pipeline-only
    # columns (vcp_passes, flag_passes, post_gap_continuation, pivot_price,
    # canslim_c_passes, eps_knowable_from, pattern_diagnostics, etc.) live on
    # today_panel for audit + report consumption but are NOT persisted to snapshot.
    # Without this projection the first real `make rank` invocation hard-fails with
    # SchemaError (CLAUDE.md "No shape surprises"). T-06-29 mitigation.
    from screener.persistence import RankingSnapshotSchema

    schema_cols = list(RankingSnapshotSchema.to_schema().columns.keys())
    snapshot_df = today_panel[[c for c in schema_cols if c in today_panel.columns]]

    # 8. Write the Parquet snapshot (always — used by Phase 5 backtest).
    # snapshot_df carries ONLY schema columns; today_panel retains the full set.
    write_snapshot(snapshot_df, snapshot_date)

    # 9. Optionally render + write the Markdown report.
    # IMPORTANT: write_report_md receives the FULL today_panel (with
    # pattern_diagnostics, vcp_passes, eps_knowable_from, etc.) because the
    # report renderer reads these for the D-19 per-pick block. Only the snapshot
    # write boundary requires projection (D-23 panel->snapshot architecture lock).
    if write_report:
        from screener.publishers.report import write_report as write_report_md

        write_report_md(
            today_panel,
            regime_row,
            snapshot_date,
            top_n=settings.REPORT_TOP_N,
            pass_rate=pass_rate,
        )

    # 10. Phase 6: Write per-leg pattern audit (D-05).
    # Only writes when VCP/flag picks are present; no-op when cross-section
    # has no patterned picks. Failures are non-fatal (audit is informational).
    try:
        pattern_audit_df = _build_pattern_audit_df(panel, snap_ts)
        if not pattern_audit_df.empty:
            persistence.write_pattern_audit_atomic(pattern_audit_df, snapshot_date)
    except Exception as e:
        log.warning("pattern_audit_write_failed", error_type=type(e).__name__)

    log.info(
        "pipeline_complete",
        snapshot_date=snapshot_date,
        n_tickers=len(today_panel),
        pass_rate=pass_rate,
        regime_state=regime_state_value,
        regime_score=regime_score_value,
        wrote_report=write_report,
    )
