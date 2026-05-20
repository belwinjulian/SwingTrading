---
phase: 08-github-actions-cron-operations
plan: "04"
subsystem: ci-workflows
tags: [phase-8, wave-2, workflow, heartbeat, ops, ops-03, github-actions, pitfall-8, deviation-d09]

# Dependency graph
requires:
  - phase: 08-01
    provides: "tests/test_phase8_workflow_static.py 17 named pytest.skip skeletons (PINNED_HASH_RE constant, HEARTBEAT_YML + REFRESH_YML path constants)"
  - phase: 08-02
    provides: ".gitignore carve-out `!/data/heartbeat.txt` so the auto-commit step's file_pattern matches a tracked path"
provides:
  - ".github/workflows/heartbeat.yml — weekly Monday 09:00 UTC heartbeat that writes data/heartbeat.txt and auto-commits via stefanzweifel/git-auto-commit-action; defeats GitHub's 60-day idle disable (Pitfall #1)"
  - "7 PASSING heartbeat-specific tests in tests/test_phase8_workflow_static.py (was 7 SKIPPED) — exists+YAML-valid, cron-schedule, contents:write + T-08-overscope-perms guard, SHA pins, data/heartbeat.txt file_pattern, T-08-script-injection regression guard (walks parsed YAML steps), T-08-secrets `set -x` regression guard"
affects:
  - "OPS-03 closed at the workflow + structural-test layer (the workflow needs no further code to close the requirement)"
  - "10 refresh-specific tests in the same test file remain SKIPPED (filled by Plan 08-06 in Wave 3)"
  - "Phase 8 wave-2 dependency for cross-cutting verifier work in 08-VALIDATION.md"

# Tech tracking
tech-stack:
  added:
    - "stefanzweifel/git-auto-commit-action v5.2.0 (SHA b863ae1933cb653a53c021fe36dbb774e1fb9403) — pinned action for the auto-commit step; reused by Plan 08-06 refresh.yml"
  patterns:
    - "Workflow-level `permissions: contents: write` scoped to a single workflow (NOT org-wide PAT) — minimum elevation needed for GITHUB_TOKEN to push data/heartbeat.txt"
    - "Trigger surface restricted to `schedule` + `workflow_dispatch` ONLY (no `push:`, no `pull_request:`) — blocks T-08-commit-loop (heartbeat commit would re-trigger heartbeat otherwise)"
    - "Concurrency block `cancel-in-progress: true` — safe to cancel queue for a trivially-fast weekly job (refresh.yml will use `false` in Plan 08-06 for long cron)"
    - "PyYAML `on:` Norway-cousin: bareword `on:` parses to Python boolean True; tests look up via `data.get(True, data.get('on'))` for dialect compatibility"
    - "Static YAML-parse tests over `run:` blocks — stronger than one-shot CI grep because every future heartbeat.yml edit must pass pytest"

key-files:
  created:
    - ".github/workflows/heartbeat.yml"
  modified:
    - "tests/test_phase8_workflow_static.py"

key-decisions:
  - "**DEVIATION from CONTEXT D-09 — heartbeat permissions: `contents: write` not `contents: read`.** Without write, the auto-commit step fails (`Permission denied to github-actions[bot]`) and no commit lands. Empty commits and tags do not count toward GitHub's 60-day idle rule (Pitfall #8 / RESEARCH Open Question A). The deviation is called out in the plan's `must_haves.truths` and is enforced + regression-guarded by `test_heartbeat_permissions_contents_write` (which also rejects any scope beyond `contents`). Surfaced here for human review during phase verification."
  - "actions/checkout v4.2.2 SHA pin (11bd71901bbe5b1630ceea73d27597364c9af683) reused verbatim from ci.yml — same SHA across all 3 workflows means a single bump-PR covers them all."
  - "stefanzweifel/git-auto-commit-action v5.2.0 SHA pin (b863ae1933cb653a53c021fe36dbb774e1fb9403) — first introduction of this action in the repo; Plan 08-06's refresh.yml will reuse the exact same SHA."
  - "`timeout-minutes: 5` mirrors `no-lookahead-gate.yml` rather than copying refresh.yml's 120-minute envelope — heartbeat is `mkdir + date + git commit`, second-scale work."
  - "`cancel-in-progress: true` is safe here because the heartbeat is idempotent (writes one timestamp); refresh.yml will keep `cancel-in-progress: false` because cold-cache yfinance runs cannot be killed without losing the JSONL failure record."
  - "Added 2 regression-guard tests (`test_heartbeat_no_github_event_interpolation_in_run_blocks` and `test_heartbeat_no_set_x`) beyond the 5 originally drafted in Plan 08-01 — gsd-plan-checker B-02 / W-02 review flagged that the YAML-parse-and-walk shape is meaningfully stronger than the one-shot grep in Task 1's verify command."

