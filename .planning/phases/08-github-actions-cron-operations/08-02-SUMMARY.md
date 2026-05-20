---
phase: 08-github-actions-cron-operations
plan: "02"
subsystem: infra
tags: [phase-8, wave-1, gitignore, carve-out, ops, ops-02, ops-03, ops-05, git, ci]

# Dependency graph
requires:
  - phase: 08-01
    provides: "tests/test_phase8_gitignore.py 4 named pytest.skip skeletons (Wave 0 foundation)"
provides:
  - ".gitignore carve-outs for data/runs.jsonl, data/heartbeat.txt, reports/*.md (the file_pattern contract for stefanzweifel/git-auto-commit-action used by refresh.yml + heartbeat.yml downstream)"
  - "Removal of obsolete root-level /runs.jsonl line (D-04 relocation)"
  - "4 PASSING tests in tests/test_phase8_gitignore.py asserting each carve-out resolves to git check-ignore exit-code 1"
affects: ["08-04 heartbeat", "08-06 refresh.yml auto-commit", "phase-8 OPS-02 success-path commit", "phase-8 OPS-03 heartbeat workflow", "phase-8 OPS-05 run-log observability"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "File-specific carve-outs (`!/data/<file>`) over directory wildcards — preserves the threat-model T-08-overscope mitigation by NOT introducing `!/data/*`"
    - "Phase-tagged comment blocks in .gitignore (`# Phase 8 (OPS-XX / D-YY):`) mirroring the Phase 6/7 style for change traceability"

key-files:
  created: []
  modified:
    - ".gitignore"
    - "tests/test_phase8_gitignore.py"

key-decisions:
  - "File-specific carve-outs (`!/data/runs.jsonl`, `!/data/heartbeat.txt`) — never `!/data/*` — to prevent accidentally allowing secrets through (T-08-overscope mitigation)"
  - "Retain `import pytest` even after removing pytest.skip stubs — matches the exact code block in the plan's <action> spec (no deviation from authoritative source)"
  - "Replace `/reports/` with `!/reports/` + `!/reports/*.md` pair (mirrors `!/data/universe/` + `!/data/universe/.gitkeep` idiom) rather than a single `!/reports/*.md` line; this lets the `reports/` directory itself be tracked plus all top-level *.md files"

patterns-established:
  - "Pattern: gitignore carve-out doc tests — use `subprocess.run([\"git\", \"-C\", REPO_ROOT, \"check-ignore\", \"-q\", path])` returning rc==1 for NOT-ignored assertions; mirrors test_ci_ema_grep_gate.py:_run_grep shape"
  - "Pattern: assertion messages include `{rc!r}` for diagnostic clarity and reference both the missing carve-out and the planning doc (08-RESEARCH.md / 08-CONTEXT.md) where the rationale lives"

requirements-completed: [OPS-02, OPS-03, OPS-05]

# Metrics
duration: 8min
completed: 2026-05-20
---

# Phase 8 Plan 02: gitignore Carve-Outs (D-04 + D-11 + Pitfall #4) Summary

**Three Phase 8 gitignore carve-outs (`!/data/runs.jsonl`, `!/data/heartbeat.txt`, `!/reports/*.md`) plus removal of the obsolete root-level `/runs.jsonl` line — enabling the OPS-02/OPS-03/OPS-05 auto-commit steps in downstream workflows to actually pick up their target files; 4 previously-skipped tests now pass.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-20 (executor agent spawn)
- **Completed:** 2026-05-20
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- `.gitignore` carve-outs added so `data/runs.jsonl`, `data/heartbeat.txt`, and `reports/<date>.md` are all NOT ignored by git (verified: `git check-ignore -q` returns exit-code 1 for each).
- Obsolete root-level `/runs.jsonl` line REMOVED (D-04 relocation — file now lives at `data/runs.jsonl`).
- `tests/test_phase8_gitignore.py`: 4 previously-skipped tests now PASS (helper `_check_ignore()` added, all bodies filled with `git check-ignore -q` subprocess assertions and diagnostic messages).
- Pitfall #4 fix locked in: the pre-Phase-8 `/reports/` line that silently blocked OPS-02's auto-commit is replaced with `!/reports/` + `!/reports/*.md`.
- Zero regressions: pre-existing carve-outs (universe, ohlcv splits, snapshots, fundamentals/insider/pattern_audit .gitkeeps, journal.sqlite, .env) preserved verbatim; full quick suite 219 passed / 28 skipped / 0 failed; FND-04 no-lookahead test still passes (2 passed).
- Threat-model T-08-secrets + T-08-overscope-perms mitigations honored: all carve-outs are file-specific (no `!/data/*` wildcard), `.env` still ignored (rc=0).

## Task Commits

Each task was committed atomically on branch `worktree-agent-aaac8c1272fc6b219`:

1. **Task 1: Update .gitignore with three Phase 8 carve-outs** — `5686cfe` (chore)
   - Edit 1: removed `/runs.jsonl` line.
   - Edit 2: replaced `/reports/` with `!/reports/` + `!/reports/*.md` (commented).
   - Edit 3: inserted `!/data/runs.jsonl` + `!/data/heartbeat.txt` block (commented) after `!/data/snapshots/.gitkeep`.

2. **Task 2: Fill bodies of tests/test_phase8_gitignore.py** — `249e541` (test)
   - Added `_check_ignore()` helper (mirrors `tests/test_ci_ema_grep_gate.py:_run_grep`).
   - Filled all 4 test bodies with rc==1 assertions + diagnostic messages.
   - All 4 now PASS (verified by `pytest tests/test_phase8_gitignore.py -v`).

## Files Created/Modified

- `.gitignore` — added Phase 8 carve-out block (`!/data/runs.jsonl`, `!/data/heartbeat.txt`), removed `/runs.jsonl`, replaced `/reports/` with `!/reports/` + `!/reports/*.md` (commented per Phase 8 phase-tag style). Net: +14 / −2 lines.
- `tests/test_phase8_gitignore.py` — bodies of 4 `pytest.skip(...)` stubs replaced with `_check_ignore()` calls + assertions. Net: +72 / −25 lines.

## Decisions Made

- **File-specific carve-outs only** — no `!/data/*` wildcard. The threat model (T-08-overscope) explicitly flags wildcard scope as an Information-Disclosure risk; using `!/data/runs.jsonl` and `!/data/heartbeat.txt` individually keeps `/data/*` as the blanket ignore and minimizes the carve-out surface to two named files.
- **Retain `import pytest`** even though the file no longer uses `pytest.skip()` — matches the exact code block in the plan's `<action>` spec bytewise. (If ruff later flags this as unused, that would be a separate Plan-08-02-followup; the plan-spec code is authoritative for this commit.)
- **`!/reports/` + `!/reports/*.md` pair** (not just `!/reports/*.md`) — mirrors the `!/data/universe/` + `!/data/universe/.gitkeep` idiom from Phase 2. The directory un-ignore is necessary so git will descend into `reports/` at all; the file pattern is what actually allows the `.md` artifacts past `.gitignore`.
- **No `add_options: "-f"`** anywhere — plan explicitly forbids it per Pitfall #4 (it would hide what's committed from reviewers); carve-outs are the only mechanism.

## Deviations from Plan

None — plan executed exactly as written. The reference code block in `<task>` Task 2 `<action>` was applied bytewise. One minor done-criterion inconsistency was observed but is not a deviation in execution:

- **Observation (not a deviation):** Task 2 done criterion says `grep -c "_check_ignore" tests/test_phase8_gitignore.py` should return `>= 5` (helper def + 3 call sites + at least 1 assertion message). The actual count from the reference code block is 4 (1 def + 3 call sites). The assertion messages in the plan's reference code reference `!/data/runs.jsonl` / `!/data/heartbeat.txt` / carve-out paths, NOT the helper name `_check_ignore`. My implementation matches the plan's reference code bytewise. The 4-vs-5 mismatch lives in the plan, not the implementation. Flagging here for the verifier's awareness.

## Issues Encountered

- None of substance. The `tests/test_phase8_gitignore.py -v` run reported a `Coverage failure: total of 0 is less than fail-under=80` warning when run in isolation — this is expected behavior for any single-file pytest invocation against this repo (the 80% threshold is for whole-suite runs). The tests themselves all PASSED. Confirmed with `pytest -m "not slow"` whole-suite run: 219 passed, 28 skipped, 0 failed, no coverage errors.

## Threat Model Compliance

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-08-secrets | mitigate | ✓ `.env` ignore preserved (line 28); carve-outs are non-secret artifacts only |
| T-08-overscope-perms (carve-out scope) | mitigate | ✓ File-specific carve-outs only; `grep -c "^!/data/\*$" .gitignore` = 0 (no wildcard `!/data/*` introduced) |
| T-08-script-injection / T-08-supply-chain / T-08-commit-loop / T-08-overscope-perms | accept | ✓ No workflow YAML, action, or permission grant in this plan (carve-outs only) |

## User Setup Required

None — no external service configuration required.

## Verification Snapshot

Final state post-Task 2:

```text
data/runs.jsonl                    rc=1 (NOT ignored — D-04 / OPS-05)  ✓
data/heartbeat.txt                 rc=1 (NOT ignored — D-11 / OPS-03)  ✓
reports/2026-05-19.md              rc=1 (NOT ignored — Pitfall #4 / OPS-02)  ✓
.env                               rc=0 (still ignored — secret protection)  ✓
data/ohlcv/AAPL/prices.parquet     rc=0 (still ignored — Phase 2 contract)  ✓

grep counts:
  !/data/runs.jsonl              1   ✓
  !/data/heartbeat.txt           1   ✓
  !/reports/*.md                 1   ✓
  !/data/universe/               2   ✓ (preserved)
  !/data/journal.sqlite          1   ✓ (Phase 7 preserved)
  data/ohlcv/**/splits.parquet   1   ✓ (Phase 2 preserved)
  !/data/*  (over-broad)         0   ✓ (T-08-overscope honored)
  /runs.jsonl  (obsolete)        0   ✓ (D-04 line removed)

Test runs:
  pytest tests/test_phase8_gitignore.py -v   →   4 passed, 0 skipped
  pytest tests/test_backtest_no_lookahead.py →   2 passed (FND-04 intact)
  pytest -m "not slow"                       →   219 passed, 28 skipped, 0 failed
```

## Next Phase Readiness

- Plans 08-04 (heartbeat.yml weekly cron) and 08-06 (refresh.yml nightly auto-commit) can now wire `file_pattern` arguments to the `stefanzweifel/git-auto-commit-action` step knowing that `git add` will pick up `data/runs.jsonl`, `data/heartbeat.txt`, and `reports/*.md` past `.gitignore` without needing `add_options: -f`.
- The 4 PASS tests in `tests/test_phase8_gitignore.py` will keep regressions from sneaking back in (e.g. anyone reverting the carve-outs will trip the CI test immediately).
- No blockers for Wave 2 work.

## Self-Check: PASSED

**Files asserted to exist:**
- `.gitignore` — FOUND (modified, contains all 3 expected carve-outs + comments)
- `tests/test_phase8_gitignore.py` — FOUND (modified, 4 passing tests + helper)
- `.planning/phases/08-github-actions-cron-operations/08-02-SUMMARY.md` — FOUND (this file)

**Commits asserted to exist:**
- `5686cfe` (chore(08-02): add Phase 8 gitignore carve-outs) — FOUND in `git log --oneline -5`
- `249e541` (test(08-02): fill Phase 8 gitignore carve-out tests) — FOUND in `git log --oneline -5`

**Behaviors asserted:**
- `git check-ignore -q data/runs.jsonl` → exit 1 (verified above)
- `git check-ignore -q data/heartbeat.txt` → exit 1 (verified above)
- `git check-ignore -q reports/2026-05-19.md` → exit 1 (verified above)
- `git check-ignore -q .env` → exit 0 (verified above)
- `pytest tests/test_phase8_gitignore.py` → 4/4 PASS (verified above)
- `pytest -m "not slow"` → 219 passed, 28 skipped, 0 failed (verified above)

---
*Phase: 08-github-actions-cron-operations*
*Completed: 2026-05-20*
