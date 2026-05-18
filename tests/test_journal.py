"""tests/test_journal.py — Phase 7 OUT-04..06 SQLite + trigger tests (Plan 07-03 bodies)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pandera as pa
import pytest

from screener import persistence
from screener.persistence import (
    PicksSchema,
    _ensure_picks_schema,
    append_picks_rows,
    read_picks_for_date,
)


def _make_row(
    ticker: str = "AAPL",
    snapshot_date: str = "2026-05-18",
    playbook_tag: str = "minervini_vcp",
    composite_score: float = 75.0,
    regime_state: str = "Confirmed Uptrend",
    entry_price: float = 180.0,
    stop_price: float = 175.0,
    shares: int = 50,
    risk_per_share: float = 5.0,
    atr_zone: str = "in-zone",
    pivot_distance_atr_breakout: float = 0.41,
    features_json: str | None = None,
    ingested_at: str = "2026-05-18T22:30:00Z",
) -> dict:
    """Factory for a complete picks row dict (13 decision cols + ingested_at)."""
    if features_json is None:
        features_json = json.dumps({
            "rs_rating": 92, "trend_template_score": 8,
            "pattern_diagnostics": {
                "type": "vcp", "n_contractions": 3,
                "depth_sequence": [0.25, 0.15, 0.08],
                "first_leg_depth": 0.25, "final_contraction_depth": 0.08,
                "breakout_vol_multiple": 1.7, "breakout_strength": 0.85,
                "pivot_price": 175.5, "days_in_consolidation": 18,
            },
            "features_json_version": "v1.0",
        })
    return {
        "ticker": ticker, "snapshot_date": snapshot_date,
        "playbook_tag": playbook_tag, "composite_score": composite_score,
        "regime_state": regime_state, "entry_price": entry_price,
        "stop_price": stop_price, "shares": shares,
        "risk_per_share": risk_per_share, "atr_zone": atr_zone,
        "pivot_distance_atr_breakout": pivot_distance_atr_breakout,
        "features_json": features_json, "ingested_at": ingested_at,
    }


def test_immutability_trigger(tmp_path: Path) -> None:
    """OUT-05: UPDATE on a decision column raises sqlite3.IntegrityError with 'decision column immutable'."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            conn.execute("UPDATE picks SET ticker = 'MSFT' WHERE id = 1")
        assert "decision column immutable" in str(excinfo.value)
        # Spot-check 3 more decision cols.
        for col in ("composite_score", "stop_price", "features_json"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(f"UPDATE picks SET {col} = ? WHERE id = 1", ("X",))


def test_outcome_col_not_in_trigger(tmp_path: Path) -> None:
    """OUT-06: UPDATE on exit_price does NOT fire the trigger."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        # No exception expected.
        conn.execute("UPDATE picks SET exit_price = ? WHERE id = 1", (185.50,))
        conn.commit()
        val = conn.execute("SELECT exit_price FROM picks WHERE id = 1").fetchone()[0]
        assert val == 185.50


def test_outcome_column_updatable(tmp_path: Path) -> None:
    """OUT-06: all 6 outcome cols are nullable and updatable."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    updates = {
        "entry_filled": 1, "exit_price": 200.0, "exit_date": "2026-06-01",
        "hold_days": 14, "mfe": 25.5, "mae": -3.2,
    }
    with sqlite3.connect(db) as conn:
        # Initial NULL state.
        for col in updates:
            v = conn.execute(f"SELECT {col} FROM picks WHERE id = 1").fetchone()[0]
            assert v is None, f"{col} should start NULL"
        # All six updates succeed.
        for col, val in updates.items():
            conn.execute(f"UPDATE picks SET {col} = ? WHERE id = 1", (val,))
        conn.commit()
        for col, val in updates.items():
            v = conn.execute(f"SELECT {col} FROM picks WHERE id = 1").fetchone()[0]
            assert v == val, f"{col}: {v!r} != {val!r}"