requirements-completed: [OPS-03]
requirements-partial: []

# Metrics
duration: 6min
completed: 2026-05-20
---

# Phase 8 Plan 04: Heartbeat Workflow + Static Tests Summary

**Shipped `.github/workflows/heartbeat.yml` (weekly Monday 09:00 UTC; pinned actions/checkout v4.2.2 + stefanzweifel/git-auto-commit-action v5.2.0 by 40-char SHA; writes ISO timestamp to `data/heartbeat.txt` and auto-commits it) and filled 7 heartbeat-specific test bodies in `tests/test_phase8_workflow_static.py`. OPS-03 closed at both layers. EXPLICIT DEVIATION from CONTEXT D-09: heartbeat uses `permissions: contents: write` (not `read`) because the commit MUST land for GitHub's 60-day idle rule — empty commits and tags do not count (Pitfall #8 / RESEARCH Open Question A). The deviation is documented in the plan's must_haves.truths, enforced by `test_heartbeat_permissions_contents_write` (which also forbids any extra scopes via T-08-overscope-perms guard), and surfaced in this summary for human review.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-20T12:52:49Z (executor agent spawn)
- **Completed:** 2026-05-20
- **Tasks:** 2/2
- **Files created:** 1
- **Files modified:** 1

## Accomplishments

- `.github/workflows/heartbeat.yml` created — 43 lines, parses cleanly via `yaml.safe_load`.
  - Schedule: `cron: "0 9 * * 1"` (Monday 09:00 UTC) + `workflow_dispatch:` manual trigger.
  - Permissions: `contents: write` at workflow scope ONLY (no `pull-requests:`, `issues:`, `packages:`, `id-token:`).
  - Concurrency: `${{ github.workflow }}-${{ github.ref }}` group, `cancel-in-progress: true`.
  - Job `heartbeat` on `ubuntu-latest` with `timeout-minutes: 5`.
  - Step 1 — `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2`.
  - Step 2 — `Write heartbeat timestamp`: `mkdir -p data && date -u +%Y-%m-%dT%H:%M:%SZ > data/heartbeat.txt` (pure bash, no env-var echo, no `set -x`).
  - Step 3 — `stefanzweifel/git-auto-commit-action@b863ae1933cb653a53c021fe36dbb774e1fb9403  # v5.2.0` with `commit_message: "chore: weekly heartbeat"` and `file_pattern: data/heartbeat.txt`.
- 7 previously-SKIPPED heartbeat tests in `tests/test_phase8_workflow_static.py` now PASS (verified `7 passed, 10 skipped in 0.09s` on the test file):
  - `test_heartbeat_workflow_exists_and_yaml_valid` — presence, `yaml.safe_load` parse, root-mapping check, `name == "heartbeat"`.
  - `test_heartbeat_cron_schedule` — looks up `on:` via PyYAML's True-bool key fallback, asserts `"0 9 * * 1"` in cron entries.
  - `test_heartbeat_permissions_contents_write` — asserts `permissions.contents == "write"` AND `set(perms.keys()) <= {"contents"}` (T-08-overscope-perms regression guard for D-09 deviation).
  - `test_heartbeat_workflow_pins_actions_by_sha` — `PINNED_HASH_RE.findall` returns >= 2 hits AND both required SHAs (checkout, git-auto-commit) appear verbatim.
  - `test_heartbeat_writes_data_heartbeat_txt` — `data/heartbeat.txt` referenced AND `file_pattern: data/heartbeat.txt` is the auto-commit declaration.
  - `test_heartbeat_no_github_event_interpolation_in_run_blocks` — walks every job's every step's `run:` body via parsed YAML, asserts `"${{ github.event"` substring is absent (T-08-script-injection regression guard).
  - `test_heartbeat_no_set_x` — walks parsed YAML steps, asserts `"set -x"` substring is absent in any `run:` block (T-08-secrets regression guard).
