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


def _decode_diag(raw: Any) -> dict[str, Any]:
    """Inline JSON decode for pattern_diagnostics. Architecture constraint:
    publishers/ may not import indicators/ — replicate the decode logic here.
    Returns {} on any parse failure (safe default for render path).
    """
    import json as _json

    if isinstance(raw, dict):
        return raw
    try:
        return _json.loads(str(raw or "{}"))
    except (ValueError, TypeError):
        return {}


def _format_breakdown(row: pd.Series) -> str:
    """D-19 per-pick breakdown line -- iterates DEFAULT_WEIGHTS keys.

    Phase 6 format:
    'RS=92 | Trend=8/8 | Pattern=0.67 (VCP, 4 contractions, brk_vol=2.1x) |
     Volume=0.7 | Earnings=1 (EPS YoY >=25%) | Catalyst=0.67 (2/3 flags)'
    """
    parts: list[str] = []
    for key in DEFAULT_WEIGHTS:
        if key in PHASE_4_ZEROED:
            parts.append(f"{key.capitalize()}=--(Phase 6)")
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
        elif key == "pattern":
            # Architecture constraint: publishers/ may not import indicators/.
            # Inline decode rather than importing decode_pattern_diagnostics.
            diag = _decode_diag(row.get("pattern_diagnostics", "{}"))
            pat_val = float(row.get("pattern_component", 0.0) or 0.0)
            brk_vol = float(diag.get("breakout_vol_multiple") or 0.0)
            pat_type = diag.get("type", "none")
            if pat_type == "vcp":
                detail = (
                    f"VCP, {diag.get('n_contractions', 0)} contractions, "
                    f"brk_vol={brk_vol:.1f}x"
                )
            elif pat_type == "flag":
                detail = (
                    f"flag, {diag.get('flag_bars', 0)} bars, "
                    f"brk_vol={brk_vol:.1f}x"
                )
            else:
                detail = "no pattern"
            parts.append(f"Pattern={pat_val:.2f} ({detail})")
        elif key == "earnings":
            # W11: derive C-pass from earnings_component score (>0.5 == passes).
            # eps_knowable_from IS a snapshot column; absent == omit hint.
            earnings_score = float(row.get("earnings_component", 0.0) or 0.0)
            if earnings_score > 0.5:
                earnings_label = "(EPS YoY >=25%)"
            else:
                knowable = row.get("eps_knowable_from") or ""
                hint = f", knowable {knowable}" if knowable else ""
                earnings_label = f"(EPS pending{hint})"
            parts.append(f"Earnings={round(earnings_score)} {earnings_label}")
        elif key == "catalyst":
            cat_val = float(row.get("catalyst_component", 0.0) or 0.0)
            days_raw = row.get("days_to_next_earnings")
            days_int = (
                int(days_raw)
                if days_raw is not None and not pd.isna(days_raw)
                else 999
            )
            flags = sum([
                int(0 <= days_int <= 14),
                int(bool(row.get("crossed_52w_high_within_60d", False))),
                int(bool(row.get("insider_cluster_buy", False))),
            ])
            parts.append(f"Catalyst={cat_val:.2f} ({flags}/3 flags)")
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


