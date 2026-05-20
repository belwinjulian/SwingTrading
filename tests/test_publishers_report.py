"""OUT-01 + OUT-02 — Markdown report writer behavior tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _make_scored_cross(n: int = 3) -> pd.DataFrame:
    """Build a tiny cross-section frame with all the columns render_report
    consumes."""
    return pd.DataFrame(
        {
            "ticker": [f"T{i:03d}" for i in range(n)],
            "rank": pd.array(list(range(1, n + 1)), dtype=pd.Int64Dtype()),
            "composite_score": [50.0 - i for i in range(n)],
            "rs_component": [0.9] * n,
            "trend_component": [1.0] * n,
            "volume_component": [0.7] * n,
            "pattern_component": [0.0] * n,
            "earnings_component": [0.0] * n,
            "catalyst_component": [0.0] * n,
            "passes_trend_template": [True] * n,
            "trend_template_score": pd.array([8] * n, dtype=pd.Int64Dtype()),
            "rs_rating": pd.array([90 + i for i in range(n)], dtype=pd.Int64Dtype()),
            "dryup_ratio": [0.5] * n,
            "pivot_distance_atr": [0.42, 1.5, float("nan")][:n],
            "pivot_zone": ["in-zone", "chase, skip", "unknown"][:n],
            "regime_state": ["Confirmed Uptrend"] * n,
            "regime_score": [0.82] * n,
            "close": [100.0 + i for i in range(n)],
            "high_52w": [105.0 + i for i in range(n)],
            "atr_14": [2.0] * n,
        }
    )


def _make_regime_row() -> pd.Series:
    return pd.Series(
        {
            "regime_state": "Confirmed Uptrend",
            "regime_score": 0.82,
            "spy_above_200d": True,
            "breadth_pct": 67.0,
            "distribution_days": 2,
            "vix_level": 16.4,
        }
    )


def test_report_file_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OUT-01: write_report produces reports/<date>.md."""
    monkeypatch.setattr(
        "screener.publishers.report._report_dir", lambda: tmp_path
    )
    from screener.publishers.report import write_report

    path = write_report(
        _make_scored_cross(3),
        _make_regime_row(),
        "2026-05-10",
        top_n=15,
        pass_rate=0.10,
    )
    assert path == tmp_path / "2026-05-10.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert content  # non-empty


def test_report_sections_present() -> None:
    """OUT-01: report contains all required sections."""
    from screener.publishers.report import render_report

    md = render_report(
        _make_scored_cross(3),
        _make_regime_row(),
        "2026-05-10",
        top_n=15,
        pass_rate=0.10,
    )
    assert "# Daily Picks — 2026-05-10" in md
    assert "## Regime" in md
    assert "## Top 15 Picks" in md
    assert "## Per-Pick Detail" in md
    assert "## Data Quality" in md


def test_per_pick_breakdown_format_d04() -> None:
    """OUT-02 + D-04 (Phase 6 update): breakdown line renders live Phase-4 components.

    Phase 4: PHASE_4_ZEROED contained pattern/earnings/catalyst; the breakdown
    code block rendered them as '--(Phase 6)' placeholders.
    Phase 6 D-16: PHASE_4_ZEROED == frozenset(); those placeholder entries are
    dropped from the breakdown code block. The full D-19 format (with pattern/
    earnings/catalyst values) is wired in Plan 05.

    Note: The report still contains '(Phase 6)' in hardcoded narrative strings
    (playbook/catalysts stubs, footer note, pivot proxy note) — those are Plan 05
    responsibilities and are intentionally left for now.
    """
    from screener.publishers.report import render_report

    md = render_report(
        _make_scored_cross(3),
        _make_regime_row(),
        "2026-05-10",
        top_n=15,
        pass_rate=0.10,
    )
    # Live Phase-4 components always present:
    assert "RS=" in md
    assert "Trend=" in md and "/8" in md
    assert "Volume=" in md
    # Phase 6 D-16: PHASE_4_ZEROED is empty so no 'Pattern=--(Phase 6)' in breakdown.
    # The _format_breakdown function skips keys not in the live elif branches.
    assert "Pattern=--(Phase 6)" not in md, (
        "Expected no 'Pattern=--(Phase 6)' in breakdown after D-16 activation"
    )
    assert "Earnings=--(Phase 6)" not in md, (
        "Expected no 'Earnings=--(Phase 6)' in breakdown after D-16 activation"
    )
    assert "Catalyst=--(Phase 6)" not in md, (
        "Expected no 'Catalyst=--(Phase 6)' in breakdown after D-16 activation"
    )


def test_pivot_zone_labels() -> None:
    """OUT-02 + Pitfall 5 + REVIEW CR-05: pivot_zone shows in-zone /
    chase, skip / unknown.

    Sign convention is (high_52w - close)/atr: positive when close is BELOW
    high_52w. 'in-zone' requires 0.0 <= distance <= 1.0 (close within 1 ATR
    *below* the 52w high). Breakouts (close > high_52w -> negative distance)
    and laggards (distance > 1 ATR) both classify as 'chase, skip'.
    """
    from screener.publishers.report import _classify_pivot_zone, render_report

    # Direct helper test:
    # close=98.5, high_52w=100.0, atr=2.0 -> distance = 0.75 ATR below -> in-zone
    assert _classify_pivot_zone(98.5, 100.0, 2.0) == "in-zone"
    # close=80.0, high_52w=100.0, atr=2.0 -> distance = 10 ATR below -> chase, skip
    assert _classify_pivot_zone(80.0, 100.0, 2.0) == "chase, skip"
    # close=120.0, high_52w=100.0, atr=2.0 -> distance = -10 (above high) -> chase, skip
    assert _classify_pivot_zone(120.0, 100.0, 2.0) == "chase, skip"
    assert _classify_pivot_zone(100.0, float("nan"), 2.0) == "unknown"
    assert _classify_pivot_zone(100.0, 99.0, float("nan")) == "unknown"
    assert _classify_pivot_zone(100.0, 99.0, 0.0) == "unknown"  # divide-by-zero

    # Rendered report shows all three labels (cross has one of each):
    md = render_report(
        _make_scored_cross(3),
        _make_regime_row(),
        "2026-05-10",
        top_n=15,
        pass_rate=0.10,
    )
    assert "in-zone" in md
    assert "chase, skip" in md
    assert "unknown" in md


