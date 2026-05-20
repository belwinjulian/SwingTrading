"""pipeline -> run_log integration tests — OPS-05.

Plan 08-05 (Wave 2) fills the test bodies. Tests run the full run_pipeline
orchestrator with every dependency mocked (build_panel, score, regime,
sizing, snapshot writers) and assert that the success path emits exactly
one JSONL record to ``data/runs.jsonl`` with all OPS-05 required fields.

Helpers (_setup_settings, _install_pipeline_mocks,
_make_synthetic_multiindex_panel) are imported from tests/test_pipeline_journal.py
or copied verbatim — Plan 08-05 decides at body-fill time.

No network. No real Settings reads (monkeypatch.setenv + cache_clear).
"""

# Wave: 2  (bodies filled by Plan 08-05)

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_pipeline_emits_run_log_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05: run_pipeline(snapshot_date) writes ONE JSONL record to
    _RUNS_PATH at the end of a successful run. Asserts:
      - the file exists at tmp_path/runs.jsonl
      - exactly one line was written
      - record['status'] == 'success'
      - record['regime_state'] == 'Confirmed Uptrend' (from the mocked regime)
      - record['picks_count'] is an int (not None)
      - record['duration_seconds'] > 0.0
    """
    # Reuse helpers from tests/test_pipeline_journal.py — same shape required.
    from tests.test_pipeline_journal import (
        _install_pipeline_mocks,
        _make_synthetic_multiindex_panel,
        _setup_settings,
    )

    _setup_settings(tmp_path, monkeypatch)
    runs_target = tmp_path / "runs.jsonl"
    monkeypatch.setattr(
        "screener.publishers.run_log._RUNS_PATH", runs_target
    )
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline

    run_pipeline("2026-05-18", write_report=False, write_journal=False)

    assert runs_target.exists(), f"runs.jsonl not written to {runs_target!r}"
    lines = runs_target.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, (
        f"expected exactly 1 record, got {len(lines)}: {lines!r}"
    )
    record = json.loads(lines[0])
    assert record["status"] == "success", f"status: {record!r}"
    assert record["regime_state"] == "Confirmed Uptrend", (
        f"regime_state mismatch: {record!r}"
    )
    assert isinstance(record["picks_count"], int), (
        f"picks_count must be int (not None) on success path: {record!r}"
    )
    assert record["duration_seconds"] > 0.0, (
        f"duration_seconds must be > 0 (perf_counter delta): {record!r}"
    )


def test_pipeline_run_log_record_has_all_required_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05: the success record contains EVERY OPS-05 schema field —
    status, start_time, duration_seconds, fetch_success_rate, regime_state,
    picks_count, n_429_responses, error_reason. Field presence is asserted
    via `assert set(record.keys()) >= {<expected>}` so future field additions
    don't break this test."""
    from tests.test_pipeline_journal import (
        _install_pipeline_mocks,
        _make_synthetic_multiindex_panel,
        _setup_settings,
    )

    _setup_settings(tmp_path, monkeypatch)
    runs_target = tmp_path / "runs.jsonl"
    monkeypatch.setattr(
        "screener.publishers.run_log._RUNS_PATH", runs_target
    )
    panel = _make_synthetic_multiindex_panel()
    _install_pipeline_mocks(monkeypatch, panel)

    from screener.publishers.pipeline import run_pipeline

    run_pipeline("2026-05-18", write_report=False, write_journal=False)

    record = json.loads(runs_target.read_text(encoding="utf-8").strip())
    expected_fields = {
        "status",
        "start_time",
        "duration_seconds",
        "fetch_success_rate",
        "regime_state",
        "picks_count",
        "n_429_responses",
        "error_reason",
    }
    missing = expected_fields - set(record.keys())
    assert not missing, (
        f"run_log record missing OPS-05 fields {missing!r}; "
        f"actual fields: {set(record.keys())!r}; "
        f"full record: {record!r}"
    )
    # Spot-check types where Python primitives matter.
    assert isinstance(record["start_time"], str)
    assert isinstance(record["duration_seconds"], (int, float))
    assert isinstance(record["fetch_success_rate"], (int, float))
    assert isinstance(record["n_429_responses"], int)
    assert record["error_reason"] is None  # success path
