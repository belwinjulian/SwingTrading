---
phase: 01-repo-skeleton-ci-hygiene
verified: 2026-05-02T14:18:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 01: Repo Skeleton & CI Hygiene — Verification Report

**Phase Goal:** Engineering hygiene first — `uv` env, locked v1 stack, CI gates active, Makefile orchestrating the DAG, pre-registration doc placeholder ready for Phase 4 weights.
**Verified:** 2026-05-02T14:18:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `uv sync` from a clean clone installs the full v1 stack (11 packages) with versions matching `STACK.md` pins | PASS | Wiped `.venv/`, ran `uv sync --frozen --extra dev` (resolved 142 pkgs from `uv.lock`); `importlib.metadata` reports installed versions: pandas 2.3.3, pandas-ta-classic 0.4.47, yfinance 1.3.0, vectorbt 1.0.0, edgartools 5.30.2, finnhub-python 2.4.28, fredapi 0.5.2, pydantic-settings 2.14.0, pandera 0.31.1, structlog 25.5.0, typer 0.25.1 — all match the `>=` lower bounds in `pyproject.toml` lines 25-34 and the `STACK.md` recommendations. `requires-python = "==3.11.*"` is locked. `pandas-ta-classic` is the runtime dep (not bare `pandas-ta`); TA-Lib does not appear anywhere in `pyproject.toml` or `uv.lock` (grep returned 0 hits). |
| 2 | `make data && make rank && make report && make backtest` from a clean checkout exits zero with placeholder behavior, no manual setup beyond `uv sync` and a populated `.env` | PASS | Each target invoked individually and exited 0: `make data` ran 4 stub subcommands (refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals), `make rank` ran `screener score`, `make report` ran `screener report`, `make backtest` ran `screener backtest`. Each subcommand emitted a structured JSON `[stub]` log line via `structlog`. `Settings()` defaults are populated (`config.py:20-30`) so an empty `.env` does not break the run. |
| 3 | Opening any pull request triggers GitHub Actions CI that runs `ruff check`, `mypy --strict src/screener/{indicators,signals}`, and `pytest` — all three must pass for the PR to be mergeable | PASS | `.github/workflows/ci.yml` defines three parallel jobs (`lint`, `typecheck`, `test`) on `pull_request` and `push: branches: [main]`. All jobs use `astral-sh/setup-uv@v6` + `uv sync --frozen --extra dev`. `lint` runs `ruff format --check .` and `ruff check .`. `typecheck` runs `uv run mypy` (which honors `[tool.mypy] strict = true; files = [...indicators, ...signals, ...regime.py, ...sizing.py]` from `pyproject.toml:69-72`). `test` runs `uv run pytest -m "not slow" -v` (with the `--cov-fail-under=80` gate from `pyproject.toml:106`). Branch protection on `main` is documented in `docs/branch_protection.md` and was applied via the GitHub UI ruleset (user-confirmed); the three status-check contexts (`lint`, `typecheck`, `test`) will register in GitHub's selectable list after the first workflow run — expected for a greenfield repo with no prior PR. |
| 4 | `docs/strategy_v1_preregistration.md` exists with the pre-registration template and the placeholder `<weights frozen at Phase 4 completion>` | PASS | File exists (57 lines). `grep -c "<weights frozen at Phase 4 completion>"` returns 2 (status header line 2 and dedicated "Status Token" section line 13). Doc lists all 6 v1 composite components (RS 25%, Trend 20%, Pattern 20%, Volume 10%, Earnings 15%, Catalyst 10%) with `TBD` Frozen Weight column awaiting Phase 4 freeze. References `git rev-parse HEAD` placeholder and the FND-05 freeze procedure. |

