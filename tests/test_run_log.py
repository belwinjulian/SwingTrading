"""publishers.run_log tests — OPS-05.

Plan 08-03 (Wave 1) fills the test bodies with mocked assertions over
``src/screener/publishers/run_log.py``. Tests monkeypatch the module-level
``_RUNS_PATH`` to redirect writes to ``tmp_path / "runs.jsonl"`` (no real
data/runs.jsonl writes from tests).

No network calls in any test.
"""

# Wave: 0  (named-stub skeletons; bodies filled by Plan 08-03 — see 08-VALIDATION.md "New test files")

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import get_type_hints

import pytest


def test_runlogrecord_typeddict_has_all_ops05_fields() -> None:
    """OPS-05: RunLogRecord exposes every field the workflow YAML + run_pipeline
    reference (status, start_time, duration_seconds, fetch_success_rate,
    regime_state, picks_count, n_429_responses, error_reason)."""
    pytest.skip("body filled by Plan 08-03 (Wave 1)")


def test_append_record_writes_valid_jsonl_with_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05 + Pitfall #5: append_record writes one JSONL line to _RUNS_PATH,
    flushes the Python buffer, and fsyncs the file descriptor. Verifies the
    file is created with parent dirs and the written line round-trips through
    json.loads."""
    pytest.skip("body filled by Plan 08-03 (Wave 1)")


def test_append_record_round_trip_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05: a record dict with all required fields serializes via
    json.dumps(sort_keys=True) and round-trips back to the same dict on
    json.loads — proves sort_keys + newline-termination work end-to-end."""
    pytest.skip("body filled by Plan 08-03 (Wave 1)")


def test_cli_failure_entry_writes_failure_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05 SC#5: _cli_failure_entry('failed') writes a record with
    status='failed', regime_state=None, picks_count=None, error_reason set
    from RUN_ERROR_REASON env (or the default 'pipeline step failed')."""
    pytest.skip("body filled by Plan 08-03 (Wave 1)")


def test_cli_failure_entry_uses_env_error_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS-05: when RUN_ERROR_REASON env is set, the failure record's
    error_reason field exactly matches the env value (no truncation,
    no quote-stripping)."""
    pytest.skip("body filled by Plan 08-03 (Wave 1)")
