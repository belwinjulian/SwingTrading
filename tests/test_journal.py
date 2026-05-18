"""tests/test_journal.py — Phase 7 OUT-04..06 SQLite + trigger tests.

Skeletons land in Plan 07-01 (Wave 0). Bodies land in Plan 07-03 (Wave 1).
"""
from __future__ import annotations

import pytest


def test_immutability_trigger() -> None:
    """OUT-05: UPDATE on any decision column raises sqlite3.IntegrityError with 'decision column immutable'."""
    pytest.skip("Plan 07-03")


def test_outcome_col_not_in_trigger() -> None:
    """OUT-06: UPDATE on exit_price (and other 5 outcome cols) does NOT fire the trigger."""
    pytest.skip("Plan 07-03")


def test_outcome_column_updatable() -> None:
    """OUT-06: the 6 outcome cols (entry_filled, exit_price, exit_date, hold_days, mfe, mae) are nullable and updatable."""
    pytest.skip("Plan 07-03")


def test_idempotent_append() -> None:
    """OUT-04: INSERT OR IGNORE on UNIQUE(ticker, snapshot_date) — mixed insert+duplicate batch → cur.rowcount == inserts only."""
    pytest.skip("Plan 07-03")


def test_features_json_roundtrip() -> None:
    """OUT-05: features_json column round-trips cleanly via json.loads."""
    pytest.skip("Plan 07-03")


def test_features_json_includes_diagnostics() -> None:
    """OUT-05 / D-03: features_json embeds full pattern_diagnostics dict (Phase 6 D-05 keys)."""
    pytest.skip("Plan 07-03")


def test_schema_idempotent_recreates_trigger() -> None:
    """RESEARCH Pitfall 1: DROP TABLE picks + re-call _ensure_picks_schema → trigger STILL fires on UPDATE."""
    pytest.skip("Plan 07-03")


def test_picks_schema_rejects_invalid_playbook_tag() -> None:
    """PicksSchema isin enum rejects 'none' or any tag not in {qullamaggie_continuation, minervini_vcp, leader_hold}."""
    pytest.skip("Plan 07-03")


def test_picks_schema_rejects_invalid_atr_zone() -> None:
    """PicksSchema isin enum rejects atr_zone not in {in-zone, extended, chase, skip}."""
    pytest.skip("Plan 07-03")


def test_journal_cli_idempotent() -> None:
    """OUT-04: invoke `screener journal` twice → second invocation inserts 0 rows (filled by Plan 07-05)."""
    pytest.skip("Plan 07-05")
