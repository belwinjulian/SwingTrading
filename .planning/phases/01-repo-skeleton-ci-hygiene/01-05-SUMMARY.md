---
phase: 01-repo-skeleton-ci-hygiene
plan: 05
subsystem: infra
tags: [ci, github-actions, pre-commit, ruff, mypy, pytest, branch-protection, uv]

# Dependency graph
requires:
  - phase: 01-repo-skeleton-ci-hygiene
    provides: pyproject.toml with dev extra (ruff/mypy/pytest), uv.lock, src/screener tree, tests/ (01-01 through 01-04)
provides:
  - GitHub Actions CI workflow with three parallel jobs (lint, typecheck, test) on every PR and push to main
  - .pre-commit-config.yaml running ruff format + ruff check + mypy on staged files (pytest CI-only per D-07)
  - docs/branch_protection.md documenting the one-time admin action to enforce required status checks on main
  - Lint-clean source tree (4 docstring shortenings + 1 ambiguous-Unicode replacement) ready for the gate
affects: [02-data-foundation, all-future-phases]

# Tech tracking
tech-stack:
  added: [github-actions, astral-sh/setup-uv@v6, pre-commit (config only)]
  patterns:
    - "CI cache keyed on uv.lock; uv sync --frozen --extra dev fails on lockfile drift (D-09)"
    - "Three CI status-check job names (lint/typecheck/test) are the contract for branch-protection rules (D-08)"
    - "Pre-commit covers fast checks only (ruff + mypy); pytest stays in CI to keep the local commit loop fast (D-07)"
    - "10-minute timeout per job + concurrency.cancel-in-progress to keep CI minutes honest"

key-files:
  created:
    - .github/workflows/ci.yml
    - .pre-commit-config.yaml
    - docs/branch_protection.md
    - .planning/phases/01-repo-skeleton-ci-hygiene/01-05-SUMMARY.md
  modified:
    - src/screener/cli.py (4 docstrings shortened to satisfy E501 line-length 100)
    - tests/test_architecture.py (replaced ambiguous Unicode set-union char per RUF003)
    - tests/test_cli_smoke.py (ruff-format auto-collapse of multi-line f-string)

key-decisions:
  - "Auto-fixed pre-existing lint debt (E501 + RUF003) inside this plan rather than ship a CI gate that would red-flag every subsequent PR — the plan's deliverable is a working gate, not a gate that fails on the existing tree"
  - "Pre-commit ruff rev pinned to v0.15.12 and mirrors-mypy rev pinned to v1.20.0 to match the dev-deps ranges in pyproject.toml (drift later requires a deliberate bump in both places)"
  - "Branch-protection apply (gh api) intentionally NOT performed by Claude; documented as a checkpoint awaiting human action — admin write scope is not safe to grant to a CLI agent"

patterns-established:
  - "CI workflow shape: three parallel jobs, each setup-uv@v6 + uv python install + uv sync --frozen --extra dev + run-the-check"
  - "Pre-commit scoping: mypy hook restricted via files: regex to the strict-scope dirs only, mirroring [tool.mypy] files= in pyproject.toml"
  - "Doc-first branch protection: a single Markdown file with copy-pasteable gh api command + UI fallback + verify command is the artifact; the actual apply is a one-line user action"

requirements-completed: [FND-03]

# Metrics
duration: 3min
completed: 2026-05-02
---

# Phase 1 Plan 5: CI + Pre-commit + Branch Protection Summary

**GitHub Actions CI with three parallel jobs (lint/typecheck/test) on every PR and push to main, pre-commit hooks running ruff + mypy on staged files (pytest CI-only per D-07), and a documented branch-protection procedure awaiting a one-time `gh api` apply by the user.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-02T12:54:17Z
- **Completed:** 2026-05-02T12:57:42Z
- **Tasks:** 2 fully complete + 1 doc-shipped/awaiting-human-apply
- **Files created:** 3 (ci.yml, .pre-commit-config.yaml, branch_protection.md)
- **Files modified:** 3 (cli.py, test_architecture.py, test_cli_smoke.py — auto-fixes)

## Accomplishments

