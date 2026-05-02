---
phase: 01-repo-skeleton-ci-hygiene
plan: 03
subsystem: testing
tags: [pytest, ast, architecture-test, typer, cli-smoke, hypothesis]

# Dependency graph
requires:
  - phase: 01-repo-skeleton-ci-hygiene
    plan: 01
    provides: pyproject.toml with pytest + pytest-cov + --cov-fail-under=80 markers and the dev extras (pytest, hypothesis)
  - phase: 01-repo-skeleton-ci-hygiene
    plan: 02
    provides: src/screener/ source tree with cli.py exposing the 9 D-14 typer subcommands and the layered DAG these tests enforce (post-merge dependency)
provides:
  - tests/__init__.py (package marker)
  - tests/conftest.py with session-scoped repo_root and src_screener path fixtures
  - tests/test_architecture.py — hand-rolled AST-based one-way DAG enforcement (D-16) with three sub-tests
  - tests/test_cli_smoke.py — typer CliRunner-based assertion that all 9 D-14 subcommands are exposed and exit 0 with a structured [stub] log line
affects: [phase-01-04 (CI workflow runs pytest), phase-01-05 (branch protection requires test status check), phase-02 (data layer must obey D-16), phase-03 (indicators/ must stay pure), phase-05 (backtest/ must stay airtight)]

# Tech tracking
tech-stack:
  added: [stdlib ast (no third-party import-linter), typer.testing.CliRunner]
  patterns:
    - "Architectural contract enforced by stdlib-only test (zero extra trust point)"
    - "Layer-import contract encoded in a single ALLOWED dict — extension is visible in code review"
    - "CLI surface frozen by D14_SUBCOMMANDS list — adding/removing a subcommand without updating the test fails CI"
    - "Tests use session-scoped path fixtures (repo_root, src_screener) instead of hard-coded relative paths"

key-files:
  created:
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_architecture.py
    - tests/test_cli_smoke.py
  modified: []

key-decisions:
  - "Use stdlib ast.parse + ast.walk over import-linter — same guarantees, zero extra dependency, contract self-contained in the test file"
  - "Three architecture sub-tests instead of one monolithic check: layer contract, backtest airtight, indicators/signals pure-function — failures point to the specific invariant broken"
  - "backtest/ ALLOWED set is {persistence} only (verbatim D-16) — even obs (env-coupled logger) and config (API keys) are denied to keep backtest provably non-network"
  - "obs added to all non-backtest layers' ALLOWED sets as a documented expansion of D-16 — structured logging is universally needed; CONTEXT.md introduced obs.py under Claude's Discretion"
  - "test_cli_smoke uses typer's CliRunner (in-process) over subprocess — faster, deterministic stdout capture, no PATH/env coupling"
  - "Architecture test classifies each src/screener/**/*.py file by its first path component (top-level dir or top-level .py file) — handles regime.py / sizing.py (files) and data/ / indicators/ (dirs) uniformly"

patterns-established:
  - "Pattern: ALLOWED dict as single-source-of-truth for layer contract — extending the architecture requires editing one obvious dict, change is visible in review"
  - "Pattern: D14_SUBCOMMANDS list as single-source-of-truth for CLI surface — adding a new subcommand requires editing one list, change is visible in review"
  - "Pattern: pytest fixtures for repo paths (repo_root, src_screener) — Phase 2+ tests reuse them"
  - "Pattern: hand-rolled AST tests for architectural invariants — model for future tests like 'no-look-ahead' (Phase 5) and 'SMA-not-EMA grep' (Phase 3)"

requirements-completed: [FND-03]

# Metrics
duration: 2m 12s
completed: 2026-05-02
---

# Phase 1 Plan 3: Tests Scaffolding Summary

**Pytest scaffolding plus the two foundational Phase-1 tests: an AST-based one-way DAG enforcer (D-16) with no third-party deps, and a typer CliRunner smoke test that locks the 9 D-14 subcommand surface.**

## Performance

- **Duration:** 2m 12s
- **Started:** 2026-05-02T12:36:52Z
- **Completed:** 2026-05-02T12:39:04Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `tests/` package created with session-scoped path fixtures (`repo_root`, `src_screener`) ready for Phase 2+ to extend with OHLCV / golden-file fixtures.
- `tests/test_architecture.py` encodes the D-16 layered-import contract using stdlib `ast.parse` + `ast.walk` — three sub-tests cover (1) layer contract, (2) backtest airtight from network/config/obs, (3) indicators+signals pure-function (forbid requests/yfinance/finnhub/edgar/etc.). Zero third-party dependency; contract is self-contained in one ALLOWED dict.
- `tests/test_cli_smoke.py` uses typer's in-process `CliRunner` to assert `screener --help` lists all 9 D-14 subcommands and that each subcommand exits 0 with a JSON `[stub]` log line — adding/removing a subcommand without updating the `D14_SUBCOMMANDS` list fails CI loudly.

## Task Commits

Each task was committed atomically with `--no-verify` (worktree-mode; orchestrator runs hooks centrally post-merge):

1. **Task 1: tests package scaffolding** — `024dc30` (test) — created `tests/__init__.py` (package marker) + `tests/conftest.py` (repo_root, src_screener fixtures)
2. **Task 2: AST-based DAG architecture test** — `788d914` (test) — created `tests/test_architecture.py` with three sub-tests enforcing D-16 verbatim
3. **Task 3: CLI smoke test for D-14** — `ec85cb3` (test) — created `tests/test_cli_smoke.py` using typer's CliRunner

## Files Created/Modified

