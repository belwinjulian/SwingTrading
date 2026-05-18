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


def test_journal_cli_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OUT-04: invoke `screener journal` twice → second invocation inserts 0 rows."""
    import json as _json
    from datetime import date

    from typer.testing import CliRunner

    # 1. Configure tmp paths for journal DB + snapshots dir.
    db_path = tmp_path / "journal.sqlite"
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JOURNAL_DB_PATH", str(db_path))
    monkeypatch.setenv("SNAPSHOT_DIR", str(snap_dir))
    monkeypatch.setenv("JOURNAL_THRESHOLD", "50.0")
    monkeypatch.setenv("RISK_PCT", "0.01")
    monkeypatch.setenv("ACCOUNT_EQUITY", "100000")
    from screener.config import get_settings
    get_settings.cache_clear()

    # 2. Write a real snapshot parquet that _build_journal_rows_df_from_snapshot
    # can read. Mirror the RankingSnapshotSchema-projected shape (only columns
    # that exist in the schema + the new Phase 7 sizing cols).
    today_iso = date.today().isoformat()
    snap_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "rank": 1,
                "composite_score": 75.0,
                "composite_score_raw": 75.0,  # pre-gate raw composite (Plan 07-04 Pitfall 3)
                "rs_component": 0.92, "trend_component": 1.0,
                "volume_component": 0.7, "pattern_component": 0.7,
                "earnings_component": 0.5, "catalyst_component": 0.3,
                "passes_trend_template": True, "trend_template_score": 8,
                "rs_rating": 92, "dryup_ratio": 0.85,
                "pivot_distance_atr": 0.5,  # Phase 4 sign convention
                "pivot_zone": "in-zone",
                "regime_state": "Confirmed Uptrend", "regime_score": 0.85,
                "playbook_tag": "minervini_vcp",
                "qullamaggie_score": 0, "minervini_score": 1, "leader_hold_score": 0,
                "pattern_diagnostics": (
                    '{"type":"vcp","pivot_price":175.5,"final_contraction_depth":0.08,'
                    '"depth_sequence":[0.25,0.15,0.08],"n_contractions":3,'
                    '"first_leg_depth":0.25,"breakout_vol_multiple":1.7,'
                    '"breakout_strength":0.85,"days_in_consolidation":18}'
                ),
                "breakout_strength": 0.85,
                "days_to_next_earnings": None,
                "crossed_52w_high_within_60d": False,
                "insider_cluster_buy": False,
                "earnings_in_3d_warn": False,
                "eps_knowable_from": None,
                # Phase 7 sizing cols (Plan 07-04 step 5.5 populates these in the
                # live pipeline; here we mimic that for the catch-up path).
                "stop_price": 161.46, "entry_price": 180.0, "shares": 50,
                "risk_per_share": 18.54, "atr_zone": "in-zone",
                "pivot_distance_atr_breakout": 0.25,
                "trail_rule_label": "21d EMA (then 50d SMA after 15 bars)",
                # Phase 7 revision iter 1: adr_rejected + rejection_reason are real
                # snapshot columns (Plan 07-01 revised). Catch-up helper reads
                # adr_rejected directly — Warning #6 single-source-of-truth.
                "adr_rejected": False, "rejection_reason": "",
            },
        ]
    )
    snap_df.to_parquet(snap_dir / f"{today_iso}.parquet", index=False)

    # 3. First invocation — inserts 1 row.
    from screener.cli import app
    runner = CliRunner()
    result1 = runner.invoke(app, ["journal"])
    assert result1.exit_code == 0, f"first invoke failed: {result1.stdout}"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        count_after_first = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    assert count_after_first == 1, f"expected 1 row after first invoke, got {count_after_first}"

    # 4. Second invocation — INSERT OR IGNORE → zero inserts.
    result2 = runner.invoke(app, ["journal"])
    assert result2.exit_code == 0, f"second invoke failed: {result2.stdout}"
    with sqlite3.connect(db_path) as conn:
        count_after_second = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
    assert count_after_second == count_after_first, (
        f"idempotency violated: {count_after_first} → {count_after_second}"
    )

    # 5. Structlog events sanity: second invocation should report
    # n_idempotent_skip == n_attempted (everything was a duplicate).
    events2 = [
        _json.loads(line) for line in result2.stdout.splitlines()
        if line.strip().startswith("{")
    ]
    catchup_events = [
        ev for ev in events2 if ev.get("event") == "journal_catchup_complete"
    ]
    assert catchup_events, f"expected journal_catchup_complete event; got events: {events2!r}"
    ev = catchup_events[-1]
    assert ev["n_inserted"] == 0, f"expected n_inserted=0; got {ev!r}"
    assert ev["n_idempotent_skip"] == ev["n_attempted"], f"expected full skip; got {ev!r}"
