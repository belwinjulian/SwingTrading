---
phase: 08-github-actions-cron-operations
plan: "03"
subsystem: publishers
tags: [phase-8, wave-1, run-log, publisher, ops, ops-05, jsonl, fsync, observability]

# Dependency graph
requires:
  - phase: 08-01
    provides: "src/screener/publishers/run_log.py scaffold (RunLogRecord TypedDict + _RUNS_PATH constant + raise-NotImplementedError signatures + __main__ block) plus tests/test_run_log.py 5 named pytest.skip skeletons"
provides:
  - "Real append_record(record) body — mkdir parent, json.dumps(record, sort_keys=True) + newline, flush + os.fsync(f.fileno()), structlog 'run_log_appended' event"
  - "Real _cli_failure_entry(status) body — reads RUN_START_TIME (defaults to datetime.now(UTC).isoformat(timespec='seconds')) + RUN_ERROR_REASON (default 'pipeline step failed'), constructs RunLogRecord with status='failed' / regime_state=None / picks_count=None, calls append_record"
  - "5 PASSING tests in tests/test_run_log.py (was 5 SKIPPED) covering TypedDict field surface, JSONL+fsync writes, sort_keys round-trip, default-env failure record, env-override failure record"
  - "python -m screener.publishers.run_log failure entrypoint working — verified from arbitrary cwd"
