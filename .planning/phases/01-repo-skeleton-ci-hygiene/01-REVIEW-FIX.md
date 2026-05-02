---
phase: 01-repo-skeleton-ci-hygiene
fixed_at: 2026-05-02T00:00:00Z
review_path: .planning/phases/01-repo-skeleton-ci-hygiene/01-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 1: Code Review Fix Report

**Fixed at:** 2026-05-02T00:00:00Z
**Source review:** `.planning/phases/01-repo-skeleton-ci-hygiene/01-REVIEW.md`
**Iteration:** 1
**Scope:** critical_warning (4 warnings; 8 info findings deferred per scope)

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

All four WARNING findings were applied cleanly with full local verification
(ruff, mypy via pre-commit, pytest, and YAML parse). No findings required
rollback. The 8 INFO findings (IN-01..IN-08) are out of scope for this
iteration and remain open in `01-REVIEW.md` for future cleanup.

## Fixed Issues

### WR-01: `Settings()` instantiated at module import time

**Files modified:** `src/screener/config.py`
**Commit:** 71ad128
**Applied fix:** Replaced module-level `settings = Settings()` with a
`@functools.lru_cache(maxsize=1) def get_settings() -> Settings` accessor.
Importing `screener.config` no longer reads `.env` or runs pydantic
validation; both defer until the first `get_settings()` call. Module
docstring updated to document the lazy contract and the
`get_settings.cache_clear()` reset path for tests.

No backwards-compatibility shim is needed: `grep -rn 'from screener.config\|import screener.config'` across `src/` and `tests/` returned zero hits, so there are no callers of the old module-level `settings` to update.

**Verification:**
- `uv run ruff check src/screener/config.py` — passed
- `uv run ruff format --check src/screener/config.py` — passed (already formatted)
- `uv run python -c "from screener.config import get_settings; ..."` — instance is the expected `Settings`, second call returns the same object (cache hit confirmed)
- `uv run pytest -q -m "not slow"` — 5 passed, coverage gate (80%) reached

---

### WR-02: GitHub Actions third-party actions pinned to floating tags

**Files modified:** `.github/workflows/ci.yml`
**Commit:** bb2c7b5
**Applied fix:** Pinned both third-party actions to full 40-char commit
SHAs across all three jobs (lint, typecheck, test):

- `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2`
- `astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0`

SHAs were resolved via the GitHub Git Refs API:
- `actions/checkout` v4.2.2 → SHA via `refs/tags/v4.2.2` lookup
- `astral-sh/setup-uv` v6.8.0 (latest in the v6.x line) → SHA via tag lookup

The human-readable tag is preserved in a trailing comment on each line for
reviewer scannability and Dependabot diff readability.

The previous floating tags (`@v4`, `@v6`) left CI exposed to a
tj-actions-style supply-chain compromise — a concern that becomes material
once Phase 2+ wires Finnhub/FRED secrets into workflow steps.

**Verification:**
- `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` — parsed cleanly
- Step `uses` lines inspected programmatically; all 6 occurrences (3 jobs × 2 actions) pinned to SHA + comment

**Follow-up suggestion (not applied here):** add Dependabot config
(`.github/dependabot.yml` with `package-ecosystem: github-actions`) so SHA
bumps stay current automatically. Worth doing in a Phase 1 polish PR or as
the first step of Phase 2.

---

### WR-03: Pre-commit mypy `additional_dependencies` drifted from `pyproject.toml`

**Files modified:** `.pre-commit-config.yaml`
**Commit:** a572713
**Applied fix:** Added the four missing runtime dependencies to the mypy
hook's `additional_dependencies` list, with version constraints mirrored
exactly from `pyproject.toml [project].dependencies`:

- `scipy>=1.13,<2`
- `pyarrow>=17,<18`
- `requests-cache>=1.3,<2`
- `tenacity>=9.1,<10`

Added an in-file comment explaining the mirror requirement so future
maintainers understand why this list is duplicated rather than synthesized.

A more robust long-term solution (sourcing the list from `uv export
--extras dev` or a `[tool.mypy-additional]` table) was considered and
deferred — the cheap mirror is sufficient for Phase 1 and matches the
review's "cheapest fix that preserves Phase 1 scope" recommendation.

**Verification:**
- `uv run pre-commit run --all-files` — all hooks (`ruff format`, `ruff`,
  `mypy`) passed with the expanded environment
- pre-commit cleanly built a new mypy environment containing the four added
  packages (visible in the `[INFO] Initializing environment` line)

---

### WR-04: Pre-commit mypy `files` regex unanchored — over-matches

**Files modified:** `.pre-commit-config.yaml`
**Commit:** a5a7763
**Applied fix:** Changed
`^src/screener/(indicators|signals|regime\.py|sizing\.py)` →
`^src/screener/(indicators/|signals/|regime\.py$|sizing\.py$)`.

Directories now require a trailing `/` (so `indicatorsfoo/x.py` no longer
matches), and module files now require an end anchor (so `regime.pyi`,
`regime.pyc`, `regime.py.bak` no longer match).

Verified the new regex against an 11-case match table covering all
behaviors enumerated in the review:

| Path | Matches? | Expected? | Result |
|---|---|---|---|
| `src/screener/regime.py` | yes | yes | OK |
| `src/screener/regime.pyi` | no | no | OK |
| `src/screener/regime.pyc` | no | no | OK |
| `src/screener/regime.py.bak` | no | no | OK |
| `src/screener/sizing.py` | yes | yes | OK |
| `src/screener/sizing.py.bak` | no | no | OK |
| `src/screener/indicators/foo.py` | yes | yes | OK |
| `src/screener/indicatorsfoo/x.py` | no | no | OK |
| `src/screener/signals/foo.py` | yes | yes | OK |
| `src/screener/signalsfoo/x.py` | no | no | OK |
| `src/screener/cli.py` | no | no | OK |

**Verification:**
- Regex match table (above) passed all 11 cases
- `uv run pre-commit run --all-files` — all hooks still pass; mypy hook
  still runs against the four real strict-scope targets

---

## Skipped Issues

None — all four warning findings were applied cleanly with no rollback.

## Out of Scope (deferred)

The following 8 INFO findings remain open in `01-REVIEW.md` and were not
fixed in this iteration (per `fix_scope: critical_warning`):

- IN-01: `obs.configure()` re-runs `logging.basicConfig` per CLI invocation
- IN-02: `obs.configure()` snapshots `sys.stdout` reference
- IN-03: `Settings` field names use SCREAMING_SNAKE_CASE
- IN-04: CI workflow doesn't expose `workflow_dispatch`
- IN-05: Loop-variable shadowing in `tests/test_cli_smoke.py`
- IN-06: `_iter_source_files` doesn't exclude `.venv`/`build`/`dist`
- IN-07: Pre-commit mypy hook missing `language_version` pin
- IN-08: `pyproject.toml` ruff `PD` selector vs Phase 2 `df` naming

These are all genuine improvements but none block Phase 2 work; pull them
into a future hygiene PR or address opportunistically when touching the
relevant files.

---

_Fixed: 2026-05-02T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