- `.github/workflows/ci.yml` ships three parallel jobs (lint, typecheck, test) on `pull_request` and `push: branches: [main]` (D-05, D-06, D-09) — each job uses `astral-sh/setup-uv@v6` with `enable-cache: true` keyed on `uv.lock`, runs `uv sync --frozen --extra dev`, and has a 10-minute timeout
- `.pre-commit-config.yaml` ships `ruff-format`, `ruff` (--fix), and a scoped `mypy` hook (D-07, D-10); pytest is intentionally absent
- `docs/branch_protection.md` documents the exact `gh api` PUT call, the equivalent web-UI click-path, and a `--jq '.required_status_checks.contexts'` verification command — ready for the user to execute
- Pre-existing lint debt that would have broken the new CI gate on its first run was auto-fixed (4 long docstrings + 1 ambiguous-Unicode comment) so the gate ships green

## Task Commits

1. **Task 1: Author .github/workflows/ci.yml with three parallel jobs** — `8f765fe` (ci)
2. **Task 2: Author .pre-commit-config.yaml + auto-fix pre-existing lint** — `314433b` (chore)
3. **Task 3 (doc portion): Author docs/branch_protection.md** — `b509112` (docs)
4. **Plan metadata commit (this SUMMARY + STATE/ROADMAP/REQUIREMENTS updates)** — pending after STATE updates

Task 3's actual `gh api` apply is non-autonomous and awaits the user (see "Awaiting Human Action" below).

## Files Created/Modified

- `.github/workflows/ci.yml` — three CI jobs; cache-keyed setup-uv@v6; uv sync --frozen --extra dev; 10-min timeout; concurrency-cancel
- `.pre-commit-config.yaml` — ruff-format, ruff (--fix), mypy (scoped to indicators/signals/regime.py/sizing.py); no pytest hook (D-07)
- `docs/branch_protection.md` — required status checks, gh api invocation, web-UI fallback, verification command
- `src/screener/cli.py` — shortened 4 docstrings to satisfy E501 line-length 100
- `tests/test_architecture.py` — replaced `⊆ ∪` with prose to satisfy RUF003
- `tests/test_cli_smoke.py` — pre-commit ruff-format auto-collapsed a two-line f-string

## Decisions Made

- **Auto-fix the pre-existing lint debt rather than ship a known-failing CI gate.** Without these 5 fixes, the very first PR after this plan would have failed all of `ruff check` and `pre-commit`, defeating the plan's purpose. Treated as Rule 1 (auto-fix bugs) — the new artifact (CI gate) is structurally broken without the fix. Auto-fixes are minimal: 4 docstring shortenings preserving meaning + 1 Unicode → ASCII swap in a comment.
- **Pin pre-commit hook revs to specific patches** (`ruff-pre-commit v0.15.12`, `mirrors-mypy v1.20.0`) rather than floating — drift between the local pre-commit cache and the CI's `uv sync --frozen` install is a known footgun. Bump both intentionally when bumping pyproject.toml.
- **Do not run `gh api` myself.** Branch protection is a destructive admin operation on shared infrastructure. The doc provides everything the user needs; a checkpoint is returned to the orchestrator.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Pre-existing E501 line-length violations in src/screener/cli.py**
- **Found during:** Task 2 verification (`uvx pre-commit run --all-files` after writing the config)
- **Issue:** Four docstrings in `cli.py` exceeded the project's `line-length = 100` ruff setting (lines 31, 49, 55, 79). Shipped by an earlier wave (Plan 02). Without this fix, every PR after Plan 05 lands would fail the new `lint` CI job, defeating the plan's purpose.
- **Fix:** Shortened each offending docstring while preserving meaning (e.g., "writes weekly Parquet snapshot" → "weekly Parquet snapshot"; "implementation" wording trimmed; etc.).
- **Files modified:** `src/screener/cli.py`
- **Verification:** `uv run ruff check .` exits 0 after the fix; `uv run pytest -m "not slow"` still 5 passed (cli_smoke tests still recognize all 9 D-14 subcommands by name, not docstring).
- **Committed in:** `314433b` (alongside Task 2 because the pre-commit config is what discovered the violations)

