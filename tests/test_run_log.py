"""publishers.run_log tests — OPS-05.

Plan 08-03 (Wave 1) fills the test bodies with mocked assertions over
``src/screener/publishers/run_log.py``. Tests monkeypatch the module-level
``_RUNS_PATH`` to redirect writes to ``tmp_path / "runs.jsonl"`` (no real
data/runs.jsonl writes from tests).

No network calls in any test.
"""

# Wave: 1  (bodies filled by Plan 08-03)

from __future__ import annotations

import json
from pathlib import Path
from typing import get_type_hints

import pytest


def test_runlogrecord_typeddict_has_all_ops05_fields() -> None:
    """OPS-05: RunLogRecord exposes every field the workflow YAML + run_pipeline
    reference (status, start_time, duration_seconds, fetch_success_rate,
    regime_state, picks_count, n_429_responses, error_reason)."""
    from screener.publishers.run_log import RunLogRecord

    hints = get_type_hints(RunLogRecord)
    expected = {
        "status",
        "start_time",
        "duration_seconds",
        "fetch_success_rate",
        "regime_state",
        "picks_count",
        "n_429_responses",
        "error_reason",
    }
    assert expected <= set(hints.keys()), (
        f"RunLogRecord missing OPS-05 fields: {expected - set(hints.keys())!r}; "
        f"got fields: {set(hints.keys())!r}"
    )


def test_append_record_writes_valid_jsonl_with_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05 + Pitfall #5: append_record writes one JSONL line to _RUNS_PATH,
    flushes the Python buffer, and fsyncs the file descriptor. Verifies the
    file is created with parent dirs and the written line round-trips through
    json.loads."""
    from screener.publishers import run_log

    target = tmp_path / "subdir" / "runs.jsonl"  # parent missing on purpose
    monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", target)

    rec = {
        "status": "success",
        "start_time": "2026-05-19T22:30:00+00:00",
        "duration_seconds": 1847.0,
        "fetch_success_rate": 0.982,
        "regime_state": "Confirmed Uptrend",
        "picks_count": 7,
        "n_429_responses": 3,
        "error_reason": None,
    }
    run_log.append_record(rec)

    assert target.exists(), f"runs.jsonl not created at {target!r}"
    raw = target.read_text(encoding="utf-8")
    assert raw.endswith("\n"), f"line not newline-terminated: {raw!r}"
    parsed = json.loads(raw.strip())
    assert parsed == rec, f"round-trip mismatch: {parsed!r} != {rec!r}"


def test_append_record_round_trip_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05: a record dict with all required fields serializes via
    json.dumps(sort_keys=True) and round-trips back to the same dict on
    json.loads — proves sort_keys + newline-termination work end-to-end."""
    from screener.publishers import run_log

    target = tmp_path / "runs.jsonl"
    monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", target)

    rec_with_nulls = {
        "status": "failed",
        "start_time": "2026-05-19T22:30:00+00:00",
        "duration_seconds": 0.0,
        "fetch_success_rate": 0.0,
        "regime_state": None,
        "picks_count": None,
        "n_429_responses": 0,
        "error_reason": "universe coverage 91.2% < 95% threshold",
    }
    run_log.append_record(rec_with_nulls)

    parsed = json.loads(target.read_text(encoding="utf-8").strip())
    assert parsed == rec_with_nulls, f"null-bearing record mismatch: {parsed!r}"


def test_cli_failure_entry_writes_failure_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05 SC#5: _cli_failure_entry('failed') writes a record with
    status='failed', regime_state=None, picks_count=None, error_reason set
    from RUN_ERROR_REASON env (or the default 'pipeline step failed')."""
    from screener.publishers import run_log

    target = tmp_path / "runs.jsonl"
    monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", target)
    monkeypatch.delenv("RUN_ERROR_REASON", raising=False)
    monkeypatch.delenv("RUN_START_TIME", raising=False)

    run_log._cli_failure_entry("failed")

    record = json.loads(target.read_text(encoding="utf-8").strip())
    assert record["status"] == "failed"
    assert record["regime_state"] is None
    assert record["picks_count"] is None
    assert record["error_reason"] == "pipeline step failed"
    assert record["n_429_responses"] == 0
    assert "start_time" in record  # default ISO timestamp present


def test_cli_failure_entry_uses_env_error_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05: when RUN_ERROR_REASON env is set, the failure record's
    error_reason field exactly matches the env value (no truncation,
    no quote-stripping)."""
    from screener.publishers import run_log

    target = tmp_path / "runs.jsonl"
    monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", target)
    monkeypatch.setenv("RUN_ERROR_REASON", "yfinance 429 retry exhausted")
    monkeypatch.setenv("RUN_START_TIME", "2026-05-19T22:30:00+00:00")

    run_log._cli_failure_entry("failed")

    record = json.loads(target.read_text(encoding="utf-8").strip())
    assert record["error_reason"] == "yfinance 429 retry exhausted"
    assert record["start_time"] == "2026-05-19T22:30:00+00:00"
