"""publishers.run_log — JSONL observability log for the nightly pipeline.

Writes one record per pipeline invocation to data/runs.jsonl. Called from
TWO sites in run_pipeline-aware code:
  1. publishers.pipeline.run_pipeline (success path — end of run, inline import)
  2. python -m screener.publishers.run_log {success|failure}
     (failure path invoked from the refresh.yml workflow when an earlier step
     fails; success path also available for symmetry but not used by v1)

D-06: NOT a typer subcommand. Module-internal call OR `python -m`. The
9-subcommand surface is locked by tests/test_cli_smoke.py (D-24).

OPS-05 record schema (success):
    status, start_time, duration_seconds, fetch_success_rate, regime_state,
    picks_count, n_429_responses, error_reason (null)

OPS-05 record schema (failure):
    status, start_time, duration_seconds, fetch_success_rate, regime_state
    (null), picks_count (null), n_429_responses, error_reason (str)

Architecture (D-23): publishers/ may import persistence/config/obs.
THIS module imports ONLY stdlib + structlog — keeps the writer minimal and
independent of Settings (which keeps the module-level _RUNS_PATH constant
trivially monkeypatchable in tests).

Crash-safety: open(path,'a') + json.dumps + flush + fsync. JSONL records
are newline-terminated so a partial-write tail leaves the file recoverable.
fsync is REQUIRED — without it, runner timeout/OOM can lose the last record.
(See 08-RESEARCH.md §Pitfall 5.)

Bodies are stubs in Plan 08-01 (Wave 0); Plan 08-03 (Wave 1) fills them.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import structlog

log = structlog.get_logger(__name__)


class RunLogRecord(TypedDict, total=False):
    """OPS-05 record schema. `total=False` because failure records omit
    or null-out picks_count / regime_state."""

    status: str  # "success" | "failed"
    start_time: str  # ISO 8601 UTC
    duration_seconds: float
    fetch_success_rate: float
    regime_state: str | None
    picks_count: int | None
    n_429_responses: int
    error_reason: str | None


# REVIEW: module-level constant (NOT a getattr-on-Settings helper) so that
# tests can monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", ...)
# without bouncing through pydantic-settings' @lru_cache. Deviates from the
# persistence.py _<name>_dir() helper pattern by design — see 08-PATTERNS.md
# §"Module-level path constant pattern".
_RUNS_PATH: Path = Path("data/runs.jsonl")


def append_record(record: RunLogRecord) -> None:
    """Append one record to data/runs.jsonl with flush + fsync (crash-safe).

    The caller (run_pipeline) constructs the dict with all required fields.
    This function ONLY writes; it does not collect metrics.

    Crash-safety (Pitfall #5): flush + os.fsync are BOTH required. flush
    pushes Python's text-mode buffer to the OS; fsync forces the OS to
    persist to disk. Without fsync, a runner timeout / OOM can lose the
    last record even though Python returned from write().
    """
    _RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True) + "\n"
    with open(_RUNS_PATH, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())  # force OS write — critical for the failure path
    log.info(
        "run_log_appended",
        status=record.get("status"),
        path=str(_RUNS_PATH),
    )


def _cli_failure_entry(status: str) -> None:
    """`python -m screener.publishers.run_log {success|failure}` entrypoint.

    Reads minimal metrics from environment (set by the workflow):
      RUN_START_TIME  — ISO timestamp from the workflow step (optional;
                        defaults to now)
      RUN_ERROR_REASON — defaults to "pipeline step failed"

    The success path is NOT invoked via this CLI in v1 — run_pipeline writes
    its own record directly via append_record(...). The success branch
    here exists for symmetry / future use; calling it produces a record
    with picks_count=None which is INCORRECT for a real success path. v1
    workflow YAML invokes ONLY the failure branch.
    """
    start_time = os.environ.get(
        "RUN_START_TIME",
        datetime.now(UTC).isoformat(timespec="seconds"),
    )
    record: RunLogRecord = {
        "status": status,
        "start_time": start_time,
        "duration_seconds": 0.0,
        "fetch_success_rate": 0.0,
        "regime_state": None,
        "picks_count": None,
        "n_429_responses": 0,
        "error_reason": os.environ.get(
            "RUN_ERROR_REASON", "pipeline step failed"
        ),
    }
    append_record(record)


if __name__ == "__main__":
    # Entry: python -m screener.publishers.run_log {success|failure}
    # NOTE: scripts/check_preregistration.py is the only other src-tree use
    # of print(..., file=sys.stderr); CLAUDE.md "no print()" rule applies to
    # runtime logging, not __main__ usage validation.
    if len(sys.argv) != 2 or sys.argv[1] not in ("success", "failure"):
        print(
            "usage: python -m screener.publishers.run_log {success|failure}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    _cli_failure_entry("failed" if sys.argv[1] == "failure" else "success")
