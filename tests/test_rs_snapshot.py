"""RS snapshot + macro persistence tests (D-10, D-11, D-15, D-16; RESEARCH Pitfalls 9, 10).

Wave 0 covers the persistence-layer schema seam additions for Phase 3:
- write_rs_snapshot_atomic / read_rs_snapshot
- write_macro_atomic / read_macro_*
- atomic-write crash safety
- schema dtype enforcement (Int64 nullable; ticker regex)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.errors
import pytest

from screener.persistence import (
    _macro_dir,
    _rs_snapshot_dir,
    read_macro_spy,
    read_rs_snapshot,
    write_macro_atomic,
    write_rs_snapshot_atomic,
)


def _make_rs_snapshot_df(n_tickers: int = 5) -> pd.DataFrame:
    """Build an RsSnapshotSchema-shaped df: rs_rating MUST be Int64 nullable."""
    tickers = [f"AAA{i}" if i > 0 else "AAA" for i in range(n_tickers)]
    rs_raw = [1.5 + i * 0.1 for i in range(n_tickers)]
    rs_rating = pd.array([90 - i * 10 for i in range(n_tickers)], dtype="Int64")
    return pd.DataFrame({"ticker": tickers, "rs_raw": rs_raw, "rs_rating": rs_rating})


def test_rs_snapshot_atomic_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mid-write crash leaves no partial Parquet and no .tmp residue."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    df = _make_rs_snapshot_df()

    def _raise(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise)
    with pytest.raises(OSError):
        write_rs_snapshot_atomic(df, "2026-04-30")

    target = snapshot_dir / "2026-04-30.parquet"
    assert not target.exists(), "rs snapshot must not exist after a mid-write crash"
    leftover = list(snapshot_dir.glob(".2026-04-30.parquet.*.tmp"))
    assert leftover == [], f"No tmp residue should remain; found {leftover}"


def test_rs_snapshot_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write + read recovers exactly the same RS snapshot frame."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    df = _make_rs_snapshot_df()
    target = write_rs_snapshot_atomic(df, "2026-04-30")
    assert target.exists()

    loaded = read_rs_snapshot("2026-04-30")
    assert list(loaded.columns) == ["ticker", "rs_raw", "rs_rating"]
    assert len(loaded) == len(df)
    assert loaded["rs_rating"].dtype == pd.Int64Dtype()


def test_rs_snapshot_schema_rejects_bad_rating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pitfall 9: rs_rating must be pd.Int64Dtype (nullable Int64), NOT int64."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    bad = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "rs_raw": [1.0],
            "rs_rating": pd.Series([50], dtype="int64"),  # NOT nullable Int64
        }
    )
    with pytest.raises(pandera.errors.SchemaError):
        write_rs_snapshot_atomic(bad, "2026-04-30")


def test_rs_snapshot_schema_rejects_lowercase_ticker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ticker must match ^[A-Z][A-Z0-9\\-]{0,9}$ — lowercase rejected."""
    snapshot_dir = tmp_path / "rs_snapshots"
    monkeypatch.setattr("screener.persistence._rs_snapshot_dir", lambda: snapshot_dir)

    bad = pd.DataFrame(
        {
            "ticker": ["aapl"],
            "rs_raw": [1.0],
            "rs_rating": pd.array([50], dtype="Int64"),
        }
    )
    with pytest.raises(pandera.errors.SchemaError):
        write_rs_snapshot_atomic(bad, "2026-04-30")


def test_write_macro_atomic_unknown_series_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown series name fails fast — typo guard."""
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: tmp_path / "macro")
    df = pd.DataFrame(
        {"close": [1.0]}, index=pd.DatetimeIndex(["2026-04-30"], name="date")
    )
    with pytest.raises(ValueError, match="unknown macro series"):
        write_macro_atomic(df, "junk")


def test_read_macro_spy_validates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Parquet missing the volume column fails MacroOhlcvSchema lazy validation.

    lazy=True in validate_at_read collects all errors and raises SchemaErrors
    (plural, not SchemaError singular) per pandera's lazy-mode contract.
    """
    macro_dir = tmp_path / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)

    bad_spy = pd.DataFrame(
        {
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
        },  # missing volume
        index=pd.DatetimeIndex(["2026-04-30"], name="date"),
    )
    target = macro_dir / "spy.parquet"
    bad_spy.to_parquet(target, engine="pyarrow", index=True)
    # lazy=True raises SchemaErrors (plural) not SchemaError (singular).
    with pytest.raises((pandera.errors.SchemaError, pandera.errors.SchemaErrors)):
        read_macro_spy()


def test_macro_dir_resolves_from_settings() -> None:
    """_macro_dir() returns the D-12 default path."""
    assert _macro_dir() == Path("data/macro")


def test_rs_snapshot_dir_resolves_from_settings() -> None:
    """_rs_snapshot_dir() returns the D-12 default path."""
    assert _rs_snapshot_dir() == Path("data/rs_snapshots")


def test_snapshot_atomic_write_crash_no_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mid-write crash leaves no partial Parquet and no .tmp residue
    — mirrors test_rs_snapshot_atomic_write for write_snapshot_atomic."""
    snapshot_dir = tmp_path / "snapshots"
    monkeypatch.setattr(
        "screener.persistence._snapshot_dir", lambda: snapshot_dir
    )

    from screener.persistence import write_snapshot_atomic

    # Build a minimal valid frame for RankingSnapshotSchema
    # (Phase 6 extension applied: Plan 06-01 added 11 new columns).
    df = pd.DataFrame(
        {
            "ticker": ["AAA"],
            "rank": pd.array([1], dtype=pd.Int64Dtype()),
            "composite_score": [50.0],
            "rs_component": [0.5],
            "trend_component": [0.5],
            "volume_component": [0.5],
            "pattern_component": [0.0],
            "earnings_component": [0.0],
            "catalyst_component": [0.0],
            "passes_trend_template": [True],
            "trend_template_score": pd.array([5], dtype=pd.Int64Dtype()),
            "rs_rating": pd.array([90], dtype=pd.Int64Dtype()),
            "dryup_ratio": [0.6],
            "pivot_distance_atr": [0.5],
            "pivot_zone": ["in-zone"],
            "regime_state": ["Confirmed Uptrend"],
            "regime_score": [0.8],
            # Phase 6 extension (Plan 06-01) — safe placeholders.
            "playbook_tag": ["none"],
            "qullamaggie_score": pd.array([0], dtype=pd.Int64Dtype()),
            "minervini_score": pd.array([0], dtype=pd.Int64Dtype()),
            "leader_hold_score": pd.array([0], dtype=pd.Int64Dtype()),
            "pattern_diagnostics": ['{"type": "none"}'],
            "breakout_strength": [0.0],
            "days_to_next_earnings": pd.array([pd.NA], dtype=pd.Int64Dtype()),
            "crossed_52w_high_within_60d": [False],
            "insider_cluster_buy": [False],
            "earnings_in_3d_warn": [False],
            "eps_knowable_from": pd.array([None], dtype=object),
        }
    )

    def _raise(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise)
    with pytest.raises(OSError):
        write_snapshot_atomic(df, "2026-05-10")

    target = snapshot_dir / "2026-05-10.parquet"
    assert not target.exists(), (
        "snapshot must not exist after a mid-write crash"
    )
    leftover = list(snapshot_dir.glob(".2026-05-10.parquet.*.tmp"))
    assert leftover == [], (
        f"No tmp residue should remain; found {leftover}"
    )
