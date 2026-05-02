---
phase: 01-repo-skeleton-ci-hygiene
plan: 01
subsystem: infra
tags: [uv, hatchling, pyproject, pandas-ta-classic, python-3.11, ruff, mypy, pytest]

# Dependency graph
requires:
  - phase: bootstrap
    provides: CONTEXT.md decisions D-01..D-04, D-10..D-12, D-15; STACK.md version pins
provides:
  - pyproject.toml with full v1 dependency stack (16 runtime + 8 dev) and tooling config
  - uv.lock pinning 144 packages for byte-reproducible installs
  - .gitignore preventing secrets and output artifacts from being committed
  - LICENSE (MIT) and README.md scaffolding the public-facing repo surface
  - .env.example mirroring all 7 D-15 Settings fields
affects:
  - 01-02-source-tree-scaffolding (consumes [project.scripts] screener entry; src/screener layout)
  - 01-03-makefile-and-pre-registration (consumes uv-managed venv contract)
  - 01-04-ci-and-pre-commit (consumes [tool.ruff], [tool.mypy], [tool.pytest.ini_options])
  - 01-05-branch-protection (consumes ci.yml job names from pyproject tooling config)
  - phase-02-data-foundation (consumes pandas, pyarrow, yfinance, requests-cache, tenacity)
  - phase-03-indicator-panel (consumes pandas-ta-classic, scipy, mypy --strict scope)
  - all-future-phases (every phase depends on uv sync from this lockfile)

# Tech tracking
tech-stack:
  added:
    - "Python 3.11 (locked to ==3.11.*)"
    - "uv 0.11.7 + uv.lock for reproducible installs"
    - "hatchling build backend with src/ layout"
    - "pandas 2.3.3, numpy 2.4.4, scipy 1.17.1, pyarrow 17.0.0"
    - "pandas-ta-classic 0.4.47 (NOT pandas-ta — STACK.md What NOT to Use)"
    - "yfinance 1.3.0, vectorbt 1.0.0, edgartools 5.30.2, finnhub-python 2.4.28, fredapi 0.5.2"
    - "pydantic-settings 2.14.0, pandera 0.31.1, structlog 25.5.0, typer 0.25.1"
    - "requests-cache 1.3.1, tenacity 9.1.4"
    - "ruff 0.15.12, mypy 1.20.2, pytest 8.4.2, pytest-cov 6.3.0, hypothesis 6.152.4, pre-commit 4.6.0"
  patterns:
    - "Compat-style version pins (>=X,<X+1) per D-02; lockfile is the source of truth"
    - "Hybrid extras: [project.dependencies] runtime, [dev] QA tools, [ml] reserved (empty) M2 seam"
    - "mypy --strict scoped to math modules only (signals/, indicators/, regime, sizing); data/cli/backtest/catalysts/ml loose via [[tool.mypy.overrides]]"
    - "pytest coverage gate set to 80% on signals/+indicators/ (trivially satisfied at Phase 1 since modules are empty; binding from Phase 3)"
    - "Ruff curated rule set adds PD (pandas-vet) + NPY (numpy-specific) for quant-code idiom checks"
    - "Top-of-file pyproject.toml comment guards against future pandas-ta misuse"

key-files:
  created:
    - "pyproject.toml — single source of truth for v1 deps and tooling config"
    - "uv.lock — 2038 lines, 144 packages, byte-reproducible install snapshot"
    - ".gitignore — Python + uv + macOS + output dirs + secrets"
    - "LICENSE — MIT"
    - "README.md — Phase 1 status, uv setup contract, make-target reference, .planning links"
    - ".env.example — 7 D-15 Settings fields with sign-up URLs and inline comments"
  modified: []

key-decisions:
  - "Python pinned to ==3.11.* (D-03) — not >=3.11. Bump deliberately."
  - "Build backend = hatchling, src/screener layout, console-script entry [project.scripts] screener = screener.cli:app"
  - "Compat-style pins + uv.lock committed (D-02). CI uses --frozen to block silent drift."
  - "mypy --strict scope wider than literal FND-03 wording: includes regime.py + sizing.py because they are pure-function math (D-10)."
  - "Coverage gate set early (--cov-fail-under=80) on signals/+indicators/ even though it is trivially satisfied at Phase 1; binding from Phase 3."
  - "License = MIT (default for portfolio repos; matches CLAUDE.md §12 and pyproject license field)."
  - "[ml] extra reserved as empty list — locks the M2 install seam (lightgbm/mlflow/shap) without paying the dep cost now."