def test_data_quality_warning_banner_d07(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-07: pass_rate > warn_threshold renders 'WARNING:' banner (no emoji)."""
    from screener.publishers.report import render_report

    md_warn = render_report(
        _make_scored_cross(3), _make_regime_row(), "2026-05-10",
        top_n=15, pass_rate=0.31,
    )
    assert "WARNING:" in md_warn
    assert "31.0%" in md_warn
    # Pitfall 12: no emoji unicode.
    assert "⚠" not in md_warn
    assert "\U0001f6a8" not in md_warn

    md_clean = render_report(
        _make_scored_cross(3), _make_regime_row(), "2026-05-10",
        top_n=15, pass_rate=0.10,
    )
    assert "WARNING:" not in md_clean


def test_pivot_column_header_d05() -> None:
    """D-05: column header reads 'ATR from 52w high (Phase 4 proxy)' verbatim."""
    from screener.publishers.report import PIVOT_COLUMN_HEADER, render_report

    assert PIVOT_COLUMN_HEADER == "ATR from 52w high (Phase 4 proxy)"
    md = render_report(
        _make_scored_cross(3), _make_regime_row(), "2026-05-10",
        top_n=15, pass_rate=0.10,
    )
    assert PIVOT_COLUMN_HEADER in md


def test_report_atomic_write_crash_no_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Markdown write is atomic: a crash mid-write leaves no .tmp residue."""
    monkeypatch.setattr(
        "screener.publishers.report._report_dir", lambda: tmp_path
    )

    # Force os.replace to raise mid-write.
    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("simulated crash")

    from screener.publishers.report import write_report

    monkeypatch.setattr("screener.publishers.report.os.replace", _raise)
    with pytest.raises(OSError):
        write_report(
            _make_scored_cross(3), _make_regime_row(), "2026-05-10",
            top_n=15, pass_rate=0.10,
        )

    target = tmp_path / "2026-05-10.md"
    assert not target.exists()
    leftover = list(tmp_path.glob(".2026-05-10.md.*.tmp"))
    assert leftover == [], f"No tmp residue should remain; found {leftover}"


def test_render_report_includes_sizing_fields_and_skipped_section() -> None:
    """Plan 07-04: render_report emits Entry/Stop/Trail/Shares/Zone per pick AND
    ## Skipped Picks section when skipped_picks is non-empty."""
    import pandas as pd

    from screener.publishers.report import render_report

    actionable = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "composite_score": [85.0], "rs_rating": [92], "trend_template_score": [8],
            "volume_component": [0.7],
            "pivot_distance_atr": [0.5], "pivot_zone": ["in-zone"],
            "playbook_tag": ["minervini_vcp"],
            "pattern_diagnostics": ['{"type":"vcp","pivot_price":175.5,"final_contraction_depth":0.08}'],
            "qullamaggie_score": [0], "minervini_score": [1], "leader_hold_score": [0],
            "breakout_strength": [0.85],
            "days_to_next_earnings": [pd.NA], "crossed_52w_high_within_60d": [False],
            "insider_cluster_buy": [False], "earnings_in_3d_warn": [False],
            "eps_knowable_from": [None], "rank": pd.array([1], dtype=pd.Int64Dtype()),
            "regime_state": ["Confirmed Uptrend"], "regime_score": [0.82],
            # Phase 7 sizing cols populated by Plan 07-04 step 5.5.
            "stop_price": [161.46],   # 175.5 * (1 - 0.08)
            "entry_price": [180.0],
            "shares": pd.array([50], dtype=pd.Int64Dtype()),
            "risk_per_share": [18.54],
            "atr_zone": ["in-zone"],
            "pivot_distance_atr_breakout": [0.25],
            "trail_rule_label": ["21d EMA (then 50d SMA after 15 bars)"],
            "adr_rejected": [False], "rejection_reason": [""],
        }
    )
    skipped = pd.DataFrame(
        {
            "rejection_reason": ["adr_exceeded"],
            "risk_per_share": [1.4], "adr_pct": [1.0], "entry_price": [100.0],
            "close": [100.0],
        },
        index=pd.Index(["BADTICK"], name="ticker"),
    )
    regime_row = pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82})

    md = render_report(
        actionable, regime_row, snapshot_date="2026-05-18",
        top_n=15, pass_rate=0.10, skipped_picks=skipped,
    )

    # Sizing per-pick fields present.
    assert "**Entry:** $180.00" in md
    assert "**Stop:** $161.46" in md
    assert "**Trail:** 21d EMA" in md
    assert "**Shares:** 50" in md
    assert "**Zone:** in-zone" in md
    # ## Skipped Picks section rendered.
    assert "## Skipped Picks" in md
    assert "BADTICK" in md
    assert "R/R broken" in md
