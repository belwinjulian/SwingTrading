"""publishers.report — daily Markdown report writer (OUT-01, OUT-02).

Produces reports/YYYY-MM-DD.md with: regime banner, top-N picks table,
per-pick blocks (composite breakdown including PHASE_4_ZEROED placeholders
per D-04), and data-quality footer (with WARNING banner when D-07 fires).

Atomic write via tempfile + os.replace (same-filesystem rename — POSIX-atomic).
Mirrors persistence._write_parquet_atomic but writes UTF-8 text instead of
Parquet.

Architecture (D-16): publishers/ may import {signals, sizing, regime,
persistence, config, obs}. No data/, no network.

No emoji per CLAUDE.md "Coding Conventions" + Phase 4 RESEARCH Pitfall 12 --
plain ASCII only ('WARNING:', not a warning symbol).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import structlog

from screener.config import get_settings
from screener.signals.composite import DEFAULT_WEIGHTS, PHASE_4_ZEROED

log = structlog.get_logger(__name__)

PivotZone = Literal["in-zone", "chase, skip", "unknown"]

PIVOT_COLUMN_HEADER = "ATR from 52w high (Phase 4 proxy)"  # D-05 verbatim


# --- Helpers --------------------------------------------------------------


def _report_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "REPORT_DIR", "reports"))


def _classify_pivot_zone(close: float, high_52w: float, atr: float) -> PivotZone:
    """D-06 + Pitfall 5: 3-state pivot zone classifier.

    Returns 'unknown' when high_52w is NaN, atr is NaN, or atr == 0.
    Returns 'in-zone' when close is within 1 ATR *below* the 52-week high
    (0.0 <= (high_52w - close) / atr <= 1.0); else 'chase, skip'.

    Per REVIEW CR-05: distance is measured as (high_52w - close) / atr so a
    stock trading well below its 52-week high (e.g., -10 ATR) is classified
    as 'chase, skip' (a laggard, not a near-pivot candidate). Stocks above
    the 52-week high (breakouts) also classify as 'chase, skip' here --
    Phase 6 with the real VCP pivot will refine the breakout case.
    """
    if pd.isna(high_52w) or pd.isna(atr) or atr == 0:
        return "unknown"
    distance = (high_52w - close) / atr  # positive when close is BELOW high_52w
    return "in-zone" if 0.0 <= distance <= 1.0 else "chase, skip"


def _add_publisher_columns(
    cross: pd.DataFrame, regime_row: pd.Series
) -> pd.DataFrame:
    """Add pivot_distance_atr, pivot_zone, regime_state, regime_score, rank
    columns to a cross-section frame. Used by run_pipeline before snapshot
    write so the snapshot satisfies RankingSnapshotSchema.

    Phase 6 (Plan 06-01) extension: emit safe defaults for the 11 new
    RankingSnapshotSchema columns when callers (Phase 4 fixtures, Phase 5
    backfill, this Wave-0 plan) have not yet wired the pattern / playbook /
    catalyst layers. Plans 06-02/06-03/06-04 replace these defaults with the
    real values upstream; the column-add here only runs when the column is
    missing, so once the new computations exist the placeholders are silently
    superseded.
    """
    out = cross.copy()
    # Pitfall 5: replace 0 ATR with NA before division.
    # REVIEW CR-05: sign convention is (high_52w - close)/atr so a positive
    # number means close is BELOW the 52w high (small positive = near-pivot;
    # large positive = laggard). Matches _classify_pivot_zone's distance.
    atr_safe = out["atr_14"].replace(0, pd.NA)
    out["pivot_distance_atr"] = (out["high_52w"] - out["close"]) / atr_safe
    out["pivot_zone"] = [
        _classify_pivot_zone(c, h, a)
        for c, h, a in zip(out["close"], out["high_52w"], out["atr_14"], strict=False)
    ]
    out["regime_state"] = str(regime_row["regime_state"])
    out["regime_score"] = float(regime_row["regime_score"])
    # Rank by composite_score desc; ties get the same rank ('dense'); NaN -> bottom.
    out["rank"] = pd.array(
        out["composite_score"]
        .rank(ascending=False, method="dense", na_option="bottom")
        .astype("Int64"),
        dtype=pd.Int64Dtype(),
    )

    # Phase 6 Wave-0 (Plan 06-01) placeholder defaults for the extended
    # RankingSnapshotSchema. Each is set only if absent so downstream Phase 6
    # plans can populate the real values upstream without colliding.
    n = len(out)
    if "playbook_tag" not in out.columns:
        out["playbook_tag"] = ["none"] * n
    if "qullamaggie_score" not in out.columns:
        out["qullamaggie_score"] = pd.array([0] * n, dtype=pd.Int64Dtype())
    if "minervini_score" not in out.columns:
        out["minervini_score"] = pd.array([0] * n, dtype=pd.Int64Dtype())
    if "leader_hold_score" not in out.columns:
        out["leader_hold_score"] = pd.array([0] * n, dtype=pd.Int64Dtype())
    if "pattern_diagnostics" not in out.columns:
        # JSON-encoded "no pattern" dict; Plan 06-02 swaps in real diagnostics.
        out["pattern_diagnostics"] = ['{"type": "none"}'] * n
    if "breakout_strength" not in out.columns:
        out["breakout_strength"] = [0.0] * n
    if "days_to_next_earnings" not in out.columns:
        out["days_to_next_earnings"] = pd.array([pd.NA] * n, dtype=pd.Int64Dtype())
    if "crossed_52w_high_within_60d" not in out.columns:
        out["crossed_52w_high_within_60d"] = [False] * n
    if "insider_cluster_buy" not in out.columns:
        out["insider_cluster_buy"] = [False] * n
    if "earnings_in_3d_warn" not in out.columns:
        out["earnings_in_3d_warn"] = [False] * n
    if "eps_knowable_from" not in out.columns:
        # Nullable string column; pandas keeps as object dtype.
        out["eps_knowable_from"] = pd.array([None] * n, dtype=object)

    if out.index.name != "ticker":
        # Cross-section is indexed by ticker; reset for snapshot column shape.
        out.index.name = "ticker"
    out = out.reset_index()
    return out


def _format_breakdown(row: pd.Series) -> str:
    """D-04 per-pick breakdown line -- iterates DEFAULT_WEIGHTS keys,
    renders PHASE_4_ZEROED entries as '--(Phase 6)' placeholders.

    Format: 'RS=92 | Trend=7/8 | Pattern=--(Phase 6) | Volume=0.7 |
    Earnings=--(Phase 6) | Catalyst=--(Phase 6)'
    """
    parts: list[str] = []
    for key in DEFAULT_WEIGHTS:
        label = key.capitalize()
        if key in PHASE_4_ZEROED:
            parts.append(f"{label}=--(Phase 6)")
        elif key == "rs":
            rs_val = row.get("rs_rating")
            rs_str = "?" if pd.isna(rs_val) else str(int(rs_val))
            parts.append(f"RS={rs_str}")
        elif key == "trend":
            tt_val = row.get("trend_template_score")
            tt_str = "?" if pd.isna(tt_val) else str(int(tt_val))
            parts.append(f"Trend={tt_str}/8")
        elif key == "volume":
            v_val = row.get("volume_component")
            v_str = "?" if pd.isna(v_val) else f"{float(v_val):.2f}"
            parts.append(f"Volume={v_str}")
    return " | ".join(parts)


def _write_text_atomic(content: str, target: Path) -> None:
    """Markdown-text analog of persistence._write_parquet_atomic.

    Tempfile MUST be in the same directory as target so os.replace() is a
    same-filesystem rename (POSIX-atomic). A crash leaves no partial file
    and the .tmp is unlinked.

    REVIEW WR-03 (iter 2) / WR-04 (iter 1): tempfile is created with
    delete=False so the context manager does NOT clean it up on exit.
    Perform the tmp.write() INSIDE the `with` block (consolidated with
    os.replace under a single try/except) so a SIGKILL between the outer
    `with` exit and the inner write call cannot orphan an empty .tmp.
    The iter-1 fix re-opened the empty tempfile for the actual write,
    which closed the disk-full leak but introduced a narrow empty-.tmp
    orphan window between `with` exit and the inner `open()`.

    REVIEW IN-01 (iter 3): the consolidated `write-inside-with` structure
    below is now STRICTER than persistence._write_parquet_atomic, which
    still uses the older split pattern (NamedTemporaryFile context exits
    before `df.to_parquet(tmp_path, ...)`, leaving a narrow empty-.tmp
    orphan window between `with` exit and the `to_parquet()` call). The
    parquet variant should be brought to the same standard in a follow-up
    (see persistence.py:_write_parquet_atomic). Both helpers remain
    POSIX-atomic at the `os.replace()` step; only the tempfile-cleanup
    guarantee differs.
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


