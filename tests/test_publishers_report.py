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
    """OUT-02 + D-04: per-pick block contains 6-component breakdown
    with '---(Phase 6)' placeholders for PHASE_4_ZEROED keys."""
    from screener.publishers.report import render_report

    md = render_report(
        _make_scored_cross(3),
        _make_regime_row(),
        "2026-05-10",
        top_n=15,
        pass_rate=0.10,
    )
    # Live components show real values:
    assert "RS=" in md
    assert "Trend=" in md and "/8" in md
    assert "Volume=" in md
    # Zeroed components show placeholder:
    assert "Pattern=" in md and "(Phase 6)" in md
    assert "Earnings=" in md and "(Phase 6)" in md
    assert "Catalyst=" in md and "(Phase 6)" in md
    # Playbook + catalysts placeholder lines from the per-pick block:
    assert "**Playbook:** " in md and "(Phase 6)" in md
    assert "**Catalysts:** " in md and "(Phase 6)" in md


def test_pivot_zone_labels() -> None:
    """OUT-02 + Pitfall 5: pivot_zone shows in-zone / chase, skip / unknown."""
    from screener.publishers.report import _classify_pivot_zone, render_report

    # Direct helper test:
    assert _classify_pivot_zone(100.0, 99.0, 2.0) == "in-zone"  # 0.5 ATR -> in-zone
    assert _classify_pivot_zone(120.0, 100.0, 2.0) == "chase, skip"  # 10 ATR
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
    import os as _os

    original_replace = _os.replace

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