- `tests/__init__.py` — empty docstring; marks `tests/` as a package
- `tests/conftest.py` — `repo_root` and `src_screener` session-scoped path fixtures
- `tests/test_architecture.py` — 190 lines; the architectural contract (ALLOWED dict + 3 tests + helper functions). Pure stdlib (`ast`, `pathlib`, `pytest`).
- `tests/test_cli_smoke.py` — 63 lines; D14_SUBCOMMANDS list + 2 tests using typer's `CliRunner`.

## Decisions Made

- **stdlib `ast` over `import-linter`** — Same guarantees as the third-party tool, with zero extra trust point and contract co-located with the test. Easier to evolve as the layer set grows.
- **Three sub-tests instead of one monolithic check** — A failure in (a) the generic layer-import contract, (b) the backtest-is-airtight invariant, or (c) the indicators+signals pure-function discipline points to a specific class of regression. Easier to triage.
- **backtest's ALLOWED set is exactly `{"persistence"}`** — Verbatim D-16 (CONTEXT.md). Even `obs` (env-coupled logger) and `config` (API keys) are denied. Backtest reads disk artifacts only; logging is stdlib `logging` if needed.
- **`obs` allowed in every non-backtest ALLOWED set** — Documented as a planner-level expansion of D-16 because CONTEXT.md introduces `obs.py` under Claude's Discretion and structured logging is needed everywhere except the airtight backtest scope.
- **typer `CliRunner` over `subprocess.run([...])`** — Faster, deterministic stdout capture, no PATH/env coupling; matches typer's recommended in-process test harness.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

### Deferred to post-merge gate (parallel-execution worktree state)

This worktree was created from commit `0aa75784` (Plan 01 complete) and is running in parallel with Plan 02 in a sister worktree. As a result, `src/screener/` does not yet exist in this worktree's filesystem. This is the documented parallel-execution mode.

Concrete observation, captured for transparency:

```
$ uv run pytest tests/ -v
collected 3 items / 1 error
ERROR collecting tests/test_cli_smoke.py
  ModuleNotFoundError: No module named 'screener'
```

Both test files are syntactically valid Python (verified via `ast.parse`). The collection error is the expected post-merge concern: once the orchestrator merges this worktree's `tests/` with the sister worktree's `src/screener/`, `pytest` will collect and run cleanly. The post-merge test gate is the source of truth for runtime pass/fail; this worktree's job is to ship correct test-file content, which it has.

Sub-test prediction post-merge (against Plan 02's source tree):

- `test_layer_import_contract` — should PASS (Plan 02 ships only module-docstring `__init__.py` files for all layers and a `cli.py` that imports `screener.obs` (allowed for `cli`, which is the composition root and skipped); no import violations)
- `test_backtest_does_not_import_data_layer` — should PASS (`backtest/__init__.py` is a docstring; no internal imports)
- `test_indicators_signals_pure_no_io_imports` — should PASS (`indicators/__init__.py` and `signals/__init__.py` are docstrings; no I/O imports)
- `test_help_lists_all_d14_subcommands` — should PASS (Plan 02 wires all 9 D-14 subcommands)
- `test_each_subcommand_exits_zero_with_stub_log` — should PASS (Plan 02's `_stub` helper logs `{"command": "<name>", "message": "[stub] <name> not yet implemented", ...}`)

### Coverage gate behavior in Phase 1

The `--cov-fail-under=80` gate in `pyproject.toml` (D-11) covers `src/screener/signals/` and `src/screener/indicators/`. In Phase 1, both of those layers contain only module docstrings (no executable lines) — coverage is trivially satisfied (0/0 statements covered, treated as 100% by pytest-cov). Documented in CONTEXT.md as expected: the gate becomes binding at Phase 3 once real signal/indicator code lands.

### Local mutation check (manual, not committed)

The plan asks for a manual local mutation check: temporarily add `from screener.publishers import report  # noqa` inside `src/screener/indicators/__init__.py` and confirm `test_layer_import_contract` fails. This check is NOT executable in this worktree because `src/screener/indicators/__init__.py` does not yet exist here. Once the worktrees merge, the check can be performed locally; the test logic is structured such that adding `from screener.publishers import X` to any non-cli, non-publishers file in `src/screener/` is correctly detected by `_internal_imports` and will produce a violation in the `forbidden` set.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- Plans 04 (Makefile) and 05 (CI + branch protection) can now wire `uv run pytest` as a status check; the test suite is non-empty and meaningful.
- Phase 2 data-layer work will need to obey the D-16 contract this test enforces — any new module added under `src/screener/data/` must import only from `persistence`, `config`, `obs` (or fail the architecture test).
- Phase 3 indicators/signals work will trigger the `--cov-fail-under=80` gate to become binding, and the `test_indicators_signals_pure_no_io_imports` sub-test will hold the pure-function discipline.
- Plan 04's Makefile `test` target should shell out to `uv run pytest` (no special flags needed; markers and coverage are set in `[tool.pytest.ini_options]`).

## Self-Check: PASSED

- `tests/__init__.py`: FOUND
- `tests/conftest.py`: FOUND (contains `def repo_root` and `def src_screener`)
- `tests/test_architecture.py`: FOUND (contains `ast.parse`; no `import_linter`/`importlinter`; 12 ALLOWED entries)
- `tests/test_cli_smoke.py`: FOUND (contains `from typer.testing import CliRunner`; D14_SUBCOMMANDS has exactly the 9 D-14 names in order)
- Commit `024dc30`: FOUND (Task 1: pytest scaffolding)
- Commit `788d914`: FOUND (Task 2: architecture test)
- Commit `ec85cb3`: FOUND (Task 3: CLI smoke test)
- All four test files are syntactically valid Python (`python3 -c "import ast; ast.parse(open(p).read())"` succeeds for each)

---
*Phase: 01-repo-skeleton-ci-hygiene*
*Plan: 03 — tests-scaffolding*
*Completed: 2026-05-02*
