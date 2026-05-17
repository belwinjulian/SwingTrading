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


# ---------------------------------------------------------------------------
# Phase 6 (Plan 06-05) — D-19 format + Pitfall 9 two-pass + leader_hold section
# ---------------------------------------------------------------------------


def _make_phase6_row(
    ticker: str = "AAPL",
    playbook_tag: str = "qullamaggie_continuation",
    composite_score: float = 75.0,
    earnings_in_3d_warn: bool = False,
    days_to_next_earnings: int | None = None,
    crossed_52w_high_within_60d: bool = False,
    insider_cluster_buy: bool = False,
) -> pd.Series:
    """Build a Phase 6 row with all D-19 columns populated."""
    return pd.Series(
        {
            "ticker": ticker,
            "rank": 1,
            "composite_score": composite_score,
            "rs_rating": 92,
            "trend_template_score": 8,
            "rs_component": 0.92,
            "trend_component": 1.0,
            "volume_component": 0.70,
            "pattern_component": 0.67,
            "earnings_component": 1.0,
            "catalyst_component": 0.33,
            "passes_trend_template": True,
            "dryup_ratio": 0.6,
            "pivot_distance_atr": 0.5,
            "pivot_zone": "in-zone",
            "regime_state": "Confirmed Uptrend",
            "regime_score": 0.82,
            "close": 175.5,
            "high_52w": 175.5,
            "atr_14": 3.2,
            "playbook_tag": playbook_tag,
            "qullamaggie_score": 1 if "qullamaggie" in playbook_tag else 0,
            "minervini_score": 1 if "minervini" in playbook_tag else 0,
            "leader_hold_score": 1 if playbook_tag == "leader_hold" else 0,
            "pattern_diagnostics": (
                '{"type":"vcp","n_contractions":4,"breakout_vol_multiple":2.1,'
                '"breakout_strength":0.73,"days_in_consolidation":24}'
            ),
            "breakout_strength": 0.73,
            "days_to_next_earnings": pd.NA if days_to_next_earnings is None else days_to_next_earnings,
            "crossed_52w_high_within_60d": crossed_52w_high_within_60d,
            "insider_cluster_buy": insider_cluster_buy,
            "earnings_in_3d_warn": earnings_in_3d_warn,
            "eps_knowable_from": "",
        }
    )


def _make_phase6_cross(rows: list[pd.Series]) -> pd.DataFrame:
    return pd.DataFrame(rows).reset_index(drop=True)


def test_d19_breakdown_format() -> None:
    """D-19: _format_breakdown renders D-19 per-pick format for a VCP pick."""
    import re
    from screener.publishers.report import _format_breakdown

    row = _make_phase6_row()
    result = _format_breakdown(row)
    # RS and Trend always present
    assert re.search(r"RS=\d+", result), f"Missing RS: {result!r}"
    assert re.search(r"Trend=\d+/8", result), f"Missing Trend: {result!r}"
    # Pattern renders VCP with contraction count and brk_vol
    assert re.search(r"Pattern=0\.67 \(VCP, 4 contractions, brk_vol=2\.1x\)", result), (
        f"Pattern D-19 format not found: {result!r}"
    )
    # Volume present
    assert re.search(r"Volume=[\d.]+", result), f"Missing Volume: {result!r}"
    # Earnings present
    assert re.search(r"Earnings=[01] \(EPS", result), f"Missing Earnings: {result!r}"
    # Catalyst present with flags count
    assert re.search(r"Catalyst=[\d.]+ \(\d/3 flags\)", result), (
        f"Catalyst D-19 format not found: {result!r}"
    )


def test_currently_held_section_separate() -> None:
    """D-15 + Pitfall 9: leader_hold picks go to 'Currently Held / Leaders'
    section, NOT the top-N table. leader_hold tickers must NOT appear in the
    top-N table even when their composite_score is higher than actionable picks.
    """
    from screener.publishers.report import render_report

    # 5 actionable picks (qullamaggie)
    actionable_rows = [
        _make_phase6_row(
            ticker=f"Q{i:02d}",
            playbook_tag="qullamaggie_continuation",
            composite_score=70.0 - i,
        )
        for i in range(5)
    ]
    # 3 leader_hold picks with composite_score ABOVE the actionable picks
    leader_rows = [
        _make_phase6_row(
            ticker=f"LH{i}",
            playbook_tag="leader_hold",
            composite_score=90.0 - i,  # higher than actionable
        )
        for i in range(3)
    ]
    cross = _make_phase6_cross(actionable_rows + leader_rows)
    regime = _make_regime_row()
    md = render_report(cross, regime, "2026-05-16", top_n=10, pass_rate=0.10)

    # "Currently Held / Leaders" section must be present
    assert "## Currently Held / Leaders" in md, (
        f"Expected 'Currently Held / Leaders' section in report: {md[:400]!r}"
    )
    # Leader tickers must appear ONLY in the leaders section, NOT the top-N table
    table_section = md.split("## Per-Pick Detail")[0]
    for lticker in ["LH0", "LH1", "LH2"]:
        assert lticker not in table_section, (
            f"Leader ticker {lticker!r} leaked into top-N table section"
        )
    # All actionable tickers must appear (they ARE in the top-N table)
    for qticker in ["Q00", "Q01", "Q02", "Q03", "Q04"]:
        assert qticker in md, f"Actionable ticker {qticker!r} missing from report"


def test_none_tag_excluded() -> None:
    """D-15 + Pitfall 9: picks with playbook_tag == 'none' must be excluded
    entirely from the report (not in top-N and not in leaders section).
    """
    from screener.publishers.report import render_report

    # One actionable pick + one none-tag pick
    rows = [
        _make_phase6_row(ticker="GOOD", playbook_tag="qullamaggie_continuation", composite_score=80.0),
        _make_phase6_row(ticker="NONE_PICK", playbook_tag="none", composite_score=95.0),  # high score but excluded
    ]
    cross = _make_phase6_cross(rows)
    md = render_report(cross, _make_regime_row(), "2026-05-16", top_n=10, pass_rate=0.10)

    assert "NONE_PICK" not in md, (
        f"Expected 'NONE_PICK' to be excluded from report, but found it in: {md[:400]!r}"
    )
    assert "GOOD" in md, "Expected actionable ticker 'GOOD' in report"


def test_earnings_in_3d_warn_renders() -> None:
    """D-11a: per-pick block shows 'WARNING: Earnings in Nd' when
    earnings_in_3d_warn=True.
    """
    from screener.publishers.report import render_report

    row = _make_phase6_row(
        ticker="WARN",
        playbook_tag="qullamaggie_continuation",
        earnings_in_3d_warn=True,
        days_to_next_earnings=2,
    )
    cross = _make_phase6_cross([row])
    md = render_report(cross, _make_regime_row(), "2026-05-16", top_n=10, pass_rate=0.10)

    assert "WARNING: Earnings in" in md, (
        f"Expected 'WARNING: Earnings in' in report; got: {md!r}"
    )
