"""backtest/report - markdown report renderer for `make backtest`.

Writes reports/backtest-YYYY-MM-DD.md with YAML frontmatter disclosure header
(BCK-06), OOS Sharpe distribution table (BCK-01), per-regime breakdown (BCK-05),
and per-playbook breakdown (BCK-04, stubbed as 'leader_hold' for Phase 5).

Architectural contract (D-17, RESEARCH section E L12): persistence + stdlib only +
intra-layer (backtest.vbt_runner and backtest.metrics are allowed). Uses
stdlib logging - NEVER structlog. The atomic-text-write helper is INLINE-COPIED
from publishers/report.py (cannot be imported across layers).

LOGGING DISCIPLINE (B-1 fix iter 2): stdlib `logging.Logger.<level>()` does
NOT accept arbitrary kwargs. All log lines use f-string form. NEVER use the
structlog-style `log.info("event", key=value)` pattern here.

B-3 fix iter 2: `_render_per_regime_section` consumes
`result.all_regime_returns` (long-format DataFrame produced by vbt_runner)
via `metrics.per_regime_breakdown`. The previous Phase-5 placeholder
("per-trade regime attribution arrives in Phase 6+") was wrong - the data
exists in snapshots (D-13, confirmed by persistence.RankingSnapshotSchema).

C-2 fix iter 3: `_render_per_regime_section` emits a visible WARN line in the
rendered markdown when `result.all_regime_returns.empty`. Surfaces the
empty-input failure mode user-visibly in the report instead of letting three
benign-looking "0 / -" rows look like a legitimate data state. Wording is
verbatim from 05-RESEARCH.md section A Q11.
"""

from __future__ import annotations

import logging
import math
import os
import subprocess
import tempfile
from datetime import date as date_type
from pathlib import Path

from screener.backtest.metrics import (
    CANONICAL_REGIMES,
    per_playbook_breakdown,
    per_regime_breakdown,
)
from screener.backtest.vbt_runner import SLIPPAGE_TIERS, BacktestResult

log = logging.getLogger(__name__)


COMMONS_CLAUSE_CAVEAT = (
    "vectorbt is Apache 2.0 + Commons Clause licensed. These backtest results "
    "are for personal/research/portfolio use; commercial resale is prohibited."
)

SURVIVORSHIP_CAVEAT = (
    "Universe is the iShares IWB constituent list as of universe_source_date. "
    "Historical members of Russell 1000 who were delisted before that date are "
    "NOT in the test set. This introduces a known upward bias of ~1-2% CAGR. "
    "Mitigation: walk-forward OOS sliding window reduces single-period overfit."
)

# C-2 fix iter 3: verbatim WARN line for empty all_regime_returns case.
# Wording sourced from 05-RESEARCH.md section A Q11; do NOT paraphrase.
EMPTY_REGIME_RETURNS_WARN_LINE = (
    "> ⚠ No regime-attributed returns produced. See 05-RESEARCH.md §A Q11."
)