affects: ["08-05 pipeline run-log integration (inline-imports append_record)", "08-06 refresh.yml `if: failure()` step (python -m invocation)", "phase-8 OPS-05 nightly observability"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "File-I/O with flush + os.fsync(fd) for crash-safety on workflow runner timeout/OOM (Pitfall #5) — both calls required because flush only pushes to OS buffers, fsync pushes OS buffer to disk"
    - "json.dumps(record, sort_keys=True) so downstream diffs of runs.jsonl don't churn on field order"
    - "Module-level Path constant (_RUNS_PATH) monkeypatched via monkeypatch.setattr('module._RUNS_PATH', tmp_path/file) — sidesteps pydantic-settings @lru_cache and keeps the writer dependency-free"
    - "Architectural isolation (D-23): publishers/run_log.py imports ONLY stdlib + structlog — no screener.* imports so the writer survives even when Settings/persistence/obs are broken"

key-files:
  created: []
  modified:
    - "src/screener/publishers/run_log.py"
    - "tests/test_run_log.py"

key-decisions:
  - "Keep flush() AND os.fsync(f.fileno()) — both are required (Pitfall #5). flush only pushes Python's text buffer to the OS write buffer; fsync forces the OS buffer to disk. Without fsync, a runner timeout/OOM after write() returns can still lose the last record."
  - "datetime.now(UTC).isoformat(timespec='seconds') as the RUN_START_TIME fallback — second-resolution is sufficient for nightly-cron observability and avoids microsecond noise in JSONL diffs"
  - "Success branch in _cli_failure_entry exists for symmetry only (NOT invoked by v1 workflow YAML) — the docstring explicitly flags that calling it produces picks_count=None which is INCORRECT for a real success record; the real success path runs inline from publishers/pipeline.py via append_record"
  - "import json at module top (not inside the function) — append_record is on the nightly hot path; module-top imports avoid the import overhead on every call. json + os + datetime + Path + structlog + TypedDict already scaffolded by Plan 08-01"

patterns-established:
  - "Pattern: failure-path JSONL writer is the most-critical write in the system — give it the strictest crash-safety treatment (flush + fsync) because the failure case is the one we most need to preserve"
  - "Pattern: monkeypatch module-level path constants via monkeypatch.setattr('module._RUNS_PATH', tmp_path/file) — strictly cleaner than env-var redirection because there's no Settings re-instantiation involved"
  - "Pattern: tests import the module INSIDE the test function (not at the top) so module-import side-effects can't leak between tests and so monkeypatch.setattr works on a fresh module reference"

requirements-completed: [OPS-05]
requirements-partial: []

# Metrics
duration: 12min
completed: 2026-05-20
---

# Phase 8 Plan 03: Run-Log Bodies + Tests Summary

**Filled the bodies of `append_record()` + `_cli_failure_entry()` in `src/screener/publishers/run_log.py` and the 5 named test skeletons in `tests/test_run_log.py` (created as stubs by Plan 08-01). The writer now does the crash-safe `mkdir-parent → open(a) → write(json.dumps(record, sort_keys=True) + "\n") → flush → os.fsync(fd)` sequence and logs `run_log_appended` via structlog; the failure-CLI entry reads `RUN_START_TIME` + `RUN_ERROR_REASON` env vars (with sensible defaults) and routes through `append_record` so failures survive a runner timeout/OOM. OPS-05 observability requirement now satisfied at the writer layer; Plan 08-05 will wire `append_record` into `run_pipeline` and Plan 08-06 will invoke `python -m screener.publishers.run_log failure` from `refresh.yml`.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-20 (executor agent spawn)
- **Completed:** 2026-05-20
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- `append_record(record: RunLogRecord) -> None` body filled: makes parent dir, writes `json.dumps(record, sort_keys=True) + "\n"` in `"a"` mode with UTF-8, calls `f.flush()` then `os.fsync(f.fileno())`, emits a `run_log_appended` structlog event with `status` + `path` fields.
- `_cli_failure_entry(status: str) -> None` body filled: reads `RUN_START_TIME` (default `datetime.now(UTC).isoformat(timespec='seconds')`) + `RUN_ERROR_REASON` (default `'pipeline step failed'`), constructs a `RunLogRecord` with `status` + `start_time` + `duration_seconds=0.0` + `fetch_success_rate=0.0` + `regime_state=None` + `picks_count=None` + `n_429_responses=0` + `error_reason=<env or default>`, calls `append_record(record)`.
- 5 previously-SKIPPED tests in `tests/test_run_log.py` now PASS:
  - `test_runlogrecord_typeddict_has_all_ops05_fields` — asserts `get_type_hints(RunLogRecord)` contains all 8 OPS-05 fields.
  - `test_append_record_writes_valid_jsonl_with_fsync` — monkeypatches `_RUNS_PATH` to `tmp_path/subdir/runs.jsonl` (parent missing), verifies file is created, newline-terminated, round-trips through `json.loads`.
  - `test_append_record_round_trip_json` — null-bearing record (regime_state=None, picks_count=None) round-trips bytewise through `json.dumps(sort_keys=True)` → `json.loads`.
  - `test_cli_failure_entry_writes_failure_record` — default branch: with env unset, record has `status='failed'`, `regime_state is None`, `picks_count is None`, `error_reason == 'pipeline step failed'`, `n_429_responses == 0`, `start_time` present.
  - `test_cli_failure_entry_uses_env_error_reason` — env branch: `RUN_ERROR_REASON='yfinance 429 retry exhausted'` and `RUN_START_TIME='2026-05-19T22:30:00+00:00'` both flow verbatim into the record.
- `python -m screener.publishers.run_log failure` smoke-tested from a fresh tmp directory: created `data/runs.jsonl` under cwd with one sorted-keys JSONL line carrying `RUN_ERROR_REASON=smoke-test invocation` (SC#3 verified end-to-end).
- D-23 isolation preserved — `grep -v '^#' src/screener/publishers/run_log.py | grep -c "from screener"` returns 0 (no `from screener.*` imports).
- D-24 9-subcommand surface unchanged — `tests/test_cli_smoke.py::test_subcommand_surface_locked` still PASSES (1 passed).
- FND-04 no-look-ahead test still PASSES (2 passed) — no `signals/` or `backtest/` touched in this plan.
- mypy clean on `src/screener/publishers/run_log.py` (`Success: no issues found in 1 source file`).

## Task Commits

Each task was committed atomically on branch `worktree-agent-accbad65a216b1e44`:

1. **Task 1: Implement append_record and _cli_failure_entry in run_log.py** — `5b90549` (feat)
   - Replaced `raise NotImplementedError(...)` in `append_record` with the real 5-line body (mkdir + json.dumps + open(a) + flush + fsync + structlog event).
   - Replaced `raise NotImplementedError(...)` in `_cli_failure_entry` with the env-reading + record-constructing + append_record-calling body.
   - Module imports (json, os, sys, datetime/UTC, Path, TypedDict, structlog) and the `if __name__ == "__main__"` block left untouched.

2. **Task 2: Fill bodies of 5 run_log tests (SKIPPED → PASSED)** — `0d503c4` (test)
   - Replaced each `pytest.skip(...)` with the real test body (5 tests).
   - Updated wave marker comment to `# Wave: 1 (bodies filled by Plan 08-03)`.
   - All `from screener.publishers import run_log` (and the TypedDict import) live INSIDE each test function so monkeypatching `_RUNS_PATH` works on a fresh module reference each time.

## Files Created/Modified

- `src/screener/publishers/run_log.py` — bodies of `append_record` (5 LOC core + structlog event) and `_cli_failure_entry` (env reads + dict literal + append_record call) filled. Net: +37 / −7 lines. Module imports + RunLogRecord TypedDict + `_RUNS_PATH` constant + `__main__` block UNCHANGED.
- `tests/test_run_log.py` — bodies of 5 `pytest.skip(...)` stubs replaced with real assertions + monkeypatch invocations + tmp_path file-existence checks. Wave marker updated 0 → 1. Net: +87 / −6 lines.

## Decisions Made

- **`flush()` AND `os.fsync(f.fileno())` are BOTH non-negotiable.** flush pushes Python's text-mode buffer to the OS write buffer; fsync forces the OS buffer to be persisted to disk. The plan-spec made this explicit; the smoke test confirms the call sequence works on macOS (Darwin 24.6.0). The failure case is the most critical write in the system because that's the case the workflow YAML invokes when an earlier step has already failed — if fsync is skipped and the runner times out or is OOM-killed, the JSONL record is silently lost.
- **`json.dumps(record, sort_keys=True)`** — without sort_keys, the dict iteration order leaks into the JSONL output and causes downstream `git diff data/runs.jsonl` to churn on field ordering. The deterministic sort eliminates that noise (verified by the smoke-test output line where keys come back alphabetically: `duration_seconds, error_reason, fetch_success_rate, n_429_responses, picks_count, regime_state, start_time, status`).
- **`datetime.now(UTC).isoformat(timespec='seconds')` for the RUN_START_TIME default** — second-resolution is sufficient for nightly-cron observability and avoids microsecond noise. The format matches what the workflow YAML will pass in (Plan 08-06 will set `RUN_START_TIME=$(date -u +%Y-%m-%dT%H:%M:%S%z)` in shell), so the env-set vs default-set paths produce indistinguishable records.
- **Success branch in `_cli_failure_entry` is intentionally a "smell" path.** The docstring explicitly warns that the success record produced by this CLI has `picks_count=None`, which is incorrect for a real success record (a real success has `picks_count >= 0`). The branch exists ONLY for `python -m screener.publishers.run_log success` invocation symmetry — v1 workflow YAML calls only the failure branch; the real success path runs inline from `publishers/pipeline.py:run_pipeline` (Plan 08-05) and constructs its own record with the real `picks_count`.
- **Test-internal imports** (`from screener.publishers import run_log` INSIDE each test) — keeps module-import side-effects from leaking across tests and makes `monkeypatch.setattr('screener.publishers.run_log._RUNS_PATH', target)` work cleanly on a fresh reference each invocation. This matches the pattern used in `tests/test_insider_io.py`.

## Deviations from Plan

None — plan executed exactly as written. Both `<action>` reference code blocks were applied bytewise. The plan's authoritative source for the function bodies and test bodies was the verbatim spec under `<action>` for each task; both were applied without modification.

Auto-fix Rules 1-3 were not triggered — no bugs, missing critical functionality, or blocking issues were discovered during execution. The plan's pre-existing scaffolding (TypedDict, _RUNS_PATH constant, signatures, `__main__` block) was correctly set up by Plan 08-01 and required no Rule 2 additions.

## Issues Encountered

- **Worktree path confusion (resolved early).** Initial Read/Edit calls used the project's main absolute path `/Users/belwinjulian/SwingTrading/...` instead of the worktree path `/Users/belwinjulian/SwingTrading/.claude/worktrees/agent-accbad65a216b1e44/...`. Edits temporarily landed in the main repo working tree (NOT committed there). Reverted the main repo file via `git checkout -- src/screener/publishers/run_log.py` before any commit was made, then re-applied the same edits to the worktree path. No commits were made on `main`; no pollution leaked. Both Task 1 (`5b90549`) and Task 2 (`0d503c4`) are committed on the worktree branch only.
- **No other issues.** Test run, mypy run, and `python -m` smoke test all PASSED on first attempt after the edits were correctly placed in the worktree.

## Threat Model Compliance

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-08-secrets | mitigate | ✓ `grep -E "FINNHUB_API_KEY\|EDGAR_IDENTITY\|FRED_API_KEY\|set -x" src/screener/publishers/run_log.py` returns empty. Module reads ONLY `RUN_ERROR_REASON` + `RUN_START_TIME` env vars (both workflow-controlled non-secret strings). No secret-bearing env vars are read or logged. |
| T-08-script-injection | accept | ✓ This plan ships Python only; no workflow YAML, no `${{ github.event.* }}` interpolation. |
| T-08-supply-chain | accept | ✓ No new GitHub Actions, no new third-party dependencies — only stdlib + structlog (already pinned). |
| T-08-overscope-perms | accept | ✓ Module is library code; permissions are granted by the workflow that invokes it (Plans 08-04 + 08-06). |
| T-08-commit-loop | accept | ✓ `append_record` appends one line per invocation. No `git push` calls, no recursive triggers, no auto-rerun. |
| Disk-fill via unbounded JSONL growth | accept | ✓ ~150 bytes/line × 365 nightly runs/year × 5 years ≈ 270 KB. Well below any practical threshold; no log rotation needed for v1. |

## User Setup Required

None — no external service configuration required for this plan. (Plan 08-06 will add a workflow-YAML step that sets `RUN_ERROR_REASON` and invokes `python -m screener.publishers.run_log failure`; that's a future plan.)

## Verification Snapshot

Final state post-Task 2 (verified locally):

```text
=== Plan 08-03 Done Criteria ===
grep -c "os.fsync(f.fileno())" src/screener/publishers/run_log.py            = 1   ✓
grep -c "json.dumps(record, sort_keys=True)" src/screener/publishers/run_log.py = 1   ✓
grep -c "raise NotImplementedError" src/screener/publishers/run_log.py       = 0   ✓
grep -v '^#' src/screener/publishers/run_log.py | grep -c "from screener"    = 0   ✓ (D-23)
grep -c "pytest.skip" tests/test_run_log.py                                  = 0   ✓
grep -c "monkeypatch.setattr" tests/test_run_log.py                          = 4   ✓ (>= 4)

=== Test Runs ===
pytest tests/test_run_log.py                                  → 5 passed, 0 skipped, 0 failed  ✓
pytest tests/test_phase8_gitignore.py                         → 4 passed, 0 skipped, 0 failed  ✓
pytest tests/test_backtest_no_lookahead.py                    → 2 passed (FND-04 intact)  ✓
pytest tests/test_cli_smoke.py::test_subcommand_surface_locked → 1 passed (D-24 intact)  ✓

=== Type Check ===
mypy src/screener/publishers/run_log.py                       → Success: no issues found in 1 source file  ✓

=== CLI Smoke Test ===
(from tmp dir) RUN_ERROR_REASON="smoke-test invocation" python -m screener.publishers.run_log failure
  → data/runs.jsonl created under cwd with:
     {"duration_seconds": 0.0, "error_reason": "smoke-test invocation",
      "fetch_success_rate": 0.0, "n_429_responses": 0, "picks_count": null,
      "regime_state": null, "start_time": "2026-05-20T12:48:25+00:00", "status": "failed"}
  → sort_keys=True confirmed (alphabetical order: duration_seconds, error_reason, ...)
  → newline-terminated  ✓ (SC#3)
```

## Next Phase Readiness

- **Plan 08-05 (pipeline run-log integration)** can now do `from screener.publishers.run_log import append_record` at the END of `run_pipeline` and construct the success record (with real `picks_count`, real `duration_seconds`, real `fetch_success_rate`, real `regime_state`, real `n_429_responses`) and call `append_record(record)`. The writer is crash-safe, fsync-correct, and TypedDict-typed.
- **Plan 08-06 (refresh.yml workflow YAML)** can now add an `if: failure()` step that runs `python -m screener.publishers.run_log failure` with `RUN_ERROR_REASON` set from the failing job context. The `python -m` entrypoint is verified working from arbitrary cwd; `data/runs.jsonl` carve-out from Plan 08-02 means the auto-commit step will pick the file up past `.gitignore`.
- **No blockers** for Wave 1's remaining plans or Wave 2.
- **Plan 08-03 was the OPS-05 core**; OPS-05 marks complete-at-the-writer-layer now. Pipeline integration (Plan 08-05) closes OPS-05 end-to-end.

## Self-Check: PASSED

**Files asserted to exist:**
- `src/screener/publishers/run_log.py` — FOUND (modified, contains real bodies; `grep -c "os.fsync(f.fileno())"` returns 1, `grep -c "raise NotImplementedError"` returns 0)
- `tests/test_run_log.py` — FOUND (modified, 5 tests PASS, 0 SKIPPED, wave marker updated)
- `.planning/phases/08-github-actions-cron-operations/08-03-SUMMARY.md` — FOUND (this file)

**Commits asserted to exist on branch `worktree-agent-accbad65a216b1e44`:**
- `5b90549` — feat(08-03): implement append_record and _cli_failure_entry in run_log.py — FOUND in `git log --oneline -3`
- `0d503c4` — test(08-03): fill bodies of 5 run_log tests (SKIPPED -> PASSED) — FOUND in `git log --oneline -3`

**Behaviors asserted:**
- `append_record(rec)` writes one JSONL line, round-trips bytewise via `json.loads` — verified by inline smoke test (RUN_LOG_OK) and by `test_append_record_writes_valid_jsonl_with_fsync` PASS.
- `os.fsync(f.fileno())` is called — verified by source grep (count == 1) and by `test_append_record_writes_valid_jsonl_with_fsync` indirectly (test fails if fsync raises on the open file descriptor).
- `_cli_failure_entry('failed')` produces a record with `status='failed'`, `regime_state=None`, `picks_count=None`, `error_reason` from env-or-default — verified by 2 tests (default branch + env branch) and by the cwd-`python -m` smoke test.
- `python -m screener.publishers.run_log failure` works from arbitrary cwd — verified by the tmp-dir smoke test above.
- D-23 isolation (no screener.* imports in run_log.py) — verified by grep count == 0.
- D-24 9-subcommand surface — verified by `test_subcommand_surface_locked` PASS.
- FND-04 no-look-ahead — verified by `test_backtest_no_lookahead.py` 2 PASS.

---
*Phase: 08-github-actions-cron-operations*
*Completed: 2026-05-20*
