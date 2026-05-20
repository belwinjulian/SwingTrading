---
phase: 08-github-actions-cron-operations
plan: "01"
subsystem: testing
tags: [phase-8, wave-0, foundation, run-log, test-scaffolding, ops, ops-05, jsonl, typeddict]

# Dependency graph
requires:
  - phase: 04-trend-template-composite-skeleton-first-report
    provides: publishers/snapshot.py module-shape exemplar (module docstring + `from __future__ import annotations` + module-level structlog logger)
  - phase: 06-pattern-detection-full-signal-stack-playbook-tagging
    provides: D-24 test_subcommand_surface_locked test (9-subcommand byte-level lock) — Plan 08-01 must not break it
provides:
  - publishers/run_log.py module skeleton (RunLogRecord TypedDict + _RUNS_PATH constant + append_record() stub + _cli_failure_entry() stub + `python -m` entrypoint)
  - 5 named pytest.skip skeletons in tests/test_run_log.py (OPS-05 schema, fsync, success/failure paths) — bodies for Plan 08-03
  - 4 named pytest.skip skeletons in tests/test_phase8_gitignore.py (D-04 + D-11 + Pitfall #4 carve-outs) — bodies for Plan 08-02
  - 17 named pytest.skip skeletons in tests/test_phase8_workflow_static.py (refresh.yml + heartbeat.yml structural assertions, T-08-* threat mitigations) — bodies for Plans 08-04 + 08-06
  - 2 named pytest.skip skeletons in tests/test_pipeline_emits_run_log.py (pipeline -> runs.jsonl integration) — body for Plan 08-05
  - Stable file/test surface for Plans 08-02..08-06 to fill bodies into (Nyquist sampling pattern)
affects: [phase-8 Plan 08-02 gitignore carve-outs, Plan 08-03 run_log bodies, Plan 08-04 heartbeat workflow, Plan 08-05 pipeline integration, Plan 08-06 refresh workflow]

# Tech tracking
tech-stack:
  added: []  # No new third-party deps — structlog already pinned at 25.5.x
  patterns:
    - "Pattern (existing): publishers/ module shape — module docstring + `from __future__ import annotations` + module-level `log = structlog.get_logger(__name__)`"
    - "Pattern (new): module-level `_RUNS_PATH: Path = Path(\"data/runs.jsonl\")` constant for monkeypatch.setattr test redirection (deviates from persistence._<name>_dir() helper pattern by design — D-23 isolation requires no Settings dependency)"
    - "Pattern (new): pytest.skip body-stub convention with explicit `body filled by Plan 08-XX (Wave N)` citation in skip reason — decoder-level discoverability across the 4 new test files"
    - "Pattern (existing): REPO_ROOT = Path(__file__).resolve().parents[1] for filesystem-relative test fixtures (mirrors tests/test_ci_ema_grep_gate.py:14)"
    - "Pattern (existing): three-block import order (stdlib / third-party / from screener.*) preceded by Wave marker comment"
  patterns-established:
    - "Module-level path constant (NOT Settings-bound) for test monkeypatch targets in publishers/* modules that must remain stdlib-only"
    - "Wave: N marker comment preamble on every Phase 6+ test file (encodes which downstream plan fills the body)"

key-files:
  created:
    - src/screener/publishers/run_log.py  # OPS-05 module skeleton (108 lines)
    - tests/test_run_log.py  # 5 OPS-05 skeletons (68 lines)
    - tests/test_phase8_gitignore.py  # 4 D-04/D-11/Pitfall #4 skeletons (51 lines)
    - tests/test_phase8_workflow_static.py  # 17 refresh.yml + heartbeat.yml + T-08-* skeletons (158 lines)
    - tests/test_pipeline_emits_run_log.py  # 2 pipeline integration skeletons (50 lines)
  modified: []  # Plan 08-01 is foundation-only — no existing files touched (D-24 CLI surface unchanged)

key-decisions:
  - "Module-level _RUNS_PATH constant in publishers/run_log.py (NOT a getattr-on-Settings helper) so tests can monkeypatch.setattr without bouncing through pydantic-settings @lru_cache"
  - "publishers/run_log.py imports stdlib + structlog ONLY (no screener.* deps) — D-23 architecture isolation; keeps the writer minimal and independent of Settings"
  - "All test skeletons use pytest.skip with explicit body-filling plan citation (e.g., 'body filled by Plan 08-03 (Wave 1)') so future executors can route skeletons to owners"
  - "Function signatures in test skeletons already declare fixtures (tmp_path, monkeypatch) — downstream plans only fill bodies, never touch signatures"

patterns-established:
  - "Pattern: module-level Path constant for monkeypatch test redirection (publishers/run_log.py::_RUNS_PATH)"
  - "Pattern: pytest.skip body-stub with `body filled by Plan 08-XX (Wave N)` citation as decoder convention"
  - "Pattern: `python -m screener.publishers.<module> {arg}` __main__ entrypoint for workflow-callable Python that does not warrant a typer subcommand (preserves D-24 9-subcommand lock)"

requirements-completed: []  # OPS-05 is partial — TypedDict + signatures shipped; bodies in Plan 08-03

# Metrics
duration: 8min
completed: 2026-05-20
---

# Phase 8 Plan 01: Wave 0 Foundation Summary

**Wave 0 scaffolding for Phase 8 — `publishers/run_log.py` module skeleton (RunLogRecord TypedDict + `_RUNS_PATH` constant + 2 stub functions + `python -m` entrypoint) plus 28 named `pytest.skip` test skeletons across 4 new test files, enabling Plans 08-02..08-06 to fill bodies into a stable surface.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-20T12:21:43Z
- **Completed:** 2026-05-20T12:30:10Z
- **Tasks:** 5
- **Files created:** 5
- **Files modified:** 0

## Accomplishments

- Shipped `src/screener/publishers/run_log.py` with the OPS-05 record schema (`RunLogRecord` TypedDict — 8 fields), `_RUNS_PATH` module-level constant (Path("data/runs.jsonl")), `append_record()` and `_cli_failure_entry()` stub functions raising `NotImplementedError("Plan 08-03 fills this body")`, plus `if __name__ == "__main__"` entrypoint for `python -m screener.publishers.run_log {success|failure}`.
- Shipped 5 named `pytest.skip` skeletons in `tests/test_run_log.py` covering OPS-05 schema completeness, `append_record` flush+fsync semantics (Pitfall #5), JSON round-trip, failure-record env reading, and SC#5 status='failed' shape.
- Shipped 4 named `pytest.skip` skeletons in `tests/test_phase8_gitignore.py` enforcing D-04 (`data/runs.jsonl` carve-out), D-11 (`data/heartbeat.txt` carve-out), Pitfall #4 (`reports/*.md` carve-out so OPS-02 isn't silently blocked), and stale-line removal at repo root.
- Shipped 17 named `pytest.skip` skeletons in `tests/test_phase8_workflow_static.py` enforcing both `refresh.yml` (10 skeletons: cron, workflow_dispatch, pinned actions, perms, timeout, cancel-in-progress, no-${{github.event.*}} interpolation, two-step commit, file-pattern coverage) and `heartbeat.yml` (7 skeletons: yaml-valid, cron, perms, pinned actions, heartbeat.txt write, no-${{github.event.*}} interpolation, no-`set -x`) — all five T-08-* threat-model mitigations have skeleton enforcement in place.
- Shipped 2 named `pytest.skip` skeletons in `tests/test_pipeline_emits_run_log.py` for the pipeline -> runs.jsonl integration path (success record exists with status='success' + every OPS-05 field).
- D-24 9-subcommand CLI surface LOCK is intact: `tests/test_cli_smoke.py::test_subcommand_surface_locked` still passes.
- D-23 architecture isolation is intact: `grep -v '^#' src/screener/publishers/run_log.py | grep -c "from screener"` returns 0.
- FND-04 no-look-ahead gate still passes (`tests/test_backtest_no_lookahead.py::* 2 passed in 5.17s`).
- Full quick-suite green: `215 passed, 32 skipped, 0 failed` (was 187 passed + 4 skipped before Plan 08-01; the 28 new skeletons account for the skipped delta).

## Task Commits

Each task was committed atomically. The first commit (`d000bb1`) is a cherry-pick — see "Deviations from Plan" for the rationale.

1. **Task 1: Create publishers/run_log.py with TypedDict + signatures + __main__ scaffold** — `d000bb1` (feat) — also exists at `47d0a30` on `main` due to a recovery deviation; see "Deviations" below.
2. **Task 2: Create tests/test_run_log.py with 5 named pytest.skip skeletons (OPS-05)** — `97672f6` (test)
3. **Task 3: Create tests/test_phase8_gitignore.py with 4 named pytest.skip skeletons (OPS-02 / OPS-05 / D-04 / D-11)** — `bd5a8c3` (test)
4. **Task 4: Create tests/test_phase8_workflow_static.py with 17 named pytest.skip skeletons (OPS-01..04 + T-08-*)** — `034b17c` (test)
5. **Task 5: Create tests/test_pipeline_emits_run_log.py with 2 named pytest.skip skeletons (OPS-05 integration)** — `441255e` (test)

## Files Created/Modified

- `src/screener/publishers/run_log.py` — OPS-05 module skeleton: `RunLogRecord` TypedDict, module-level `_RUNS_PATH: Path` constant, `append_record()` + `_cli_failure_entry()` stubs (raise `NotImplementedError("Plan 08-03 fills this body")`), `if __name__ == "__main__"` entrypoint for `python -m screener.publishers.run_log {success|failure}`. Stdlib + structlog only — no screener.* imports (D-23 isolation).
- `tests/test_run_log.py` — 5 named pytest.skip skeletons keyed to Plan 08-03 (Wave 1) body fills. Imports stdlib only (no module-under-test imports yet) so the file collects cleanly without depending on Plan 08-03 having shipped.
- `tests/test_phase8_gitignore.py` — 4 named pytest.skip skeletons keyed to Plan 08-02 (Wave 1) body fills. Uses the REPO_ROOT = Path(__file__).resolve().parents[1] idiom from tests/test_ci_ema_grep_gate.py:14.
- `tests/test_phase8_workflow_static.py` — 17 named pytest.skip skeletons keyed to Plans 08-04 (heartbeat — 7) + 08-06 (refresh — 10). Defines `PINNED_HASH_RE` mirroring the existing ci.yml convention (`owner/repo@<40-hex>  # vX.Y.Z`).
- `tests/test_pipeline_emits_run_log.py` — 2 named pytest.skip skeletons keyed to Plan 08-05 (Wave 2) body fills. Defers all `screener.publishers.pipeline` imports to body-fill time.

## Decisions Made

- **Module-level `_RUNS_PATH` constant (NOT a `_runs_path()` Settings helper)**: tests need to redirect writes via `monkeypatch.setattr("screener.publishers.run_log._RUNS_PATH", tmp_path / "runs.jsonl")` without bouncing through `pydantic-settings`'s `@lru_cache(get_settings)`. This deviates from `persistence.py`'s `_<name>_dir()` helper pattern by design — documented inline at the constant.
- **publishers/run_log.py imports stdlib + structlog only (no `from screener.*`)**: D-23 architecture lock allows `publishers/` to import `persistence/config/obs`, but the run-log writer doesn't NEED any of those (the caller constructs the record dict; this module only writes). Keeping the import surface minimal protects the monkeypatch target.
- **`raise NotImplementedError("Plan 08-03 fills this body")` body for stubs**: lets `import screener.publishers.run_log` succeed AND `from screener.publishers.run_log import append_record, _cli_failure_entry, RunLogRecord, _RUNS_PATH` succeed, so Plan 08-03 test bodies can reference symbols immediately. Plan 08-03 swaps the body, not the signature.
- **`pytest.skip` reason strings cite the downstream plan**: every skeleton's skip reason is "body filled by Plan 08-XX (Wave N)" — turns the skeleton list into a self-documenting routing table.

## Deviations from Plan

### Procedural deviation (NOT a code-change auto-fix): wrong-worktree commit and cherry-pick recovery

**1. [Procedural — Worktree handling] Task 1 was committed on the wrong branch (`main`) and recovered via cherry-pick onto the worktree branch.**

- **Found during:** Task 1 (Create publishers/run_log.py) commit step.
- **Issue:** I ran `cd /Users/belwinjulian/SwingTrading && git commit ...` (the primary repo path) instead of operating in the worktree directory `/Users/belwinjulian/SwingTrading/.claude/worktrees/agent-a78a08bf0ce00c4c1`. The startup `<worktree_branch_check>` step had correctly placed me on `worktree-agent-a78a08bf0ce00c4c1`, but my per-command `cd` to the primary repo overrode that, and the commit (`47d0a30`) landed on `main`. The Bash tool's note that I should "avoid usage of `cd`" applies precisely to this case.
- **Fix:**
  1. Confirmed the file was missing from the worktree filesystem (`ls /Users/belwinjulian/SwingTrading/.claude/worktrees/agent-a78a08bf0ce00c4c1/src/screener/publishers/` showed only the pre-existing modules).
  2. Verified the worktree branch HEAD via `git -C <worktree> rev-parse --abbrev-ref HEAD` → `worktree-agent-a78a08bf0ce00c4c1`.
  3. Cherry-picked `47d0a30` onto the worktree branch from within the worktree: result is commit `d000bb1` (same tree, same message, attached to the correct branch).
  4. All subsequent commits (Tasks 2-5) used `git -C /Users/belwinjulian/SwingTrading/.claude/worktrees/agent-a78a08bf0ce00c4c1 ...` to pin the working directory and avoid the cwd-reset bug.
- **Files modified by the deviation:** None (recovery is a cherry-pick; the source file content is identical to what Task 1 specified).
- **Verification:** `git -C <worktree> log --oneline -6` shows the 5 task commits + cherry-picked Task 1 attached to the worktree branch. The worktree filesystem now contains `src/screener/publishers/run_log.py` with the correct content.

### Outstanding concern — surfaced to orchestrator

**Phantom commit on `main` (`47d0a30`):** the wrong-branch commit is still present at the tip of `main`. Per the `<destructive_git_prohibition>` block in this agent's instructions ("**DO NOT** 'recover' by force-rewinding the protected ref — that silently destroys concurrent commits in multi-active scenarios"), I did NOT self-heal `main` via `git update-ref` / `git reset --hard HEAD~1`. The protocol says HALT and surface a blocker (#2924). The orchestrator (or the user) should rewind `main` to `0830f68` before re-running other agents in this wave; otherwise the same content will appear twice in the main-branch history when the worktree merges back. The cherry-picked content on the worktree branch (`d000bb1`) is the canonical landing; `47d0a30` on `main` is a phantom that must be reverted by the orchestrator.

---

**Total deviations:** 1 procedural (no code-change auto-fixes via Rules 1-3; no architectural changes via Rule 4).
**Impact on plan:** The plan-as-written executed correctly — all 5 tasks shipped exact-content files matching the plan's `<action>` blocks. The deviation is a process error in worktree directory handling, recovered via cherry-pick. No scope creep, no skipped done-criteria.

## Issues Encountered

- **Stale venv shebang:** `.venv/bin/pytest` shebang pointed at `/Users/belwinjulian/Desktop/SwingTrading/.venv/bin/python3` (a path that no longer exists). Worked around by invoking `python -m pytest` directly through `.venv/bin/python3`. Pre-existing repo state — not caused by Plan 08-01 — and not in scope for this plan.
- **`uv run pytest` failed** with "Failed to spawn: `pytest`". Same root cause as the stale shebang. Worked around with the same `python -m pytest` invocation.

## User Setup Required

None — no external service configuration needed for Wave 0 scaffolding. All 28 skeleton tests skip cleanly; bodies in Plans 08-02..08-06 will require GitHub Actions context that lands automatically when those plans run.

## Self-Check

**Check 1 — files exist (from worktree root):**
- `src/screener/publishers/run_log.py` → FOUND (4193 bytes)
- `tests/test_run_log.py` → FOUND
- `tests/test_phase8_gitignore.py` → FOUND
- `tests/test_phase8_workflow_static.py` → FOUND
- `tests/test_pipeline_emits_run_log.py` → FOUND

**Check 2 — commits exist on worktree branch (`git log --oneline`):**
- `d000bb1` (Task 1 cherry-pick) → FOUND
- `97672f6` (Task 2) → FOUND
- `bd5a8c3` (Task 3) → FOUND
- `034b17c` (Task 4) → FOUND
- `441255e` (Task 5) → FOUND

**Check 3 — done criteria green:**
- `class RunLogRecord(TypedDict` count: 1 (expected 1)
- `_RUNS_PATH: Path = Path` count: 1 (expected 1)
- `def append_record(` count: 1 (expected 1)
- `def _cli_failure_entry(` count: 1 (expected 1)
- `if __name__ == "__main__":` count: 1 (expected 1)
- `from screener` (non-comment) count: 0 (D-23 isolation; expected 0)
- `raise NotImplementedError` count: 2 (expected 2)
- Phase 8 skeleton tests collected: 28 (5 + 4 + 17 + 2 — expected ≥ 28)
- `tests/test_cli_smoke.py::test_subcommand_surface_locked`: PASSED (D-24 lock intact)
- `tests/test_backtest_no_lookahead.py`: 2 PASSED (FND-04 gate intact)
- Quick suite: 215 passed, 32 skipped, 0 failed

## Self-Check: PASSED

## Next Plan Readiness

- **Plan 08-02 (Wave 1, gitignore carve-outs)** can begin immediately. Skeletons in `tests/test_phase8_gitignore.py` are named and ready to receive bodies.
- **Plan 08-03 (Wave 1, run_log bodies)** can begin immediately. `publishers/run_log.py` exposes `append_record`, `_cli_failure_entry`, `RunLogRecord`, and `_RUNS_PATH` as stable import targets; `tests/test_run_log.py` skeletons are routed to Plan 08-03.
- **Plan 08-04 (Wave 1, heartbeat workflow)** can begin immediately. 7 heartbeat skeletons in `tests/test_phase8_workflow_static.py` are named and routed to Plan 08-04.
- **Plan 08-05 (Wave 2, pipeline integration)** depends on Plan 08-03 closing first (needs the real `append_record` body to assert against). Skeletons in `tests/test_pipeline_emits_run_log.py` are named and routed.
- **Plan 08-06 (Wave 3, refresh workflow)** can begin once Plans 08-02 + 08-03 + 08-05 close. 10 refresh skeletons in `tests/test_phase8_workflow_static.py` are named and routed.
- **Blocker for orchestrator:** the phantom commit `47d0a30` on `main` must be rewound by the orchestrator/user before the worktree merges back; otherwise the same Task 1 content will land twice in main-branch history. See "Deviations from Plan" above.

---
*Phase: 08-github-actions-cron-operations*
*Plan: 01*
*Completed: 2026-05-20*