# --- Render + write -------------------------------------------------------


def render_report(
    scored_cross: pd.DataFrame,
    regime_row: pd.Series,
    snapshot_date: str,
    top_n: int,
    pass_rate: float,
) -> str:
    """Render the daily Markdown report as a single string.

    Sections:
      # Daily Picks -- YYYY-MM-DD
      ## Regime
      ## Top {N} Picks       (table)
      ## Per-Pick Detail     (per-pick blocks -- D-04)
      ## Data Quality        (footer; WARNING banner if D-07 fires)
    """
    settings = get_settings()
    warn_thresh = settings.TREND_TEMPLATE_PASS_RATE_WARN

    # Prepare top-N (rank 1..N).
    top = scored_cross.sort_values("composite_score", ascending=False).head(top_n)

    # --- Header + regime ----
    lines: list[str] = []
    lines.append(f"# Daily Picks — {snapshot_date}")
    lines.append("")
    lines.append("## Regime")
    lines.append("")
    lines.append(f"**State:** {regime_row['regime_state']}")
    lines.append(f"**Score:** {float(regime_row['regime_score']):.2f}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Top-N picks table ----
    lines.append(f"## Top {top_n} Picks")
    lines.append("")
    pivot_hdr = PIVOT_COLUMN_HEADER
    lines.append(
        f"| Rank | Ticker | Composite | Trend Template | RS | Volume |"
        f" Pivot Zone | {pivot_hdr} |"
    )
    lines.append(
        "|-----:|--------|----------:|---------------:|---:|-------:|:-----------|----------------------------------:|"
    )
    for _, row in top.iterrows():
        ticker = str(row["ticker"]).replace("|", "")  # T-4-13 escape
        composite = float(row["composite_score"])
        tt = (
            "?" if pd.isna(row.get("trend_template_score"))
            else f"{int(row['trend_template_score'])}/8"
        )
        rs = (
            "?" if pd.isna(row.get("rs_rating"))
            else str(int(row["rs_rating"]))
        )
        vol = (
            "?" if pd.isna(row.get("volume_component"))
            else f"{float(row['volume_component']):.2f}"
        )
        pz = str(row.get("pivot_zone", "unknown"))
        pd_atr = row.get("pivot_distance_atr")
        pd_str = "?" if pd.isna(pd_atr) else f"{float(pd_atr):.2f}"
        rank_val = row.get("rank")
        rank_str = "?" if pd.isna(rank_val) else str(int(rank_val))
        lines.append(
            f"| {rank_str} "
            f"| {ticker} | {composite:.1f} | {tt} | {rs} | {vol} | {pz} | {pd_str} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Per-pick detail blocks (D-04) ----
    lines.append("## Per-Pick Detail")
    lines.append("")
    for i, (_, row) in enumerate(top.iterrows(), start=1):
        ticker = str(row["ticker"])
        composite = float(row["composite_score"])
        lines.append(f"### {i}. {ticker} -- Composite {composite:.1f}")
        lines.append("")
        lines.append("```")
        lines.append(_format_breakdown(row))
        lines.append("```")
        lines.append("")
        pz = str(row.get("pivot_zone", "unknown"))
        pd_atr = row.get("pivot_distance_atr")
        pd_str = "?" if pd.isna(pd_atr) else f"{float(pd_atr):.2f}"
        lines.append(
            f"- **Pivot zone:** {pz} ({pd_str} ATR from 52w high; "
            f"proxy -- Phase 6 will use real VCP pivot)"
        )
        lines.append("- **Playbook:** --(Phase 6)")
        lines.append("- **Catalysts:** --(Phase 6)")
        lines.append("")

    lines.append("---")
    lines.append("")

    # --- Data Quality footer ----
    lines.append("## Data Quality")
    lines.append("")
    if pass_rate > warn_thresh:
        # Pitfall 12: plain ASCII 'WARNING:', no emoji.
        lines.append(
            f"**WARNING: Pass rate {pass_rate * 100:.1f}% "
            f"(expected 5-15% -- verify data quality)**"
        )
        lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Universe size | {len(scored_cross)} |")
    lines.append(f"| Trend Template pass rate | {pass_rate * 100:.1f}% |")
    lines.append(
        f"| Snapshot | data/snapshots/{snapshot_date}.parquet |"
    )
    lines.append("")
    lines.append(
        "*Composite score is capped at ~55/100 in Phase 4 -- "
        "Pattern, Earnings, and Catalyst components ship in Phase 6.*"
    )
    lines.append("")

    return "\n".join(lines)


def write_report(
    scored_cross: pd.DataFrame,
    regime_row: pd.Series,
    snapshot_date: str,
    top_n: int,
    pass_rate: float,
) -> Path:
    """Render + atomically write the Markdown report to reports/<date>.md."""
    content = render_report(scored_cross, regime_row, snapshot_date, top_n, pass_rate)
    target = _report_dir() / f"{snapshot_date}.md"
    _write_text_atomic(content, target)
    log.info(
        "report_written",
        path=str(target),
        n_picks=min(top_n, len(scored_cross)),
        snapshot_date=snapshot_date,
        pass_rate=pass_rate,
    )
    return target
