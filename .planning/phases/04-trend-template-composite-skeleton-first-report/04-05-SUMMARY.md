---
phase: "04"
plan: "05"
subsystem: cli-wiring-preregistration
tags: [cli, publishers, pipeline, preregistration, FND-05, D-08, D-09, D-10, D-14, OUT-01, wave-4]
dependency_graph:
  requires: [04-01, 04-02, 04-03, 04-04]
  provides: [cli score/report real bodies, scripts/check_preregistration.py, frozen weights doc, CI preregistration gate, D-08 integration test]
  affects: [phase-5-backtest, phase-6-signals, phase-7-sizing]
tech_stack:
  added: []
  patterns:
    - "Deferred import inside CLI body (from screener.publishers.pipeline import run_pipeline) for lazy loading and D-16 compliance"
    - "except typer.Exit: raise pattern (Pitfall 7) before broader Exception handler"
    - "Stdlib-only module top with lazy heavy import inside main() for CI-speed script (scripts/check_preregistration.py)"
    - "Two-commit freeze ceremony for tamper-evident weight preregistration (D-10)"
key_files:
  created:
    - scripts/check_preregistration.py
    - scripts/__init__.py
    - scripts/.gitkeep
    - tests/test_preregistration_check.py
  modified:
    - src/screener/cli.py
    - tests/test_cli_smoke.py
    - docs/strategy_v1_preregistration.md
    - .github/workflows/ci.yml
key_decisions:
  - "score() and report() use deferred import of run_pipeline inside body to maintain D-16 compliance at module import time"
  - "T-3-02 carry-forward: log.error logs only error_type, never exception string (API key leakage prevention)"
  - "PHASE_1_STUBS reduced from 6 to 4 entries: score and report now have real bodies"
  - "Freeze ceremony uses two-commit approach: first commit has placeholder SHA, second commit substitutes actual SHA"
  - "D-10 hash registration is tamper-evident: CI checks weights but not hash itself; human reviewer uses git log to verify chain"
requirements-completed: [FND-05, OUT-01]
duration: "~6 minutes (Tasks 1-3 complete; Task 4 checkpoint pending human verification)"
completed: "2026-05-10"
---

# Phase 04 Plan 05: CLI Wiring + Preregistration Freeze Summary

**One-liner:** Wired cli.py score/report to publishers.pipeline.run_pipeline (D-14 preserved), shipped stdlib-only FND-05 preregistration CI gate, and filled strategy_v1_preregistration.md with concrete frozen weights matching DEFAULT_WEIGHTS — awaiting D-10 two-commit freeze ceremony.

## Performance

- **Duration:** ~6 minutes (Tasks 1-3); Task 4 checkpoint pending
- **Started:** 2026-05-10T23:37:44Z
- **Completed:** 2026-05-10T23:44:43Z (Tasks 1-3)
- **Tasks:** 3 of 5 complete (Task 4 is a human-verify checkpoint; Task 5 follows Task 4)
- **Files modified:** 7

## Accomplishments

### Task 1: cli.py score/report + D-08 integration test (commit 49df0f1)

**Files:** `src/screener/cli.py`, `tests/test_cli_smoke.py`

Replaced `_stub("score")` and `_stub("report")` in `src/screener/cli.py` with real bodies:

```python
@app.command("score")
def score() -> None:
    configure_logging()
    try:
        from screener.publishers.pipeline import run_pipeline
        run_pipeline(date.today().isoformat(), write_report=False)
    except typer.Exit:
        raise  # Pitfall 7
    except Exception as e:
        log.error("score_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

Changes to `tests/test_cli_smoke.py`:
- `PHASE_1_STUBS` reduced from 6 to 4 entries (score + report removed)
- `D14_SUBCOMMANDS` untouched (D-14 lock preserved at 9 subcommands)
- Added `test_report_data_quality_gate_d08` — D-08 integration test verifying that pass_rate=0.30 + Correction -> exit_code != 0 + "data_quality_gate_failed" event
- Added `test_score_subcommand_no_longer_stub` + `test_report_subcommand_no_longer_stub`

All 9 tests in test_cli_smoke.py pass. mypy clean on cli.py. ruff clean.

### Task 2: scripts/check_preregistration.py + 3 FND-05 tests (commit cff1537)

**Files:** `scripts/check_preregistration.py`, `scripts/__init__.py`, `scripts/.gitkeep`, `tests/test_preregistration_check.py`

Stdlib-only CI gate at module top; `DEFAULT_WEIGHTS` import is deferred inside `main()` (Pitfall 9). The `NAME_TO_KEY` mapping translates the doc's friendly names to the composite.py dict keys.

`parse_doc_weights()` uses anchored regex to capture the rightmost percentage on each table row. Exits with `sys.exit` on missing row (clean error message), returns 1 with "Weight mismatch:" line (D-09 format) on any key differing by > 1e-3.

3 unit tests:
- `test_matching_weights_pass` — matching weights return 0
- `test_mismatched_weights_fail` — mismatch returns 1 with formatted diff line
- `test_missing_weight_in_doc_fail` — missing row raises SystemExit containing "Catalyst presence"

All 3 tests pass. ruff clean.

### Task 3: Fill doc weights + CI step (commit cfacdb9)

**Files:** `docs/strategy_v1_preregistration.md`, `.github/workflows/ci.yml`

Replaced all 6 TBDs in the Frozen Weight column with concrete values matching `DEFAULT_WEIGHTS` exactly:
- RS: 25%, Trend: 20%, Pattern: 20%, Volume: 10%, Earnings: 15%, Catalyst: 10%

Cleaned up placeholder tokens (`<weights frozen at Phase 4 completion>` removed). Updated status to "Frozen on 2026-05-10". Added `Frozen at commit: <PLACEHOLDER>` lines awaiting the freeze ceremony.

`.github/workflows/ci.yml`: inserted "Preregistration consistency (FND-05)" step between "Install dependencies (frozen)" and "pytest".

Script passes live: `uv run python scripts/check_preregistration.py` -> `Preregistration check passed.` (exit 0).

## Task 4 Status: CHECKPOINT (awaiting human verification)

Task 4 is the two-commit D-10 freeze ceremony. It is a `checkpoint:human-verify` and cannot be completed automatically. See the CHECKPOINT REACHED section for instructions.

The placeholder strings `<PLACEHOLDER_TO_BE_REPLACED_BY_NEXT_COMMIT>` in `docs/strategy_v1_preregistration.md` must be substituted with the actual SHA of the freeze commit.

## D-14 Lock Status

The 9-subcommand surface is intact. `D14_SUBCOMMANDS` in `tests/test_cli_smoke.py` still lists all 9 names. `test_help_lists_all_d14_subcommands` passes.

## D-16 Architecture Status

`test_architecture.py` passes. `cli.py` uses deferred import inside the body (not at module top) to avoid importing publishers at module load time, which would be fine architecturally (cli is not in D-16's restricted set), but deferred import is also consistent with the existing `refresh_macro` pattern.

## IND-02 SMA-not-EMA Gate

`grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` returns no matches. Gate intact.

## Test Count Delta

| Phase | Tests |
|-------|-------|
| Prior (Phases 1-3 + 04-01..04) | 128 |
| Plan 04-05 additions | +9 (3 cli_smoke + 3 preregistration + 3 no-longer-stub) |
| Total (131 pass + 2 skip) | 133 |

The full suite runs 131 passed, 2 skipped with `pytest -m "not slow"`.

## Deviations from Plan

None — plan executed exactly as written for Tasks 1-3. Task 4 is blocked at checkpoint per plan design.

## Known Stubs

None added by this plan. Pre-existing stubs (Phase 4 ZEROED components) are documented in 04-04-SUMMARY.md.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns beyond what is in the plan's threat model.

Mitigations applied as planned:
- **T-4-20** (info disclosure in CLI error): `log.error("score_failed", error_type=type(e).__name__)` — T-3-02 carry-forward confirmed in cli.py
- **T-4-23** (typer.Exit caught silently): `except typer.Exit: raise` before broader Exception handler in both score() and report()
- **T-4-19** (DEFAULT_WEIGHTS tampering): `scripts/check_preregistration.py` CI gate added + tested

## Self-Check: PASSED

Verified files exist:
- `src/screener/cli.py` contains 2 occurrences of `from screener.publishers.pipeline import run_pipeline` — CONFIRMED
- `scripts/check_preregistration.py` contains `parse_doc_weights`, `main`, `Weight mismatch:`, `DEFAULT_WEIGHTS` — CONFIRMED
- `docs/strategy_v1_preregistration.md` has 0 TBDs and concrete frozen weights — CONFIRMED
- `.github/workflows/ci.yml` contains `Preregistration consistency (FND-05)` step — CONFIRMED
- `tests/test_preregistration_check.py` contains `test_matching_weights_pass` — CONFIRMED

Verified commits exist:
- `49df0f1` — feat(04-05): wire cli.py score/report to publishers.pipeline + D-08 integration test
- `cff1537` — feat(04-05): add scripts/check_preregistration.py + 3 FND-05 tests
- `cfacdb9` — docs(04-05): fill preregistration weights table + add CI gate step (Task 3)