def _write_text_atomic(content: str, target: Path) -> None:
    """Markdown-text analog of persistence._write_parquet_atomic.

    Tempfile MUST be in the same directory as target so os.replace() is a
    same-filesystem rename (POSIX-atomic). Copied verbatim (stdlib-only) from
    publishers/report.py:126-169 - cannot be imported across layers per D-17.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def _resolve_universe_source_date(provided: str | None) -> str:
    """Find the most-recent data/universe/<date>.parquet stem, or 'unknown'."""
    if provided is not None:
        return provided
    universe_dir = Path("data/universe")
    if not universe_dir.exists():
        return "unknown"
    candidates = sorted(universe_dir.glob("*.parquet"))
    if not candidates:
        return "unknown"
    return candidates[-1].stem


def _resolve_preregistration_hash(provided: str | None) -> str:
    """Get the most recent git hash for the preregistration doc, or 'unknown'."""
    if provided is not None:
        return provided
    try:
        # T-5-02 mitigation: list-form argv, shell=False (default).
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "docs/strategy_v1_preregistration.md"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    return "unknown"


def _render_frontmatter(
    result: BacktestResult,
    universe_source_date: str,
    preregistration_hash: str,
) -> str:
    """Render the YAML frontmatter block (BCK-06)."""
    lines: list[str] = ["---"]
    lines.append(f"backtest_date: {date_type.today().isoformat()}")
    lines.append(f"universe_source_date: {universe_source_date}")
    lines.append("survivorship_caveat: |")
    for caveat_line in SURVIVORSHIP_CAVEAT.split(". "):
        if caveat_line.strip():
            sep = "." if not caveat_line.endswith(".") else ""
            lines.append(f"  {caveat_line.strip()}{sep}")
    lines.append("slippage_tiers:")
    # SLIPPAGE_TIERS is the single source of truth (Pitfall 7); render verbatim.
    # Order: (50M->5bps), (5M->15bps), (0->30bps)
    lines.append("  - adv_gt: 50000000  # $50M")
    lines.append(f"    bps: {int(SLIPPAGE_TIERS[0][1] * 10000)}")
    lines.append("  - adv_range: [5000000, 50000000]  # $5M-$50M")
    lines.append(f"    bps: {int(SLIPPAGE_TIERS[1][1] * 10000)}")
    lines.append("  - adv_lt: 5000000  # $5M")
    lines.append(f"    bps: {int(SLIPPAGE_TIERS[2][1] * 10000)}")
    lines.append("period_selection:")
    lines.append("  is_years: 3")
    lines.append("  oos_years: 1")
    lines.append("  slide_years: 1")
    lines.append(f"  windows_count: {len(result.windows)}")
    if result.windows:
        lines.append(f"  earliest_is_start: {result.windows[0].is_start.date().isoformat()}")
        lines.append(f"  latest_oos_end: {result.windows[-1].oos_end.date().isoformat()}")
    lines.append("regime_gate:")
    lines.append("  type: soft")
    lines.append(
        "  formula: composite_score *= regime_score  "
        "# see publishers/pipeline.apply_regime_gate"
    )
    lines.append("playbook_attribution:")
    lines.append("  status: stubbed")
    lines.append(
        "  note: All picks tagged 'leader_hold' "
        "until Phase 6 ships VCP/Qullamaggie detectors."
    )
    lines.append("preregistration:")
    lines.append(f"  weights_hash: {preregistration_hash}")
    lines.append("  doc: docs/strategy_v1_preregistration.md")
    lines.append("library_license:")
    lines.append("  vectorbt: Apache-2.0 + Commons Clause")
    lines.append(f"  caveat: {COMMONS_CLAUSE_CAVEAT!r}")
    lines.append("---")
    return "\n".join(lines)


def _render_sharpe_distribution_section(result: BacktestResult) -> str:
    """Render the OOS Sharpe distribution table (BCK-01)."""
    lines: list[str] = ["## OOS Sharpe Distribution"]
    lines.append("")
    lines.append(
        "| Window | IS Period | OOS Period | OOS Sharpe | "
        "OOS MaxDD | OOS WinRate | N Trades |"
    )
    lines.append(
        "|--------|-----------|------------|------------|"
        "-----------|-------------|----------|"
    )
    for i, w in enumerate(result.windows, start=1):
        is_period = f"{w.is_start.date()}..{w.is_end.date()}"
        oos_period = f"{w.oos_start.date()}..{w.oos_end.date()}"
        sharpe_str = f"{w.oos_sharpe:.2f}" if not _is_nan(w.oos_sharpe) else "n/a"
        lines.append(
            f"| {i} | {is_period} | {oos_period} | {sharpe_str} | "
            f"{w.oos_max_dd:.2%} | {w.oos_win_rate:.2%} | {w.n_trades} |"
        )
    lines.append("")
    lines.append(
        f"**Summary:** Sharpe distribution: "
        f"min={result.sharpe_min:.2f} | "
        f"median={result.sharpe_median:.2f} | "
        f"max={result.sharpe_max:.2f} "
        f"(n_zero_trade_windows={result.n_zero_trade_windows})"
    )
    lines.append("")
    return "\n".join(lines)


def _format_metric(value: float, fmt: str) -> str:
    """Format a float using `fmt`, returning '-' when NaN/Inf (B-3 empty-regime rendering)."""
    if value is None or _is_nan(value) or math.isinf(value):
        return "—"
    return format(value, fmt)


def _render_per_regime_section(result: BacktestResult) -> str:
    """Render the per-regime breakdown section (BCK-05) - REAL 3-row table.

    B-3 fix iter 2: Consumes `result.all_regime_returns` (long-format
    DataFrame [date, regime_state, daily_return] built per OOS window in
    vbt_runner) via `metrics.per_regime_breakdown`. Always emits 3 rows
    (CANONICAL_REGIMES). Empty regimes render with '0 / -' values rather
    than being omitted, so the report makes the universe of possible
    regimes visible at all times.

    The previous Phase-5 stub ("per-trade regime attribution arrives in
    Phase 6+") was incorrect - `regime_state` is already in snapshots
    per Phase 4's RankingSnapshotSchema (D-13, persistence.py:246-249).

    C-2 fix iter 3: when `result.all_regime_returns.empty`, emit the
    `EMPTY_REGIME_RETURNS_WARN_LINE` (verbatim from RESEARCH section A
    Q11) at the top of the section, BEFORE the 3-row table. The table
    still renders (with `0 | - | - | -` for every regime) so the report's
    structural layout stays consistent across runs, but the WARN line
    distinguishes "harness produced no regime-attributed returns at all"
    (likely an upstream defect - zero-window backtest, vbt API change,
    etc.) from "all 3 regimes happened to have zero observed days" (a
    legitimate, vanishingly-rare data state).
    """
    lines: list[str] = ["## Per-Regime Breakdown (BCK-05)"]
    lines.append("")
    lines.append(
        "Per-day OOS portfolio return attributed to the regime active on that "
        "date (sourced from `regime_state` in `data/snapshots/*.parquet`, D-13). "
        "Empty rows indicate no OOS days observed in that regime."
    )
    lines.append("")

    # C-2 fix iter 3: emit a visible WARN line when there are NO regime-attributed
    # returns at all. The 3-row table still renders below for structural
    # consistency, but this line tells the user the empty result came from the
    # empty-input fallback (likely upstream defect) rather than three regimes
    # that happened to be unobserved.
    if result.all_regime_returns is None or result.all_regime_returns.empty:
        lines.append(EMPTY_REGIME_RETURNS_WARN_LINE)
        lines.append("")
        # Also log it so CI/audit picks it up (B-1 f-string form).
        log.warning(
            "report_empty_regime_returns "
            "see=05-RESEARCH.md_sectionA_Q11 "
            f"n_windows={len(result.windows)}"
        )

    lines.append("| Regime | N Days | Total Return | Sharpe | Win Rate |")
    lines.append("|--------|--------|--------------|--------|----------|")

    breakdown = per_regime_breakdown(result.all_regime_returns)
    for regime in CANONICAL_REGIMES:
        if regime not in breakdown.index:
            # Defensive fallback - per_regime_breakdown always returns all 3,
            # but if a future contract change breaks that, render an empty row.
            lines.append(f"| {regime} | 0 | — | — | — |")
            continue
        row = breakdown.loc[regime]
        n_days_val = row["n_days"]
        n_days = int(n_days_val) if not _is_nan(n_days_val) else 0
        total_ret = _format_metric(row["total_return"], ".2%")
        sharpe = _format_metric(row["sharpe"], ".2f")
        win_rate = _format_metric(row["win_rate"], ".2%")
        lines.append(f"| {regime} | {n_days} | {total_ret} | {sharpe} | {win_rate} |")

    lines.append("")
    return "\n".join(lines)


def _render_per_playbook_section(result: BacktestResult) -> str:
    """Render the per-playbook attribution section (BCK-04, stubbed as leader_hold per D-12).

    Phase 5 (D-12): The harness does not yet tag trades with `playbook_tag`
    (Phase 6 adds VCP/Qullamaggie detectors and the tag column). For now,
    emit a single 'leader_hold' row aggregating all trades. The code path
    is structured so when Phase 6 ships a per-trade DataFrame with
    `playbook_tag`, the rendering will pick up additional rows automatically.
    """
    lines: list[str] = ["## Per-Playbook Attribution (BCK-04)"]
    lines.append("")
    lines.append(
        "Phase 5 stub (D-12): all picks tagged 'leader_hold'. "
        "Phase 6 adds 'qullamaggie_continuation' and 'minervini_vcp' rows."
    )
    lines.append("")
    lines.append("| Playbook | N Trades | Total Return | Mean OOS Sharpe | Max DD | Win Rate |")
    lines.append("|----------|----------|--------------|-----------------|--------|----------|")
    total_trades = sum(w.n_trades for w in result.windows)
    total_return = result.total_return
    mean_sharpe = result.sharpe_median
    max_dd = min((w.oos_max_dd for w in result.windows), default=0.0)
    mean_wr = (
        sum(w.oos_win_rate for w in result.windows) / max(len(result.windows), 1)
        if result.windows
        else 0.0
    )
    lines.append(
        f"| leader_hold | {total_trades} | {total_return:.2%} | "
        f"{_format_metric(mean_sharpe, '.2f')} | "
        f"{max_dd:.2%} | {mean_wr:.2%} |"
    )
    # Reference to metrics.per_playbook_breakdown so Phase 6 can swap in the
    # real per-trade DataFrame without restructuring this section.
    _ = per_playbook_breakdown
    lines.append("")
    return "\n".join(lines)


def _is_nan(x: float) -> bool:
    """Stdlib NaN check (avoids numpy dep at this layer; equivalent to math.isnan)."""
    if x is None:
        return True
    try:
        return x != x  # NaN is the only value where x != x
    except TypeError:
        return False


def render_report(
    result: BacktestResult,
    output_path: Path,
    *,
    universe_source_date: str | None = None,
    preregistration_hash: str | None = None,
) -> Path:
    """Render the backtest report to output_path (atomic write).

    Args:
        result: BacktestResult from vbt_runner.run().
        output_path: Target Path, e.g. Path('reports/backtest-2026-05-16.md').
        universe_source_date: Override the auto-discovered universe stem (test seam).
        preregistration_hash: Override the auto-discovered git hash (test seam).

    Returns:
        The resolved output_path.

    Raises:
        OSError: if the tempfile cannot be created (disk full, etc.).
    """
    universe_src = _resolve_universe_source_date(universe_source_date)
    prereg_hash = _resolve_preregistration_hash(preregistration_hash)

    sections: list[str] = [
        _render_frontmatter(result, universe_src, prereg_hash),
        "",
        f"# Backtest Report - {date_type.today().isoformat()}",
        "",
        _render_sharpe_distribution_section(result),
        _render_per_regime_section(result),
        _render_per_playbook_section(result),
    ]
    content = "\n".join(sections)
    _write_text_atomic(content, output_path)
    # B-1 fix: stdlib logger - f-string form, NEVER **kwargs.
    log.info(
        f"report_written path={output_path} n_windows={len(result.windows)} "
        f"sharpe_median={result.sharpe_median}"
    )
    return output_path
