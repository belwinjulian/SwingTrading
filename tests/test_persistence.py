"""Persistence schema + atomic-write tests (DAT-09, DAT-08, DAT-03).

Covers the 9 tests in 02-VALIDATION.md lines 52-59. Uses synthetic fixtures
from tests/conftest.py — no network, no live yfinance / iShares calls.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa
import pytest

from screener.persistence import (
    OhlcvPanelSchema,
    SplitsSchema,
    UniverseSchema,
    _write_parquet_atomic,
    make_empty_splits,
    read_panel,
    read_splits,
    validate_at_read,
    validate_at_write,
    write_ohlcv_atomic,
    write_splits_atomic,
    write_universe_atomic,
)

# --- Helpers ----------------------------------------------------------------


def _make_panel(close_vals: list[float], open_vals: list[float] | None = None) -> pd.DataFrame:
    n = len(close_vals)
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=n)],
        names=["ticker", "date"],
    )
    return pd.DataFrame(
        {
            "open": open_vals if open_vals is not None else [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": close_vals,
            "volume": [1_000_000] * n,
        },
        index=idx,
    )


def _make_ranking_snapshot_df() -> pd.DataFrame:
    """Minimal valid frame for RankingSnapshotSchema.

    Phase 6 (Plan 06-01): includes the 11 new RankingSnapshotSchema columns
    with safe placeholder defaults (playbook_tag='none', binary scores=0,
    pattern_diagnostics='{"type": "none"}', breakout_strength=0.0, catalyst
    flags=False). Plans 06-02/06-03/06-04 populate them with real values
    via the production code path (`_add_publisher_columns`).
    """
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


def _make_universe_row(sector: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAA"],
            "ticker_raw": ["AAA"],
            "name": ["Alpha Corp"],
            "sector": [sector],
            "weight_pct": [0.5],
        }
    )


# --- DAT-09: schema rejection tests -----------------------------------------


def test_panel_schema_rejects_null_close() -> None:
    bad = _make_panel(close_vals=[100.0, np.nan, 100.0])
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(OhlcvPanelSchema, bad)


def test_panel_schema_rejects_negative_price() -> None:
    bad = _make_panel(close_vals=[100.0, 100.0, 100.0], open_vals=[-1.0, 100.0, 100.0])
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(OhlcvPanelSchema, bad)


def test_panel_schema_rejects_wrong_index_order() -> None:
    """MultiIndex declared as (date, ticker) instead of (ticker, date) must fail."""
    n = 3
    idx = pd.MultiIndex.from_product(
        [pd.bdate_range(end="2026-04-30", periods=n), ["AAA"]],
        names=["date", "ticker"],  # WRONG order
    )
    bad = pd.DataFrame(
        {
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [1_000_000] * n,
        },
        index=idx,
    )
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(OhlcvPanelSchema, bad)


def test_universe_schema_rejects_unknown_sector() -> None:
    bad = _make_universe_row(sector="Bogus Sector")
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(UniverseSchema, bad)


def test_splits_schema_rejects_negative() -> None:
    bad = pd.DataFrame(
        {"ratio": [-1.0], "dividend": [0.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-06-10")], name="date"),
    )
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(SplitsSchema, bad)


def test_lazy_collects_multiple_errors() -> None:
    """validate_at_read with lazy=True collects multiple errors at once."""
    bad = _make_panel(
        close_vals=[100.0, np.nan, 100.0],
        open_vals=[-1.0, 100.0, 100.0],
    )
    with pytest.raises(pa.errors.SchemaErrors) as exc_info:
        validate_at_read(OhlcvPanelSchema, bad)
    # SchemaErrors aggregates >= 2 failures (open<0 and null-close).
    assert len(exc_info.value.failure_cases) >= 2, (
        f"Expected >= 2 failure cases for the 'null close + negative open' panel; "
        f"got {len(exc_info.value.failure_cases)}: {exc_info.value.failure_cases!r}"
    )


# --- DAT-03 / D-11: atomic-write crash safety -------------------------------


def test_atomic_write_crash_no_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "x.parquet"
    df = pd.DataFrame({"a": [1, 2, 3]})

    def _raise(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise)
    with pytest.raises(OSError):
        _write_parquet_atomic(df, target)
    assert not target.exists(), "target Parquet must not exist after a mid-write crash"
    leftover = list(tmp_path.glob(".x.parquet.*.tmp"))
    assert leftover == [], f"No tmp residue should remain; found {leftover}"


def test_write_parquet_atomic_auto_creates_new_dirs(tmp_path: Path) -> None:
    """Pitfall 10: target.parent.mkdir(parents=True, exist_ok=True) covers
    data/macro/ and data/rs_snapshots/ on first run."""
    nested = tmp_path / "macro" / "deep" / "tree" / "spy.parquet"
    df = pd.DataFrame({"a": [1, 2, 3]})
    _write_parquet_atomic(df, nested)
    assert nested.exists()


# --- DAT-08: empty splits round-trip ----------------------------------------


def test_empty_splits_schema_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: tmp_path)
    empty = make_empty_splits()
    write_splits_atomic("AAPL", empty)
    roundtrip = read_splits("AAPL")
    assert len(roundtrip) == 0
    assert list(roundtrip.columns) == ["ratio", "dividend"]
    assert roundtrip.index.name == "date"


def test_read_panel_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ohlcv_dir = tmp_path / "ohlcv"
    universe_dir = tmp_path / "universe"
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: ohlcv_dir)
    monkeypatch.setattr("screener.persistence._universe_dir", lambda: universe_dir)
    universe = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "ticker_raw": ["AAA", "BBB"],
            "name": ["Alpha Corp", "Beta Corp"],
            "sector": ["Information Technology", "Energy"],
            "weight_pct": [0.5, 0.6],
        }
    )
    write_universe_atomic(universe, "2026-04-27")
    idx = pd.bdate_range(end="2026-04-30", periods=10)
    for t in ("AAA", "BBB"):
        ohlcv = pd.DataFrame(
            {
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5] * 10,
                "volume": [1_000_000] * 10,
            },
            index=idx,
        )
        write_ohlcv_atomic(t, ohlcv)
    panel = read_panel("2026-04-27")
    assert panel.index.names == ["ticker", "date"]
    assert sorted(panel.index.get_level_values("ticker").unique().tolist()) == ["AAA", "BBB"]
    assert len(panel) == 20


# --- Phase 4 Wave 0: RankingSnapshotSchema + _assert_safe_snapshot_date -------


def test_ranking_snapshot_schema_accepts_valid_frame() -> None:
    from screener.persistence import RankingSnapshotSchema, validate_at_write
    df = _make_ranking_snapshot_df()
    validated = validate_at_write(RankingSnapshotSchema, df)
    assert len(validated) == 2


def test_ranking_snapshot_rejects_bad_pivot_zone() -> None:
    from screener.persistence import RankingSnapshotSchema, validate_at_write
    df = _make_ranking_snapshot_df()
    df["pivot_zone"] = ["BOGUS", "BOGUS"]
    with pytest.raises(pa.errors.SchemaError):
        validate_at_write(RankingSnapshotSchema, df)


def test_assert_safe_snapshot_date_rejects_traversal() -> None:
    from screener.persistence import _assert_safe_snapshot_date
    _assert_safe_snapshot_date("2026-05-10")  # silent pass
    with pytest.raises(ValueError, match="Unsafe snapshot_date"):
        _assert_safe_snapshot_date("../etc/passwd")
    with pytest.raises(ValueError, match="Unsafe snapshot_date"):
        _assert_safe_snapshot_date("2026-5-10")  # not zero-padded