def _render_per_pick_block(
    i: int, row: pd.Series, lines: list[str]
) -> None:
    """Render a single per-pick detail block (D-04 / D-19) into `lines`.

    Called from both the top-N and the Currently Held / Leaders sections.
    Phase 7: adds Entry/Stop/Trail/Shares/Zone lines when sizing columns
    are present (guarded on stop_price notna).
    """
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
    # D-19 playbook line
    tag = str(row.get("playbook_tag", "none"))
    q = int(row.get("qullamaggie_score") or 0)
    m = int(row.get("minervini_score") or 0)
    lh = int(row.get("leader_hold_score") or 0)
    lines.append(f"- **Playbook:** {tag} (Q={q}, M={m}, LH={lh})")
    # D-11a earnings warning
    if bool(row.get("earnings_in_3d_warn", False)):
        days_raw = row.get("days_to_next_earnings")
        days = int(days_raw) if days_raw is not None and not pd.isna(days_raw) else 0
        lines.append(f"- **WARNING: Earnings in {days}d**")
    # Catalyst flags (D-19)
    cat_flags: list[str] = []
    days_raw2 = row.get("days_to_next_earnings")
    days_int2 = (
        int(days_raw2)
        if days_raw2 is not None and not pd.isna(days_raw2)
        else 999
    )
    if 0 <= days_int2 <= 14:
        cat_flags.append(f"earnings in {days_int2}d")
    if bool(row.get("crossed_52w_high_within_60d", False)):
        cat_flags.append("crossed 52w high within 60d")
    if bool(row.get("insider_cluster_buy", False)):
        cat_flags.append("insider cluster-buy")
    lines.append("- **Catalysts:** " + (", ".join(cat_flags) if cat_flags else "none"))
    lines.append("")

    # Phase 7 sizing per-pick block (CONTEXT <specifics> - D-04..D-09).
    # Guard on stop_price notna so non-actionable rows (playbook_tag='none'
    # in the snapshot - Plan 07-04 revised writes the FULL universe) skip
    # this block silently. Actionable rows have sizing populated.
    if "stop_price" in row.index and pd.notna(row.get("stop_price")):
        stop = float(row["stop_price"])
        entry = float(row["entry_price"])
        shares_v = int(row["shares"])
        zone = str(row.get("atr_zone", "unknown"))
        pdist_b = row.get("pivot_distance_atr_breakout")
        pdist_str = "?" if pd.isna(pdist_b) else f"{float(pdist_b):.2f}"
        trail = str(row.get("trail_rule_label", ""))
        playbook = str(row.get("playbook_tag", "none"))
        # D-07 stop-source label per playbook.
        stop_label = {
            "qullamaggie_continuation": "low-of-entry-day",
            "minervini_vcp": "final-contraction-low",
            "leader_hold": "max(1.5xATR, recent swing low)",
        }.get(playbook, "")
        lines.append(f"- **Entry:** ${entry:.2f}")
        lines.append(f"- **Stop:** ${stop:.2f} ({stop_label})   **Trail:** {trail}")
        lines.append(f"- **Shares:** {shares_v}")
        lines.append(f"- **Zone:** {zone} ({pdist_str}xATR above pivot)")
        lines.append("")


