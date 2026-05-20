"""publishers.pipeline — orchestrator for the daily report run.

Composes the Phase 4/6/7 DAG (D-03 + D-07 + D-08 + Phase 6/7 extensions):
    build_panel -> passes_trend_template
        -> passes_qullamaggie_setup_a (Phase 6)
        -> read_fundamentals (Phase 6, D-13b lag applied at read)
        -> canslim_c_overlay (Phase 6)
        -> _add_catalyst_columns (Phase 6)
        -> composite.score
        -> tag_playbook (Phase 6)
        -> [capture composite_score_raw BEFORE apply_regime_gate — Phase 7]
        -> apply_regime_gate (soft, D-03)
        -> compute_sizing on FULL cross-section (Phase 7 step 5.5 — Blocker #1)
        -> validate_run (D-07 warn / D-08 hard fail on FULL post-sizing frame)
        -> [project today_panel to RankingSnapshotSchema columns — W-Plan05-1]
        -> write_snapshot (FULL frame — preserves OUT-03 / Phase 5 backtest contract)
        -> journal append (Phase 7 step 8.5 — D-01)
        -> write_report (receives full today_panel)
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

from pathlib import Path
from typing import Any

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


def _add_catalyst_columns(
    panel: pd.DataFrame, fundamentals: pd.DataFrame, as_of: pd.Timestamp
) -> pd.DataFrame:
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
    ).astype(bool)

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
                log.warning(
                    "pattern_audit_vcp_missing_legs",
                    ticker=ticker,
                    snapshot_date=str(as_of),
                )
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


def run_pipeline(
    snapshot_date: str,
    write_report: bool = True,
    write_journal: bool = True,
) -> None:
    """Compose the full daily pipeline.

    Args:
        snapshot_date: ISO YYYY-MM-DD string (e.g., '2026-05-10').
        write_report: if True, render Markdown to reports/<date>.md.
                      If False (`screener score` path), only the Parquet
                      snapshot is written.
        write_journal: if True (default), append actionable picks to
                       data/journal.sqlite after snapshot write (CONTEXT D-01).
                       Pass False to skip journal append (e.g., backfill runs
                       where the journal is already populated).

    Phase 7 integration note (revision iteration 1 — Blocker #1):
        compute_sizing runs on the FULL cross-section. The snapshot writer
        receives the FULL ~1000-row frame — preserving OUT-03 (full ranked
        universe in snapshot) and the Phase 5 backtest reader contract.
        The actionable-pick filter is a DERIVED VIEW built AFTER snapshot
        write, used ONLY by the report renderer + journal-append helper.
        NEVER assigned back to today_panel.

    Raises:
        typer.Exit: from validate_run on D-08 data-quality combination.
    """
    settings = get_settings()

    # === Phase 8 (OPS-05): capture timing for the run-log record ===
    # Inline import matches the existing Phase 6/7 idiom (lines 336, 343,
    # 348, 362, 395, 443, 454, 484). The success-record append happens at
    # the very end of this function, AFTER log.info("pipeline_complete").
    # The failure path is owned by refresh.yml's `if: failure()` step which
    # runs `python -m screener.publishers.run_log failure` — D-05 / D-06.
    import time as _time
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from screener.publishers.run_log import append_record

    _t_start = _time.perf_counter()
    _start_iso = _datetime.now(_UTC).isoformat(timespec="seconds")
    # === END Phase 8 step 0 (timing capture) ===

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

    # Phase 7 D-01 / Pitfall 3 / Warning #6 (revision iter 1): capture the
    # PRE-gate raw composite_score so the journal threshold doesn't shift with
    # the regime (D-03 soft-gate would otherwise systematically under-sample
    # mid-quality picks during pressure regimes). composite_score_raw is also
    # added to RankingSnapshotSchema (Plan 07-01 revised) and feeds BOTH the
    # live actionable-view derivation AND the catch-up helper in cli.journal -
    # single source of truth, no per-flow divergence (Warning #6).
    today_panel = today_panel.assign(composite_score_raw=today_panel["composite_score"])

    # 5. Apply soft regime gate (D-03).
    regime_row = compute_for_date(snap_ts, panel)
    regime_score_value = float(regime_row["regime_score"])
    regime_state_value = str(regime_row["regime_state"])
    today_panel = apply_regime_gate(today_panel, regime_score_value)

    # === Phase 7 step 5.5: SIZ-01..05 dispatch (CONTEXT D-04) ===
    # === REVISION ITERATION 1 BLOCKER #1: FULL-FRAME SIZING ===
    # compute_sizing runs on the FULL cross-section. Rows with playbook_tag NOT
    # in STOP_HELPERS (~95% of universe per signals/composite.py:261 default
    # branch) gracefully land with adr_rejected=True / rejection_reason=
    # 'invalid_stop' / NaN-able sizing columns. The snapshot writer (step 8
    # below) receives this FULL frame - preserving OUT-03 (full ranked universe
    # in snapshot) and the Phase 5 backtest reader contract.
    # The actionable-pick filter is a DERIVED VIEW (built AFTER snapshot write)
    # used ONLY by the report renderer + journal-append helper. NEVER assigned
    # back to today_panel.
    from screener.sizing import compute_sizing

    today_panel = compute_sizing(
        today_panel,
        panel,
        account_equity=settings.ACCOUNT_EQUITY,
        risk_pct=settings.RISK_PCT,
        regime_score=regime_score_value,
    )

    # Sentinel patch for atr_zone (Blocker #2 followup): the snapshot schema
    # accepts "not_applicable" for rows where playbook_tag='none' or no breakout
    # pivot exists. compute_sizing emits real zone labels for actionable rows;
    # for non-actionable rows we replace with the sentinel so the isin enum on
    # RankingSnapshotSchema.atr_zone validates at write time.
    _valid_playbook_tags = ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
    _is_actionable_tag = today_panel["playbook_tag"].isin(_valid_playbook_tags)
    today_panel["atr_zone"] = today_panel["atr_zone"].where(
        _is_actionable_tag & ~today_panel["adr_rejected"], "not_applicable"
    )

    log.info(
        "sizing_pipeline_full_frame",
        snapshot_date=snapshot_date,
        n_universe=len(today_panel),
        n_rejected=int(today_panel["adr_rejected"].sum()),
        n_actionable_tag=int(_is_actionable_tag.sum()),
    )
    # === END Phase 7 step 5.5 ===

    # 6. Compute pass rate and run the data-quality gate (D-07/D-08).
    # REVISION ITERATION 1 BLOCKER #3: validate_run + pass_rate run on the FULL
    # post-sizing frame. Sizing adds columns but does NOT remove rows, so the
    # pass-rate calculation is identical to Phase 4/6 semantics (full universe).
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
    # columns live on today_panel for audit + report consumption but are NOT all
    # persisted to snapshot. Plan 07-01 (revised) extended RankingSnapshotSchema
    # with 10 new nullable columns (7 sizing + composite_score_raw + adr_rejected
    # + rejection_reason), so the projection automatically picks them up.
    # The FULL frame (~1000 rows) is projected and written - Blocker #1 fix.
    from screener.persistence import RankingSnapshotSchema

    schema_cols = list(RankingSnapshotSchema.to_schema().columns.keys())
    snapshot_df = today_panel[[c for c in schema_cols if c in today_panel.columns]]

    # 8. Write the Parquet snapshot (always — used by Phase 5 backtest).
    # snapshot_df carries the FULL universe (all ~1000 rows including rejected
    # picks) so Phase 5 backtest reader and cli.journal catch-up can both read
    # composite_score_raw + adr_rejected from the snapshot.
    write_snapshot(snapshot_df, snapshot_date)

    # === Phase 7 step 8.5: actionable view + journal append (D-01 / OUT-04) ===
    # The actionable view is a DERIVED frame: today_panel filtered by
    # ~adr_rejected & composite_score_raw >= JOURNAL_THRESHOLD & playbook_tag
    # in VALID_PLAYBOOK_TAGS. It is consumed by the report renderer AND the
    # journal-append helper. Never assigned back to today_panel (Blocker #1).
    actionable_view = today_panel[
        (~today_panel["adr_rejected"])
        & (today_panel["composite_score_raw"] >= settings.JOURNAL_THRESHOLD)
        & (today_panel["playbook_tag"].isin(_valid_playbook_tags))
    ]
    # Skipped view = rows that WOULD have been actionable but were rejected by
    # sizing (1xADR fail / invalid stop / missing diagnostics). Excludes the
    # ~95% playbook_tag='none' rows (they were never candidates).
    skipped_view = today_panel[
        today_panel["adr_rejected"]
        & today_panel["playbook_tag"].isin(_valid_playbook_tags)
    ].copy()

    if write_journal:
        from screener.persistence import (
            PicksSchema,
            append_picks_rows,
            validate_at_write,
        )

        journal_rows_df = _build_journal_rows_df(
            actionable_view, regime_row, snapshot_date, settings,
        )
        if not journal_rows_df.empty:
            validated = validate_at_write(PicksSchema, journal_rows_df)
            n_inserted = append_picks_rows(validated.to_dict(orient="records"))
            log.info(
                "journal_append_summary",
                snapshot_date=snapshot_date,
                n_attempted=len(validated),
                n_inserted=n_inserted,
                n_idempotent_skip=len(validated) - n_inserted,
            )
        else:
            log.info(
                "journal_append_summary",
                snapshot_date=snapshot_date,
                n_attempted=0, n_inserted=0, n_idempotent_skip=0,
                reason="no_actionable_picks_above_threshold",
            )
    else:
        log.info("journal_skipped", snapshot_date=snapshot_date, reason="write_journal=False")
    # === END Phase 7 step 8.5 ===

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
            skipped_picks=skipped_view,  # NEW Phase 7 kwarg
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
        wrote_journal=write_journal,
    )

    # === Phase 8 (OPS-05): append success record to data/runs.jsonl ===
    # Single atomic-on-disk append at the end of the function — RESEARCH
    # §Integration Points: "single append at the end is atomic on disk".
    # If any prior step raised, control never reaches here; the failure
    # record is written by `python -m screener.publishers.run_log failure`
    # in refresh.yml's `if: failure()` step (D-05).
    _ticker_universe_size = max(
        1, len(panel.index.get_level_values("ticker").unique())
    )
    _picks_count = int(
        (today_panel["composite_score_raw"] >= settings.JOURNAL_THRESHOLD).sum()
    )
    append_record(
        {
            "status": "success",
            "start_time": _start_iso,
            "duration_seconds": round(_time.perf_counter() - _t_start, 2),
            "fetch_success_rate": float(len(today_panel) / _ticker_universe_size),
            "regime_state": regime_state_value,
            "picks_count": _picks_count,
            "n_429_responses": 0,
            "error_reason": None,
        }
    )
    # === END Phase 8 (OPS-05) ===


# --- Phase 7 journal helper functions ------------------------------------


def _build_journal_rows_df(
    actionable_view: pd.DataFrame,
    regime_row: pd.Series,
    snapshot_date: str,
    settings: Any,
) -> pd.DataFrame:
    """Build the PicksSchema-shaped DataFrame for journal append (CONTEXT D-01 / D-03).

    Input is the actionable VIEW (revision iteration 1 Blocker #1) -- already
    pre-filtered upstream by ~adr_rejected & composite_score_raw >= threshold &
    valid playbook_tag. The only remaining filter here is regime_state !=
    'Correction' (CONTEXT D-01 actionable-pick gate).

    Returns an empty DataFrame (with PicksSchema columns) when no rows qualify.

    Warning #5 (revision iter 1): the INSERT row builder uses key
    `pivot_distance_atr_breakout` (matches Plan 07-03 revised PicksSchema
    column name).
    """
    import json as _json
    from datetime import UTC, datetime

    regime_state = str(regime_row["regime_state"])
    schema_cols = [
        "ticker", "snapshot_date", "playbook_tag", "composite_score",
        "regime_state", "entry_price", "stop_price", "shares",
        "risk_per_share", "atr_zone", "pivot_distance_atr_breakout",
        "features_json", "ingested_at",
    ]
    if regime_state == "Correction" or actionable_view.empty:
        return pd.DataFrame(columns=schema_cols)

    now_iso = datetime.now(UTC).isoformat(timespec="seconds")

    rows = []
    for ticker, row in actionable_view.iterrows():
        # CONTEXT D-03 features_json: score components + indicators + sizing inputs + diagnostics.
        features = {
            "features_json_version": "v1.0",
            # Score components (Phase 4/6 composite layer).
            "rs_rating": _safe_int(row.get("rs_rating")),
            "trend_template_score": _safe_int(row.get("trend_template_score")),
            "pattern_component": _safe_float(row.get("pattern_component")),
            "volume_component": _safe_float(row.get("volume_component")),
            "earnings_component": _safe_float(row.get("earnings_component")),
            "catalyst_component": _safe_float(row.get("catalyst_component")),
            "composite_score": float(row["composite_score"]),
            "composite_score_raw": float(row.get("composite_score_raw", row["composite_score"])),
            "regime_score": float(row.get("regime_score", regime_row["regime_score"])),
            "regime_state": regime_state,
            "playbook_tag": str(row["playbook_tag"]),
            "qullamaggie_score": _safe_int(row.get("qullamaggie_score")),
            "minervini_score": _safe_int(row.get("minervini_score")),
            "leader_hold_score": _safe_int(row.get("leader_hold_score")),
            # Indicator values at signal time.
            "atr_14": _safe_float(row.get("atr_14")),
            "adr_pct": _safe_float(row.get("adr_pct")),
            "dryup_ratio": _safe_float(row.get("dryup_ratio")),
            "breakout_strength": _safe_float(row.get("breakout_strength")),
            "sma_50": _safe_float(row.get("sma_50")),
            "sma_150": _safe_float(row.get("sma_150")),
            "sma_200": _safe_float(row.get("sma_200")),
            "high_52w": _safe_float(row.get("high_52w")),
            "low_52w": _safe_float(row.get("low_52w")),
            # Sizing inputs.
            "entry_price": float(row["entry_price"]),
            "stop_price": float(row["stop_price"]),
            "shares": int(row["shares"]),
            "risk_per_share": float(row["risk_per_share"]),
            "atr_zone": str(row["atr_zone"]),
            "pivot_distance_atr": _safe_float(row.get("pivot_distance_atr")),  # Phase 4 col
            "pivot_distance_atr_breakout": _safe_float(row.get("pivot_distance_atr_breakout")),
            "account_equity_used": float(settings.ACCOUNT_EQUITY),
            "risk_pct_used": float(settings.RISK_PCT),
            "entry_price_semantics": "close_as_next_open_estimate",
            # Full inline pattern_diagnostics (Phase 6 D-05 schema dict).
            "pattern_diagnostics": _safe_decode_json(
                row.get("pattern_diagnostics", '{"type":"none"}')
            ),
        }
        # After _add_publisher_columns (pipeline step 7) resets the index,
        # 'ticker' becomes a column and the iter key is an integer position.
        # Prefer row["ticker"] (column) when present; fall back to the index
        # value for callers that pass a ticker-indexed actionable_view directly
        # (e.g. _build_journal_rows_df_from_snapshot).
        ticker_val = str(row["ticker"]) if "ticker" in row.index else str(ticker)
        rows.append({
            "ticker": ticker_val,
            "snapshot_date": str(snapshot_date),
            "playbook_tag": str(row["playbook_tag"]),
            "composite_score": float(row["composite_score"]),
            "regime_state": regime_state,
            "entry_price": float(row["entry_price"]),
            "stop_price": float(row["stop_price"]),
            "shares": int(row["shares"]),
            "risk_per_share": float(row["risk_per_share"]),
            "atr_zone": str(row["atr_zone"]),
            # Warning #5 (revision iter 1): use the renamed PicksSchema column.
            # Nullable in the schema; coerce NaN -> None so pandera + sqlite3 see
            # a real NULL rather than a float('nan').
            "pivot_distance_atr_breakout": (
                None
                if pd.isna(row.get("pivot_distance_atr_breakout"))
                else float(row["pivot_distance_atr_breakout"])
            ),
            "features_json": _json.dumps(features, default=str, sort_keys=True),
            "ingested_at": now_iso,
        })

    return pd.DataFrame(rows)


def _build_journal_rows_df_from_snapshot(snapshot_date: str) -> pd.DataFrame:
    """Read data/snapshots/<snapshot_date>.parquet and rebuild the journal-rows
    DataFrame for cli.journal catch-up (CONTEXT D-01).

    The snapshot Parquet has all sizing columns (Plan 07-04 step 5.5 populates
    them; W-Plan05-1 projection writes them through to the snapshot). It ALSO
    has `composite_score_raw` (Plan 07-01 revised + Warning #6) -- meaning the
    catch-up flow uses the SAME pre-gate threshold semantics as the live
    pipeline. No per-flow divergence.
    """
    settings = get_settings()
    snap_dir = Path(getattr(settings, "SNAPSHOT_DIR", "data/snapshots"))
    snap_path = snap_dir / f"{snapshot_date}.parquet"
    if not snap_path.exists():
        log.info("journal_catchup_snapshot_missing", path=str(snap_path))
        return pd.DataFrame()

    snap = pd.read_parquet(snap_path)
    if snap.empty:
        return pd.DataFrame()

    regime_state = str(snap["regime_state"].iloc[0])
    regime_row = pd.Series({
        "regime_state": regime_state,
        "regime_score": float(snap["regime_score"].iloc[0]),
    })

    # Re-derive the actionable view from the snapshot. Same predicate as the
    # live pipeline (Warning #6 single-source-of-truth).
    valid_playbook_tags = ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
    # composite_score_raw is a real column on the snapshot (Plan 07-01 revised);
    # fall back to composite_score only if a legacy snapshot lacks it.
    raw_col = (
        snap["composite_score_raw"]
        if "composite_score_raw" in snap.columns
        else snap["composite_score"]
    )
    threshold = float(settings.JOURNAL_THRESHOLD)
    # adr_rejected is also a real column on the snapshot (Plan 07-01 revised);
    # fall back to False (all-actionable) only if a legacy snapshot lacks it.
    rejected_col = (
        snap["adr_rejected"]
        if "adr_rejected" in snap.columns
        else pd.Series(False, index=snap.index)
    )
    mask = (
        (~rejected_col.fillna(False))
        & (raw_col >= threshold)
        & (snap["playbook_tag"].isin(valid_playbook_tags))
    )
    actionable_view = snap.loc[mask].copy()
    if "ticker" in actionable_view.columns:
        actionable_view = actionable_view.set_index("ticker")

    return _build_journal_rows_df(actionable_view, regime_row, snapshot_date, settings)


# --- private safe-coerce helpers (defensive against NaN / None / Int64NA) -

def _safe_int(v: Any) -> int | None:
    if v is None or pd.isna(v):
        return None
    return int(v)


def _safe_float(v: Any) -> float | None:
    if v is None or pd.isna(v):
        return None
    return float(v)


def _safe_decode_json(v: Any) -> dict:
    import json as _json
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return {"type": "none"}
    try:
        return _json.loads(str(v))
    except (ValueError, TypeError):
        return {"type": "none"}
