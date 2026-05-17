"""OUT-03 — snapshot publisher behavior tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _make_ranking_snapshot_df() -> pd.DataFrame:
    """Minimal valid frame for RankingSnapshotSchema (mirrors test_persistence
    helper from Plan 04-01; extended for Phase 6 in Plan 06-01)."""
    return pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "rank": pd.array([1, 2], dtype=pd.Int64Dtype()),
            "composite_score": [48.7, 46.2],
            "rs_component": [0.95, 0.92],
            "trend_component": [1.0, 0.875],
            "volume_component": [0.91, 0.78],
            "pattern_component": [0.0, 0.0],
            "earnings_component": [0.0, 0.0],
            "catalyst_component": [0.0, 0.0],
            "passes_trend_template": [True, True],
            "trend_template_score": pd.array([8, 7], dtype=pd.Int64Dtype()),
            "rs_rating": pd.array([95, 92], dtype=pd.Int64Dtype()),
            "dryup_ratio": [0.7, 0.8],
            "pivot_distance_atr": [0.42, 0.71],
            "pivot_zone": ["in-zone", "in-zone"],
            "regime_state": ["Confirmed Uptrend", "Confirmed Uptrend"],
            "regime_score": [0.82, 0.82],
            # Phase 6 extension (Plan 06-01) — safe placeholders.
            "playbook_tag": ["none", "none"],
            "qullamaggie_score": pd.array([0, 0], dtype=pd.Int64Dtype()),
            "minervini_score": pd.array([0, 0], dtype=pd.Int64Dtype()),
            "leader_hold_score": pd.array([0, 0], dtype=pd.Int64Dtype()),
            "pattern_diagnostics": ['{"type": "none"}', '{"type": "none"}'],
            "breakout_strength": [0.0, 0.0],
            "days_to_next_earnings": pd.array([pd.NA, pd.NA], dtype=pd.Int64Dtype()),
            "crossed_52w_high_within_60d": [False, False],
            "insider_cluster_buy": [False, False],
            "earnings_in_3d_warn": [False, False],
            "eps_knowable_from": pd.array([None, None], dtype=object),
        }
    )


def test_snapshot_written_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OUT-03: write_snapshot writes data/snapshots/<date>.parquet via the
    publisher's thin-wrapper path."""
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setattr(
        "screener.persistence._snapshot_dir", lambda: snapshot_dir
    )
    from screener.publishers.snapshot import write_snapshot

    df = _make_ranking_snapshot_df()
    path = write_snapshot(df, "2026-05-10")
    assert path == snapshot_dir / "2026-05-10.parquet"
    assert path.exists()


def test_snapshot_path_traversal_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-4-01: snapshot_date with traversal attempt is rejected before write."""
    monkeypatch.setattr(
        "screener.persistence._snapshot_dir", lambda: tmp_path / "snapshots"
    )
    from screener.publishers.snapshot import write_snapshot

    df = _make_ranking_snapshot_df()
    with pytest.raises(ValueError, match="Unsafe snapshot_date"):
        write_snapshot(df, "../etc/passwd")


def test_52w_high_60d_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CAT-02: write_snapshot accepts crossed_52w_high_within_60d=True boolean
    without pandera schema error (Plan 06-05 wires this column from pipeline).
    """
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setattr(
        "screener.persistence._snapshot_dir", lambda: snapshot_dir
    )
    from screener.publishers.snapshot import write_snapshot

    df = _make_ranking_snapshot_df()
    # Override crossed_52w_high_within_60d to True for one row
    df = df.copy()
    df["crossed_52w_high_within_60d"] = [True, False]
    path = write_snapshot(df, "2026-05-16")
    assert path.exists()
    import pandas as pd
    written = pd.read_parquet(path)
    assert written["crossed_52w_high_within_60d"].iloc[0] is True or \
        bool(written["crossed_52w_high_within_60d"].iloc[0]) is True