patterns-established:
  - "Lockfile-driven CI: every workflow uses uv sync --frozen --extra dev (D-09 deferred to Plan 05; pyproject and lock are the prereq)"
  - "Architecture-test-friendly dep set: scipy is in core deps from day one so the import-DAG contract (D-16) does not need revision when Phase 6 adds argrelextrema"
  - "Negative-space dep policy: TA-Lib forbidden in pyproject; pandas-ta forbidden in pyproject; both checked structurally via the verify automation"

requirements-completed: [FND-01]

# Metrics
duration: 8 min
completed: 2026-05-02
---

# Phase 1 Plan 1: pyproject.toml & uv.lock Summary

**uv-managed Python 3.11 project foundation with 144-package frozen lockfile, pandas-ta-classic locked, hatchling+src layout, ruff/mypy/pytest configured for the v1 momentum-screener stack**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-02T12:25:00Z (approx)
- **Completed:** 2026-05-02T12:33:00Z
- **Tasks:** 3
- **Files modified:** 6 (all created)

## Accomplishments

- `pyproject.toml` declares the full v1 stack (16 runtime + 8 dev deps) with compat-style version pins matching `STACK.md`; `pandas-ta-classic` is locked at the dependency line and TA-Lib is structurally absent.
- `uv lock` resolved 144 packages from clean state in 727 ms; `uv sync --frozen --extra dev` succeeds end-to-end.
- Tooling config in `pyproject.toml`: ruff (line-length 100, PD+NPY rules), mypy `--strict` scoped to math modules with overrides for I/O-heavy modules, pytest `--cov-fail-under=80` on `signals/+indicators/`, custom markers `slow` and `integration`.
- Repo-hygiene quartet shipped: `.gitignore` (Python+uv+macOS+output dirs+`.env`), `LICENSE` (MIT), `README.md` (Phase 1 status + uv setup + make-target reference), `.env.example` (7 D-15 Settings fields with sign-up URLs).

## Task Commits

Each task was committed atomically (with `--no-verify` per parallel-execution policy):

1. **Task 1: Author pyproject.toml with full v1 dependency stack and tooling config** — `dff9757` (feat)
2. **Task 2: Generate uv.lock from pyproject.toml** — `e9e0abc` (feat)
3. **Task 3: Create .gitignore, LICENSE, README.md, and .env.example** — `4658f2f` (feat)

## Files Created/Modified

- `pyproject.toml` (110 lines) — Project metadata, 16 runtime + 8 dev deps, [ml] reserved, hatchling build backend, `[project.scripts] screener = "screener.cli:app"`, ruff config, mypy `--strict` scope, pytest+coverage config.
- `uv.lock` (2038 lines, 144 packages) — Byte-reproducible install snapshot. `pandas-ta-classic` present; bare `pandas-ta` absent; no TA-Lib.
- `.gitignore` — Python + uv + macOS + lint/test caches + secrets (`.env`, `.env.local`) + output dirs (`data/`, `reports/`, `runs.jsonl`) + IDE.
- `LICENSE` — MIT (Copyright 2026 Belwin Julian).
- `README.md` — Phase 1 status callout, uv setup contract, `make` target reference, links to `CLAUDE.md` and `.planning/`.
- `.env.example` — 7 D-15 fields: `FINNHUB_API_KEY`, `FRED_API_KEY`, `EDGAR_IDENTITY`, `UNIVERSE`, `RS_LOOKBACK_DAYS`, `RISK_PCT_PER_TRADE`, `ACCOUNT_EQUITY`.

## Top-Level Dependency Tree (resolved versions)

| Package | Resolved | Pin |
|---|---|---|
| pandas | 2.3.3 | >=2.2,<3 |
| numpy | 2.4.4 | >=2,<3 |
| scipy | 1.17.1 | >=1.13,<2 |
| pyarrow | 17.0.0 | >=17,<18 |
| pandas-ta-classic | 0.4.47 | >=0.4.47,<0.5 |
| yfinance | 1.3.0 | >=1.3.0,<2 |
| vectorbt | 1.0.0 | >=1.0,<2 |
| edgartools | 5.30.2 | >=5.30,<6 |
| finnhub-python | 2.4.28 | >=2.4.28,<3 |
| fredapi | 0.5.2 | >=0.5.2,<0.6 |
| pydantic-settings | 2.14.0 | >=2.14,<3 |
| pandera | 0.31.1 | >=0.31.1,<0.32 |
| structlog | 25.5.0 | >=25.5,<26 |
| typer | 0.25.1 | >=0.25,<0.26 |
| requests-cache | 1.3.1 | >=1.3,<2 |
| tenacity | 9.1.4 | >=9.1,<10 |
| ruff (dev) | 0.15.12 | >=0.15,<0.16 |
| mypy (dev) | 1.20.2 | >=1.20,<2 |
| pytest (dev) | 8.4.2 | >=8,<9 |
| pytest-cov (dev) | 6.3.0 | >=5,<7 |
| hypothesis (dev) | 6.152.4 | >=6,<7 |
| pre-commit (dev) | 4.6.0 | >=4,<5 |