- 10 refresh-specific tests in the same file remain SKIPPED with the original Plan 08-06 reason ("body filled by Plan 08-06 (Wave 3)") — `grep -c "pytest.skip" tests/test_phase8_workflow_static.py` returns 10.
- Full regression run: `pytest -m "not slow" --no-cov`: **231 passed, 16 skipped, 0 failures** (0 new failures introduced).
- FND-04 no-look-ahead gate still green (this plan touched no `signals/` or `backtest/`).
- Threat-model mitigations verified via grep:
  - `grep -cE "github\.event\." .github/workflows/heartbeat.yml` returns 0 (T-08-script-injection mitigation).
  - `grep -c "push:" .github/workflows/heartbeat.yml` returns 0 (T-08-commit-loop mitigation).
  - `grep -c "secrets\." .github/workflows/heartbeat.yml` returns 0 (T-08-secrets — heartbeat needs no secrets).
  - `grep -c "set -x" .github/workflows/heartbeat.yml` returns 0 (T-08-secrets — no command-trace).
  - `grep -c "11bd71901bbe5b1630ceea73d27597364c9af683" .github/workflows/heartbeat.yml` returns 1 (T-08-supply-chain — checkout pin).
  - `grep -c "b863ae1933cb653a53c021fe36dbb774e1fb9403" .github/workflows/heartbeat.yml` returns 1 (T-08-supply-chain — git-auto-commit pin).

## Deviation from CONTEXT D-09 — REQUIRES HUMAN REVIEW

> **This section satisfies the plan's `<output>` directive ("the summary MUST include a top-level 'Deviation from CONTEXT D-09' section calling out that heartbeat uses `contents: write` (not `contents: read`), with the Pitfall #8 / Open Question A rationale, for human review during phase verification").**

CONTEXT.md decision D-09 reads (paraphrased): "CI and heartbeat stay `contents: read`." **Plan 08-04 deliberately deviates from this rule for `heartbeat.yml`.** D-09 remains in force for `ci.yml` and `no-lookahead-gate.yml` (both verified `contents: read`).

### Why the deviation is necessary