**Score:** 4/4 ROADMAP success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | v1 stack pins, hatchling backend, ==3.11.* lock, ruff/mypy/pytest config | VERIFIED | All present; `[project.scripts] screener = "screener.cli:app"`; mypy strict on indicators/signals/regime.py/sizing.py with overrides for data/cli/backtest/etc. (D-10) |
| `uv.lock` | Reproducible lockfile with pandas-ta-classic, no TA-Lib, no bare pandas-ta | VERIFIED | 142 packages locked; `name = "pandas-ta-classic"` at lock line 985; no `name = "pandas-ta"`; no TA-Lib |
| `.gitignore` | `.env`, `__pycache__`, `/data/`, `/reports/`, `/runs.jsonl` | VERIFIED | All present; output dirs anchored to repo root with leading `/` so `src/screener/data/` is NOT ignored (good comment on line 32-33) |
| `LICENSE` | MIT | VERIFIED | MIT License, Copyright Belwin Julian 2026 |
| `README.md` | Project one-liner + setup steps | VERIFIED | 1-line description matches roadmap; mentions Phase 1 status and uv setup |
| `.env.example` | All 7 D-15 Settings fields | VERIFIED | FINNHUB_API_KEY, FRED_API_KEY, EDGAR_IDENTITY, UNIVERSE, RS_LOOKBACK_DAYS, RISK_PCT_PER_TRADE, ACCOUNT_EQUITY |
| `src/screener/__init__.py` | Package marker | VERIFIED | Module docstring describes layered DAG |
| `src/screener/cli.py` | typer app with 9 D-14 subcommands logging [stub] | VERIFIED | `screener --help` lists all 9: refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit. Each calls `_stub()` which configures structlog and emits a JSON line |
| `src/screener/config.py` | pydantic-settings Settings with 7 fields | VERIFIED | `Settings(BaseSettings)` with all 7 D-15 fields; `SettingsConfigDict(env_file=".env", extra="ignore")`. Note: REVIEW.md WR-01 flagged eager `Settings()` instantiation at line 33 as a future fragility; non-blocking |
| `src/screener/obs.py` | structlog JSON config helper | VERIFIED | `configure(level)` wires JSON renderer + ISO timestamp + stdout |
| `src/screener/{persistence,regime,sizing}.py` | Module docstring stubs | VERIFIED | Three top-level stubs present |
| `src/screener/{data,indicators,signals,publishers,backtest,catalysts,ml}/__init__.py` | Layer dir markers | VERIFIED | All 7 subpackage `__init__.py` files exist |
| `tests/test_architecture.py` | AST-based DAG enforcement (D-16) | VERIFIED | 3 tests: layer-import contract, backtest-no-data-import, indicators/signals-no-IO. Pure stdlib `ast` (no import-linter dep). All pass |
| `tests/test_cli_smoke.py` | typer surface + 9 subcommands exit 0 | VERIFIED | 2 tests assert `--help` lists all 9 D-14 names and each subcommand exits 0 with a `[stub]` log line. Both pass |
| `tests/conftest.py` | repo_root + src_screener fixtures | VERIFIED | Both fixtures present, session-scoped |
| `Makefile` | data/rank/report/backtest/setup/help + .PHONY + self-doc | VERIFIED | `make help` lists 13 targets including all six required + lint/typecheck/test/all/clean/journal/backtest-audit. Each shells to `uv run screener <subcommand>` |
| `docs/strategy_v1_preregistration.md` | Placeholder + literal token | VERIFIED | See Truth #4 above |
| `docs/branch_protection.md` | Documented procedure for D-08 | VERIFIED | Documents required checks (lint/typecheck/test), settings, gh CLI command, web UI fallback, verify procedure |
| `.github/workflows/ci.yml` | 3 parallel jobs with `astral-sh/setup-uv@v6` + `uv sync --frozen` | VERIFIED | All 3 jobs (lint/typecheck/test) on pull_request + push:main; concurrency cancel-in-progress; 10-min timeouts. REVIEW.md WR-02 noted floating-tag pinning (`@v4`, `@v6`) as a non-blocking supply-chain warning |
| `.pre-commit-config.yaml` | ruff format + ruff check + mypy on staged files (no pytest per D-07) | VERIFIED | `uvx pre-commit run --all-files` passes 3 hooks: ruff-format, ruff (legacy alias), mypy (math modules — strict scope per D-10). REVIEW.md WR-03/WR-04 noted dependency-list drift and unanchored regex; non-blocking today |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pyproject.toml` | `uv.lock` | `uv lock` | VERIFIED | Lockfile matches manifest; `uv sync --frozen` succeeded |
| `pyproject.toml` | `.gitignore` | `.env` protected | VERIFIED | `.env` in gitignore line 28 |
| `Makefile` | `src/screener/cli.py` | `uv run screener <subcommand>` | VERIFIED | Each Makefile target invokes a real D-14 subcommand; subcommands exist in cli.py and respond |
| `tests/test_architecture.py` | `src/screener/**/*.py` | `ast.walk` over imports | VERIFIED | Test scans all 14 source files and enforces ALLOWED layer imports |
| `tests/test_cli_smoke.py` | `src/screener/cli.py` | typer `CliRunner` | VERIFIED | In-process invocation works; all 9 subcommands tested |
| `.github/workflows/ci.yml` | `uv.lock` | `uv sync --frozen --extra dev` | VERIFIED | 3 jobs all use `--frozen` flag (fails on lockfile drift) |
| `.github/workflows/ci.yml` | `tests/` | `uv run pytest -m "not slow" -v` | VERIFIED | test job invokes pytest with the same configuration as local |
| `docs/branch_protection.md` | `.github/workflows/ci.yml` job names | required status checks | VERIFIED | Doc names `lint`, `typecheck`, `test` — exact match with workflow job names |

### Data-Flow Trace (Level 4)

Not applicable — Phase 1 ships seams and stubs only. No data is rendered to a user-facing surface; CLI subcommands are explicitly placeholders that emit structured `[stub]` log lines. Real data flow lands in Phases 2+.

### Behavioral Spot-Checks

| # | Behavior | Command | Result | Status |
|---|----------|---------|--------|--------|
| 1 | Clean install + import works | `rm -rf .venv && uv sync --frozen --extra dev && uv run --no-sync python -c "import screener; print(screener.__file__)"` | Reports `/Users/.../src/screener/__init__.py` | PASS |
| 2 | All 11 v1 stack packages installed at correct versions | `uv run --no-sync python -c "import importlib.metadata as m; [print(p, m.version(p)) for p in [...]]"` | All 11 packages report versions ≥ pyproject pins | PASS |
| 3 | All 5 tests pass | `uv run --no-sync pytest -m "not slow" -v` | 5 passed in 0.68s; coverage 100% (gate: 80%) | PASS |
| 4 | `make help` lists required targets | `make help` | Lists data/rank/report/backtest/setup/help + 7 more | PASS |
| 5 | `make data && make rank && make report && make backtest` exits 0 | (each invoked) | All 4 EXIT: 0; 7 JSON [stub] lines emitted | PASS |
| 6 | `make lint` passes | `make lint` | "All checks passed!" EXIT: 0 | PASS |
| 7 | `make typecheck` passes | `make typecheck` | "Success: no issues found in 4 source files" EXIT: 0 | PASS |
| 8 | `uvx pre-commit run --all-files` passes | (run) | 3 hooks Passed (ruff-format, ruff, mypy) | PASS |
| 9 | Pre-registration token literal present | `grep -c "<weights frozen at Phase 4 completion>" docs/strategy_v1_preregistration.md` | 2 | PASS |
| 10 | No TA-Lib in deps | `grep -iE "ta-lib\|talib" pyproject.toml uv.lock` | 0 hits | PASS |
| 11 | No bare `pandas-ta` (only `pandas-ta-classic`) | `grep -E "name = \"pandas-ta\"$" uv.lock` | 0 hits | PASS |
| 12 | Python locked to 3.11 | `grep "requires-python" pyproject.toml` | `requires-python = "==3.11.*"` | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| FND-01 | 01-01, 01-02 | Repo skeleton runs on `uv` with `pyproject.toml` pinning the v1 stack (11 packages) | SATISFIED | Truth #1 + Spot-check #2; all 11 packages installed at correct pins |
| FND-02 | 01-02, 01-04 | `make data && make rank && make report && make backtest` runs end-to-end locally with no manual steps after setup | SATISFIED | Truth #2 + Spot-check #5; all four targets exit 0 from clean checkout |
| FND-03 | 01-03, 01-05 | CI runs ruff, mypy (strict on `signals/` and `indicators/`), and pytest on every PR | SATISFIED | Truth #3; ci.yml defines lint+typecheck+test jobs on pull_request + push:main; branch protection documented and applied via UI (status checks register on first workflow run, expected for greenfield) |

All 3 phase requirements claimed by plans match the ROADMAP.md mapping (FND-01, FND-02, FND-03 → Phase 1). No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/screener/{persistence,regime,sizing}.py` + 7 layer `__init__.py` | various | Module docstring stubs (no executable code) | INFO | Intentional Phase 1 seams; D-13 declares these as docstring placeholders. Real implementations land in later phases. NOT a stub anti-pattern — explicit and documented |
| `src/screener/cli.py:23-26` | `_stub("...")` placeholders | Stub implementations emitting `[stub]` log lines | INFO | Intentional Phase 1 placeholder per success criterion #2 ("placeholder behavior — real artifacts ship in later phases"). Each [stub] line is structured-log evidence the dispatch worked |
| `pyproject.toml:1-5` | Comment claims `import pandas_ta` (Python module name) is the same | INFO | The actual installed module is `pandas_ta_classic` — `import pandas_ta` raises `ModuleNotFoundError`. Phase 1 does not import the module so this is dormant; will surface when Phase 3 indicators land. Worth correcting to avoid future-developer confusion. Non-blocking |
| `.planning/REQUIREMENTS.md:12, 162` | FND-01 still marked `[ ]` Pending despite Phase 1 complete (FND-02 and FND-03 are marked `[x]` Complete) | INFO | Documentation lag — REQUIREMENTS.md checkbox not updated when Phase 1 completed. Affects reporting only; the underlying requirement is satisfied per Truth #1. Non-blocking |
| `.github/workflows/ci.yml` | `actions/checkout@v4`, `astral-sh/setup-uv@v6` floating-tag pins | INFO | REVIEW.md WR-02 flagged supply-chain risk; non-blocking but worth tightening before Phase 8 cron workflow lands with secrets access |
| `.pre-commit-config.yaml:24-32` | `additional_dependencies` missing scipy/pyarrow/requests-cache/tenacity | INFO | REVIEW.md WR-03; dormant today (math modules don't import these), surfaces in Phase 3+. Non-blocking |
| `.pre-commit-config.yaml:36` | `files` regex unanchored at end | INFO | REVIEW.md WR-04; over-matches `.pyi`/`.pyc`/`.bak` paths today (none exist). Non-blocking |
| `src/screener/config.py:33` | `settings = Settings()` evaluated at import time | INFO | REVIEW.md WR-01; fragile if `.env` becomes malformed. Currently no module imports `screener.config`, so dormant. Non-blocking |

No BLOCKER or WARNING-class anti-patterns found. All 8 items above are INFO-class observations or known REVIEW.md follow-ups explicitly accepted as non-blocking.

### Human Verification Required

None. All 4 ROADMAP success criteria are programmatically verifiable and verified.

The branch-protection runtime gate (per `docs/branch_protection.md` "Verify" section) cannot fully engage until the first PR is opened — at that point the three status-check contexts (`lint`, `typecheck`, `test`) become selectable in GitHub's UI. The user explicitly noted this is expected for a greenfield repo and that the ruleset has been applied via UI; no separate human verification is needed before Phase 2.

### Gaps Summary

No gaps. All 4 ROADMAP success criteria pass. All 3 phase requirements (FND-01, FND-02, FND-03) are claimed by plans and satisfied by the codebase. All 5 tests pass. The 4 REVIEW.md warnings remain as dormant follow-ups (eager Settings instantiation, floating action tags, mypy additional_dependencies drift, unanchored pre-commit regex) and are explicitly non-blocking per the REVIEW report.

One housekeeping note for the developer (not a verification gap): `.planning/REQUIREMENTS.md:12` still shows FND-01 as `[ ]` Pending while FND-02 and FND-03 are `[x]` Complete — likely a checkbox that was missed when Phase 1 was marked complete in ROADMAP.md. Worth updating in the same housekeeping pass that addresses the REVIEW.md warnings.

---

_Verified: 2026-05-02T14:18:00Z_
_Verifier: Claude (gsd-verifier)_