**2. [Rule 1 — Bug] Pre-existing RUF003 ambiguous-Unicode in tests/test_architecture.py**
- **Found during:** Task 2 verification (same `pre-commit run --all-files`)
- **Issue:** A comment used `⊆` (subset-of) and `∪` (set-union) characters; ruff RUF003 flags ambiguous Unicode in comments because they look like ASCII letters and break grep / copy-paste round-trips.
- **Fix:** Rewrote the comment in plain English ("imports are a subset of allowed plus {layer itself}").
- **Files modified:** `tests/test_architecture.py`
- **Verification:** `uv run ruff check .` exits 0; architecture tests still pass (comment-only change).
- **Committed in:** `314433b`

**3. [Rule 1 — Style] Pre-commit ruff-format auto-collapsed a two-line f-string in tests/test_cli_smoke.py**
- **Found during:** Task 2 (`pre-commit run --all-files` second pass, after the manual fixes above)
- **Issue:** A multi-line `f"... " f"..."` concatenation could fit on one line under `line-length = 100`; ruff format normalized it.
- **Fix:** Accepted the auto-format (no semantic change).
- **Files modified:** `tests/test_cli_smoke.py`
- **Verification:** `uv run pytest -m "not slow"` still 5 passed.
- **Committed in:** `314433b`

---

**Total deviations:** 3 auto-fixed (3 Rule 1 — pre-existing-debt items that would have broken the new CI gate immediately).
**Impact on plan:** All three were necessary so the gate this plan ships actually passes on day one. No new functionality was added; no scope creep.

## Issues Encountered

- None beyond the lint debt above. Pre-commit successfully fetched and cached the ruff and mypy hook environments on first run; mypy passed on the strict-scope files (none exist beyond empty `__init__.py` stubs in Phase 1, so the typecheck is trivially green).

## Self-Check

Verifying claims before completing:

- `[ -f .github/workflows/ci.yml ]` → FOUND
- `[ -f .pre-commit-config.yaml ]` → FOUND
- `[ -f docs/branch_protection.md ]` → FOUND
- `[ -f .planning/phases/01-repo-skeleton-ci-hygiene/01-05-SUMMARY.md ]` → FOUND (this file)
- `git log --oneline | grep 8f765fe` → FOUND (Task 1: ci workflow)
- `git log --oneline | grep 314433b` → FOUND (Task 2: pre-commit + auto-fixes)
- `git log --oneline | grep b509112` → FOUND (Task 3 doc: branch_protection.md)

## Self-Check: PASSED

## User Setup Required

**ONE manual action remains** to fully complete this plan and Phase 1:

The user (Belwin) must apply branch protection to `main` by running the `gh api` command from `docs/branch_protection.md`. This requires repo-admin OAuth scope that the local CLI agent does not have.

```bash
# 1. Confirm gh is authenticated
gh auth status

# 2. Apply protection (full command in docs/branch_protection.md)
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/:owner/:repo/branches/main/protection \
  -F "required_status_checks[strict]=true" \
  -F "required_status_checks[contexts][]=lint" \
  -F "required_status_checks[contexts][]=typecheck" \
  -F "required_status_checks[contexts][]=test" \
  -F "enforce_admins=false" \
  -F "required_pull_request_reviews[required_approving_review_count]=0" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=false" \
  -F "required_pull_request_reviews[require_code_owner_reviews]=false" \
  -F "restrictions=" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false" \
  -F "required_linear_history=false"

# 3. Verify
gh api /repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'
# Expected: ["lint","typecheck","test"]
```

Web-UI fallback documented in `docs/branch_protection.md`.

## Next Phase Readiness

- Phase 1 success criteria 1, 2, 4 already met by Plans 01-01..01-04. Success criterion 3 (CI gates merges) is met *after* the user runs the gh api command above.
- Phase 2 (Data Foundation) can begin once branch protection is live. **Phase 2 reminder:** when API keys (FINNHUB_API_KEY, FRED_API_KEY, EDGAR_IDENTITY) land in CI, add them as GitHub Actions `secrets:` and reference via `${{ secrets.X }}` — never `echo` them. The current workflow has `permissions: contents: read` and uses no secrets, which is correct for Phase 1.

---
*Phase: 01-repo-skeleton-ci-hygiene*
*Completed: 2026-05-02 (autonomous portion); awaiting user `gh api` apply for branch protection*