- The 60-day idle disable (Pitfall #1) measures **real commit activity on the default branch**. Empty commits, tags, and workflow-only changes do **not** count — confirmed by RESEARCH §Open Question A citing GitHub community discussion #57858 and Pitfall #8.
- The heartbeat workflow's purpose is to **produce a real commit weekly** so the nightly refresh.yml cron is never auto-disabled.
- With `contents: read`, the auto-commit step fails with "Permission denied to github-actions[bot]" — the commit never lands, the workflow runs but accomplishes nothing, and the 60-day defense silently does not work.
- The minimum elevation needed is `contents: write` (no `pull-requests:`, no `issues:`, no `packages:`, no `id-token:`). The GITHUB_TOKEN at this scope cannot modify branch protection, install apps, or write to packages.

### How the deviation is contained

- **Scoped to the workflow**, not org-wide or PAT-based. Each workflow declares its own `permissions:` block; only `heartbeat.yml` gets `write`.
- **Regression-guarded at pytest time** by `test_heartbeat_permissions_contents_write`, which asserts both `contents == "write"` AND `set(perms.keys()) <= {"contents"}`. Any future PR that adds e.g. `id-token: write` to heartbeat fails this test (T-08-overscope-perms).
- **Trigger surface restricted** to `schedule` + `workflow_dispatch` (no `push:` / `pull_request:`), preventing the heartbeat commit from re-triggering itself (T-08-commit-loop).
- **No secrets used.** `grep -c "secrets\." .github/workflows/heartbeat.yml` returns 0; the GITHUB_TOKEN is auto-provided by Actions and scoped per workflow.

### Action requested from human reviewer

- [ ] Acknowledge the deviation during phase-8 verification (or, if you want D-09 enforced strictly, request a CONTEXT.md amendment so D-09 reads: *"CI stays `contents: read`. Heartbeat uses `contents: write` because empty commits don't count toward the 60-day rule (Pitfall #8)."*).

The recommended outcome is a CONTEXT.md amendment that captures the lesson learned, but the workflow as-shipped is correct for OPS-03 either way.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create `.github/workflows/heartbeat.yml` (OPS-03 / D-11; permissions deviation from D-09) | e6e696f | `.github/workflows/heartbeat.yml` (created) |
| 2 | Fill heartbeat static test bodies in `tests/test_phase8_workflow_static.py` (7 tests SKIPPED → PASSING) | 706ed2f | `tests/test_phase8_workflow_static.py` (modified) |

## Deviations from Plan

None beyond the one explicitly mandated by the plan itself (the D-09 permissions deviation, documented above and called out in `must_haves.truths`). Both tasks executed verbatim per the plan's `<action>` blocks.

### Auto-fixed Issues

None — no auto-fixes triggered (Rules 1–3 unused). The heartbeat.yml content was specified verbatim with pre-verified 40-char SHAs; no bugs, missing functionality, or blocking issues surfaced during execution.

## Authentication Gates

None — pure file edits + commits. No external API calls, no auth required.

## Verification Evidence

### Task 1 — heartbeat.yml structural checks

```
$ grep -c "0 9 \* \* 1" .github/workflows/heartbeat.yml          # 1
$ grep -c "contents: write" .github/workflows/heartbeat.yml      # 1
$ grep -c "11bd71901bbe5b1630ceea73d27597364c9af683" .github/workflows/heartbeat.yml  # 1
$ grep -c "b863ae1933cb653a53c021fe36dbb774e1fb9403" .github/workflows/heartbeat.yml  # 1
$ grep -cE "github\.event\." .github/workflows/heartbeat.yml     # 0
$ grep -cE "^on:" .github/workflows/heartbeat.yml                 # 1
$ grep -c "push:" .github/workflows/heartbeat.yml                 # 0
$ grep -c "data/heartbeat.txt" .github/workflows/heartbeat.yml   # 4 (>=2 required)
$ grep -c "timeout-minutes: 5" .github/workflows/heartbeat.yml   # 1
$ grep -c "set -x" .github/workflows/heartbeat.yml               # 0
$ grep -c "secrets\." .github/workflows/heartbeat.yml            # 0
$ .venv/bin/python3 -c "import yaml; yaml.safe_load(open('.github/workflows/heartbeat.yml'))"
  (parsed: dict; keys: ['name', True, 'permissions', 'concurrency', 'jobs'])
```

### Task 2 — pytest results

```
$ .venv/bin/python3 -m pytest tests/test_phase8_workflow_static.py -v --no-cov
...
tests/test_phase8_workflow_static.py::test_heartbeat_workflow_exists_and_yaml_valid PASSED [ 64%]
tests/test_phase8_workflow_static.py::test_heartbeat_cron_schedule PASSED                 [ 70%]
tests/test_phase8_workflow_static.py::test_heartbeat_permissions_contents_write PASSED    [ 76%]
tests/test_phase8_workflow_static.py::test_heartbeat_workflow_pins_actions_by_sha PASSED  [ 82%]
tests/test_phase8_workflow_static.py::test_heartbeat_writes_data_heartbeat_txt PASSED     [ 88%]
tests/test_phase8_workflow_static.py::test_heartbeat_no_github_event_interpolation_in_run_blocks PASSED  [ 94%]
tests/test_phase8_workflow_static.py::test_heartbeat_no_set_x PASSED                      [100%]

======================== 7 passed, 10 skipped in 0.09s =========================
```

### Full regression

```
$ .venv/bin/python3 -m pytest -m "not slow" --no-cov -q
... 231 passed, 16 skipped, 4 warnings in 125.14s (0:02:05)
```

## Success Criteria Status

| # | Criterion | Status |
|---|-----------|--------|
| 1 | heartbeat.yml ships with cron `0 9 * * 1`, `workflow_dispatch`, `permissions: contents: write`, `timeout-minutes: 5`, `cancel-in-progress: true` | ✅ verified |
| 2 | heartbeat.yml pins actions/checkout v4.2.2 + stefanzweifel/git-auto-commit-action v5.2.0 by SHA | ✅ verified |
| 3 | heartbeat.yml writes `data/heartbeat.txt` and commits it via `file_pattern: data/heartbeat.txt` | ✅ verified |
| 4 | heartbeat.yml has NO `${{ github.event.* }}` interpolation, NO `push:` trigger, NO `set -x` | ✅ verified |
| 5 | All 7 heartbeat tests in `tests/test_phase8_workflow_static.py` pass (5 original + 2 added per gsd-plan-checker B-02) | ✅ verified (7/7 PASSED, 10 refresh tests remain SKIPPED) |
| 6 | D-09 permissions deviation surfaced in plan + this SUMMARY for human review | ✅ verified (see "Deviation from CONTEXT D-09" section above) |

## Threat Flags

None — no new security surface introduced beyond what the threat model already covered. All 5 STRIDE entries (`T-08-secrets`, `T-08-script-injection`, `T-08-supply-chain`, `T-08-overscope-perms`, `T-08-commit-loop`) verified by grep + pytest as documented in the plan's `<threat_model>`.

## Known Stubs

None — `.github/workflows/heartbeat.yml` is fully wired (no placeholder values, no TODO/FIXME, no empty `run:` blocks, no hardcoded fallback timestamps).

## TDD Gate Compliance

N/A — this plan has `type: execute` (not `type: tdd`). No RED/GREEN/REFACTOR gate sequence is required. Tests were filled alongside the implementation in Task 2.

## Self-Check: PASSED

- `[ -f .github/workflows/heartbeat.yml ]` → FOUND
- `[ -f tests/test_phase8_workflow_static.py ]` → FOUND
- `git log --oneline --all | grep -q e6e696f` → FOUND
- `git log --oneline --all | grep -q 706ed2f` → FOUND
- `pytest tests/test_phase8_workflow_static.py` → 7 passed / 10 skipped (no failures)
- `pytest -m "not slow"` → 231 passed / 16 skipped (no failures, no regressions)