def test_idempotent_append(tmp_path: Path) -> None:
    """OUT-04: INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) — mixed batch."""
    db = tmp_path / "j.sqlite"
    # First insert: 2 rows.
    n1 = append_picks_rows(
        [_make_row(ticker="AAPL"), _make_row(ticker="MSFT")], db_path=db,
    )
    assert n1 == 2
    # Second insert: 1 duplicate (AAPL), 1 new (NVDA), 1 duplicate (AAPL again).
    n2 = append_picks_rows(
        [_make_row(ticker="AAPL"), _make_row(ticker="NVDA"), _make_row(ticker="AAPL")],
        db_path=db,
    )
    assert n2 == 1, f"Expected 1 NVDA insert; got {n2}"
    # Total row count == 3 (AAPL + MSFT + NVDA).
    with sqlite3.connect(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        assert total == 3
    # Empty-batch early-return path.
    assert append_picks_rows([], db_path=db) == 0


def test_features_json_roundtrip(tmp_path: Path) -> None:
    """OUT-05: features_json column round-trips cleanly via json.loads."""
    db = tmp_path / "j.sqlite"
    expected = {"rs_rating": 92, "composite_score": 75.0, "extra": {"k": [1, 2, 3]}}
    append_picks_rows([_make_row(features_json=json.dumps(expected))], db_path=db)
    df = read_picks_for_date("2026-05-18", db_path=db)
    assert len(df) == 1
    loaded = json.loads(df.iloc[0]["features_json"])
    assert loaded == expected


def test_features_json_includes_diagnostics(tmp_path: Path) -> None:
    """OUT-05 / D-03: features_json embeds full pattern_diagnostics dict (Phase 6 D-05 keys)."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)  # _make_row default includes diagnostics
    df = read_picks_for_date("2026-05-18", db_path=db)
    loaded = json.loads(df.iloc[0]["features_json"])
    diag = loaded["pattern_diagnostics"]
    for required_key in (
        "type", "n_contractions", "depth_sequence", "first_leg_depth",
        "final_contraction_depth", "breakout_vol_multiple", "breakout_strength",
        "pivot_price", "days_in_consolidation",
    ):
        assert required_key in diag, f"pattern_diagnostics missing {required_key}"


def test_schema_idempotent_recreates_trigger(tmp_path: Path) -> None:
    """RESEARCH Pitfall 1: DROP TABLE picks + re-call _ensure_picks_schema → trigger STILL fires."""
    db = tmp_path / "j.sqlite"
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        conn.executescript("DROP TABLE picks;")  # cascades the trigger
    _ensure_picks_schema(db)  # re-create
    append_picks_rows([_make_row()], db_path=db)
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            conn.execute("UPDATE picks SET ticker = 'X' WHERE id = 1")
        assert "decision column immutable" in str(excinfo.value)


def test_picks_schema_rejects_invalid_playbook_tag() -> None:
    """PicksSchema isin enum rejects 'none' or any tag not in the locked set."""
    bad = pd.DataFrame([_make_row(playbook_tag="none")])
    # Drop schema-irrelevant cols if _make_row adds any in future; today the
    # dict keys are exactly the PicksSchema fields.
    with pytest.raises(pa.errors.SchemaError):
        PicksSchema.validate(bad, lazy=False)
    bad2 = pd.DataFrame([_make_row(playbook_tag="day_trade")])
    with pytest.raises(pa.errors.SchemaError):
        PicksSchema.validate(bad2, lazy=False)


def test_picks_schema_rejects_invalid_atr_zone() -> None:
    """PicksSchema isin enum rejects atr_zone not in {in-zone, extended, chase, skip}."""
    bad = pd.DataFrame([_make_row(atr_zone="chase-skip")])  # missing space + comma
    with pytest.raises(pa.errors.SchemaError):
        PicksSchema.validate(bad, lazy=False)


def test_journal_cli_idempotent() -> None:
    """OUT-04: invoke `screener journal` twice → second invocation inserts 0 rows (filled by Plan 07-05)."""
    pytest.skip("Plan 07-05")