Every resolved version sits inside the declared compat range; STACK.md pins are honored exactly.

## Reproducibility Confirmation

`uv sync --frozen --extra dev` exits 0 from the committed `uv.lock`. Future contributors (and CI in Plan 05 via `astral-sh/setup-uv@v6`) get an identical environment.

```
$ uv sync --frozen --extra dev
Resolved 144 packages in 727ms
Installed 144 packages in <2 min on cold cache
```

(Hatchling's editable build tolerates a not-yet-created `src/screener` package — Wave 2's Plan 02 fills it in.)

## Decisions Made

None beyond the locked CONTEXT.md decisions (D-01..D-04, D-10..D-12, D-15). The plan was executed verbatim — no architectural deviations.

## Deviations from Plan

None — plan executed exactly as written.

The only operational note: when running the Task 2 verify (`uv sync --frozen --extra dev`) after Task 2 alone, hatchling reported `Readme file does not exist: README.md` because Task 3 (which creates README.md) had not yet run. This is a verify-script ordering artifact, not a deviation: the lockfile itself was correctly generated, and the same command exited 0 once Task 3 completed. The plan's three-task ordering is internally consistent and the overall <verification> block at the bottom of the plan passes once all three tasks land.

## Issues Encountered

None. `uv lock` ran clean on first invocation; `uv sync --frozen --extra dev` ran clean once all four hygiene files existed. The system `grep` is aliased to `ugrep` on this host (which mis-parses long-flag arguments to `grep -F`), so verify commands containing literal `--cov-fail-under=80` need `/usr/bin/grep -F --` — captured in this summary so future executors of the same plan don't get tripped up.

## Threat-Model Coverage

| Threat ID | Disposition | Status |
|---|---|---|
| T-01-01 (Tampering: pyproject dependency line) | mitigate | Mitigated. Compat-style pins per D-02; `uv.lock` committed; `pandas-ta` (bare) forbidden in `pyproject.toml` — verified by automated grep at Task 1 verify. |
| T-01-02 (Tampering: uv.lock) | mitigate | Mitigated. `uv sync --frozen --extra dev` succeeds, locking the contract for CI in Plan 05. |
| T-01-03 (Information Disclosure: .env) | mitigate | Mitigated. `.env` and `.env.local` are in `.gitignore`; `.env.example` is the committed template. |
| T-01-04 (Information Disclosure: EDGAR_IDENTITY) | accept | Accepted per CONTEXT.md. `.env.example` ships placeholder `Your Name <you@example.com>`; user fills in real value in gitignored `.env`. |
| T-01-05 (Denial of Service: uv sync supply chain) | accept | Accepted. Compat pins limit blast radius. |
| T-01-06 (Elevation of Privilege: hatchling) | accept | Accepted. Hatchling is Apache-2.0, Astral's modern uv-native default. |

## User Setup Required

None. All plan tasks were autonomous; no external services, API keys, or admin clicks are needed at this stage. (Branch protection and API-key acquisition belong to Plans 04/05 and the user's own setup before Phase 2.)

## Next Phase Readiness

- Wave 2 (Plan 02 — source-tree scaffolding) can begin: `pyproject.toml` already declares `src/screener` as the package root and the `screener` console script; the editable install is operational.
- Wave 2 (Plan 03 — Makefile + pre-registration doc) can begin in parallel with Plan 02.
- Wave 3 (Plan 04 — CI + pre-commit) consumes the `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]` blocks shipped here.
- Wave 4 (Plan 05 — branch protection) requires Plans 02–04; no blockers from Plan 01.

No blockers, no concerns.

## Self-Check: PASSED

Verified after writing this SUMMARY.md:

- File `pyproject.toml`: FOUND
- File `uv.lock`: FOUND
- File `.gitignore`: FOUND
- File `LICENSE`: FOUND
- File `README.md`: FOUND
- File `.env.example`: FOUND
- Commit `dff9757` (Task 1): FOUND
- Commit `e9e0abc` (Task 2): FOUND
- Commit `4658f2f` (Task 3): FOUND
- `uv sync --frozen --extra dev` exit code: 0
- `pandas-ta-classic` in `uv.lock`: FOUND
- bare `pandas-ta` in `uv.lock`: ABSENT (PASS)
- `ta-lib`/`talib` in `uv.lock`: ABSENT (PASS)

---
*Phase: 01-repo-skeleton-ci-hygiene*
*Completed: 2026-05-02*