def render_report(
    scored_cross: pd.DataFrame,
    regime_row: pd.Series,
    snapshot_date: str,
    top_n: int,
    pass_rate: float,
    skipped_picks: pd.DataFrame | None = None,
) -> str:
    """Render the daily Markdown report as a single string.

    Sections:
      # Daily Picks -- YYYY-MM-DD
      ## Regime
      ## Top {N} Picks       (table -- qullamaggie_continuation + minervini_vcp only)
      ## Per-Pick Detail     (per-pick blocks -- D-04 / D-19 + Phase 7 sizing)
      ## Currently Held / Leaders  (leader_hold picks -- D-15; Pitfall 9)
      ## Skipped Picks       (D-06 rejected picks -- Phase 7; only if non-empty)
      ## Data Quality        (footer; WARNING banner if D-07 fires)

    Args:
        skipped_picks: Phase 7 kwarg (default None, backwards-compat). When
            non-empty, renders a ## Skipped Picks section after the per-pick
            blocks and before ## Data Quality. Contains ADR-rejected picks
            from sizing (SIZ-02 1xADR auto-reject, invalid stop, missing
            pattern_diagnostics).

    Pitfall 9 two-pass selection:
      Pass 1: filter to {qullamaggie_continuation, minervini_vcp} -> top-N
      Pass 2: filter to leader_hold -> separate section (no top-N cap)
      Picks with playbook_tag == "none" are dropped entirely.
    """
    settings = get_settings()
    warn_thresh = settings.TREND_TEMPLATE_PASS_RATE_WARN

    # Pitfall 9: two-pass selection. When playbook_tag column is absent (legacy
    # callers from Phase 4 tests), fall back to using the full frame for top-N.
    if "playbook_tag" in scored_cross.columns:
        actionable_mask = scored_cross["playbook_tag"].isin(
            ["qullamaggie_continuation", "minervini_vcp"]
        )
        leader_mask = scored_cross["playbook_tag"] == "leader_hold"
        actionable = (
            scored_cross[actionable_mask]
            .sort_values("composite_score", ascending=False)
            .head(top_n)
        )
        leaders = (
            scored_cross[leader_mask]
            .sort_values("composite_score", ascending=False)
        )
    else:
        # Legacy fallback: no playbook_tag column (Phase 4 test callers).
        actionable = scored_cross.sort_values("composite_score", ascending=False).head(top_n)
        leaders = pd.DataFrame()

    top = actionable  # alias for table rendering

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

    # --- Per-pick detail blocks (D-04 / D-19) ----
    lines.append("## Per-Pick Detail")
    lines.append("")
    for i, (_, row) in enumerate(top.iterrows(), start=1):
        _render_per_pick_block(i, row, lines)

    lines.append("---")
    lines.append("")

    # --- Currently Held / Leaders section (D-15; Pitfall 9) ----
    if not leaders.empty:
        lines.append("## Currently Held / Leaders")
        lines.append("")
        lines.append(
            "Existing positions to monitor (not new entries; informational only)."
        )
        lines.append("")
        for i, (_, lrow) in enumerate(leaders.iterrows(), start=1):
            _render_per_pick_block(i, lrow, lines)
        lines.append("---")
        lines.append("")

    # --- Phase 7 Skipped Picks section (CONTEXT D-06 / Pitfall 6) ----
    if skipped_picks is not None and len(skipped_picks) > 0:
        lines.append("## Skipped Picks")
        lines.append("")
        lines.append(
            "Picks excluded by the SIZ-02 1xADR auto-reject (or Pitfall 6 "
            "invalid stop / Pitfall 5 missing diagnostics). Excluded from "
            "both the report top-N AND the journal."
        )
        lines.append("")
        for ticker, srow in skipped_picks.iterrows():
            ticker_str = str(ticker) if not isinstance(ticker, str) else ticker
            reason = str(srow.get("rejection_reason", ""))
            risk = (
                float(srow.get("risk_per_share", 0.0))
                if pd.notna(srow.get("risk_per_share"))
                else 0.0
            )
            adr_pct = (
                float(srow.get("adr_pct", 0.0))
                if pd.notna(srow.get("adr_pct"))
                else 0.0
            )
            entry = float(srow.get("entry_price", srow.get("close", 0.0)))
            adr_dollars = (adr_pct / 100.0) * entry if entry > 0 else 0.0
            multiple = (risk / adr_dollars) if adr_dollars > 0 else 0.0
            if reason == "adr_exceeded":
                lines.append(
                    f"- **{ticker_str}** -- skipped: R/R broken, risk = {multiple:.2f}xADR"
                )
            elif reason == "invalid_stop":
                lines.append(
                    f"- **{ticker_str}** -- skipped: invalid stop (entry <= stop_price)"
                )
            elif reason == "missing_diagnostics":
                lines.append(
                    f"- **{ticker_str}** -- skipped: missing pattern diagnostics"
                )
            else:
                lines.append(f"- **{ticker_str}** -- skipped: {reason}")
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
    skipped_picks: pd.DataFrame | None = None,
) -> Path:
    """Render + atomically write the Markdown report to reports/<date>.md.

    Args:
        skipped_picks: Phase 7 kwarg (default None, backwards-compat). When
            non-empty, passes through to render_report for the ## Skipped Picks
            section (D-06 rejection surface — SIZ-02 1xADR auto-reject).
    """
    content = render_report(
        scored_cross, regime_row, snapshot_date, top_n, pass_rate,
        skipped_picks=skipped_picks,
    )
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
