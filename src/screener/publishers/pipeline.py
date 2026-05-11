"""publishers.pipeline — orchestrator for the daily report run.

Composes the Phase 4 DAG (D-03 + D-07 + D-08):
    build_panel -> passes_trend_template -> composite.score
        -> apply_regime_gate (soft, D-03)
        -> validate_run (D-07 warn / D-08 hard fail)
        -> write_snapshot + (optional) write_report

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

    D-07: pass_rate > warn_threshold (default 0.25) -> structlog warning,
          no exit. The publisher report.py renders a banner in the data-
          quality footer.

    D-08: pass_rate > fail_threshold_with_correction (default 0.25) AND
          regime_state == 'Correction' -> typer.Exit(code=1). Caller (the
          CLI body in Plan 04-05) MUST allow typer.Exit to propagate so
          the process exit code reflects the failure (Pitfall 7).

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

    # 1. Build the indicator panel for the snapshot date.
    panel = build_panel(snapshot_date)

    # 2. Compute Trend Template gate + score columns.
    panel = passes_trend_template(panel)

    # 3. Compute composite scores via weights-dict (D-13).
    panel = score(panel, DEFAULT_WEIGHTS)

    # 4. Cross-section the panel to the snapshot date (one row per ticker).
    snap_ts = pd.Timestamp(snapshot_date)
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
    from screener.publishers.report import _add_publisher_columns

    today_panel = _add_publisher_columns(today_panel, regime_row)

    # 8. Write the Parquet snapshot (always — used by Phase 5 backtest).
    from screener.publishers.snapshot import write_snapshot

    write_snapshot(today_panel, snapshot_date)

    # 9. Optionally render + write the Markdown report.
    if write_report:
        from screener.publishers.report import write_report as write_report_md

        write_report_md(
            today_panel,
            regime_row,
            snapshot_date,
            top_n=settings.REPORT_TOP_N,
            pass_rate=pass_rate,
        )

    log.info(
        "pipeline_complete",
        snapshot_date=snapshot_date,
        n_tickers=len(today_panel),
        pass_rate=pass_rate,
        regime_state=regime_state_value,
        regime_score=regime_score_value,
        wrote_report=write_report,
    )
