---
phase: 01-repo-skeleton-ci-hygiene
plan: 02
subsystem: infra
tags: [python, typer, pydantic-settings, structlog, src-layout, hatchling, scaffolding]

# Dependency graph
requires:
  - phase: 01-repo-skeleton-ci-hygiene/01
    provides: "pyproject.toml pinning typer/pydantic-settings/structlog and the [project.scripts] screener=screener.cli:app console-script entry point"
provides:
  - "src/screener/ package importable end-to-end with all 7 architectural layers as docstring-only markers (D-13)"
  - "Settings(BaseSettings) with all 7 v1 env-driven fields per D-15 (FINNHUB_API_KEY, FRED_API_KEY, EDGAR_IDENTITY, UNIVERSE, RS_LOOKBACK_DAYS, RISK_PCT_PER_TRADE, ACCOUNT_EQUITY)"
  - "obs.configure() helper wiring structlog to JSON output on stdout (named obs.py to avoid shadowing stdlib logging)"
  - "Typer CLI exposing all 9 v1 subcommands per D-14 — every subcommand exits 0 with a structured [stub] log line, locking the Makefile contract for Plan 04"
affects:
  - "01-03-tests-scaffolding (architecture test parses these import-empty modules; CLI smoke test asserts the 9-subcommand surface)"
  - "01-04-makefile-and-preregistration-doc (make data/rank/report/backtest shells out to typer subcommand names locked here)"
  - "01-05-ci-and-precommit (mypy --strict scope is regime/sizing/indicators/signals — placeholders here mean trivially passing in Phase 1, becomes binding from Phase 3)"
  - "Phase 2+ (every later phase fills in module bodies; the architectural seams will not move)"

# Tech tracking
tech-stack:
  added: []  # All stack pinned in 01-01; this plan ships the consuming source tree only
  patterns:
    - "Layered DAG src layout (data → indicators → signals → regime → sizing → publishers; backtest reads disk only; catalysts/ml are M2 reserve seams)"
    - "Module-docstring-only layer markers (D-13) — locks the architectural set without committing to public-API shapes Phase 2+ may want to revise"
    - "pydantic-settings BaseSettings with SettingsConfigDict(env_file='.env') and CAPS field naming; defaults match CLAUDE.md §10.2 numerics"
    - "structlog JSON renderer on stdout — idempotent configure() call from CLI startup; per-module loggers via structlog.get_logger(__name__)"
    - "Typer composition root with no_args_is_help=True; subcommand bodies will be filled in additively by later phases without breaking the CLI contract"

key-files:
  created:
    - "src/screener/__init__.py — package marker (architecture docstring)"
    - "src/screener/config.py — Settings(BaseSettings) with all 7 D-15 fields"
    - "src/screener/obs.py — structlog JSON-output configure() helper"
    - "src/screener/cli.py — typer composition root with all 9 v1 subcommands (D-14)"
    - "src/screener/persistence.py — disk-format placeholder (Phase 2 schema seam)"
    - "src/screener/regime.py — market-regime placeholder (Phase 3)"
    - "src/screener/sizing.py — per-playbook sizing placeholder (Phase 7)"
    - "src/screener/data/__init__.py — only-I/O-layer marker"
    - "src/screener/indicators/__init__.py — pure-function indicator panel marker (SMAs, NOT EMAs)"
    - "src/screener/signals/__init__.py — signal stack marker (minervini/qullamaggie/canslim/composite)"
    - "src/screener/publishers/__init__.py — report/journal/snapshot fan-out marker"
    - "src/screener/backtest/__init__.py — offline-only marker (reads persistence + stdlib only)"
    - "src/screener/catalysts/__init__.py — M2 reserve seam"
    - "src/screener/ml/__init__.py — M2 ML reserve seam"
  modified:
    - ".gitignore — anchored /data/, /reports/, /runs.jsonl to repo root with leading slash so src/screener/data/ is not ignored"

key-decisions:
  - "Honored D-13 strictly: every layer file is a single ast.Constant docstring. No def, no class, no NotImplementedError. Verified via ast.parse acceptance check."
  - "Honored D-14 verbatim: 9 subcommand names exactly as specified (refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit). Each calls obs.configure() then logs structured stub line."
  - "Honored D-15 verbatim: all 7 Settings fields use the CAPS naming the plan dictated; SettingsConfigDict(env_file='.env', extra='ignore'); a module-level settings = Settings() instance is exposed for later-phase imports."
  - "Picked obs.py for the structlog helper (Claude's Discretion in 01-CONTEXT.md offered logconfig.py / obs.py / logging.py — chose obs.py to avoid stdlib shadowing entirely)."

patterns-established:
  - "AST-pure docstring placeholders: layer markers ship one ast.Expr/ast.Constant module body and nothing else; CI architecture test (Plan 03) will validate this contract going forward."
  - "obs.configure() is idempotent and safe to call from every CLI subcommand entry; per-command stubs call it on every invocation rather than relying on a single startup hook."
  - "All Typer subcommands use kebab-case names registered explicitly via @app.command('refresh-universe') so Python function naming (snake_case) and CLI naming (kebab-case) are decoupled."

requirements-completed: [FND-01, FND-02]

# Metrics
duration: 4min
completed: 2026-05-02
---

# Phase 1 Plan 2: Source Tree Scaffolding Summary

**src/screener/ package now imports end-to-end with all 7 architectural layers locked as docstring-only markers, a real pydantic-settings Settings class, structlog JSON-output config, and a Typer CLI exposing the full 9-subcommand v1 surface — every subcommand exits 0 with a structured `[stub]` log line.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-02T12:38:17Z
- **Completed:** 2026-05-02T12:42:00Z
- **Tasks:** 3 / 3
- **Files modified:** 15 (14 created, 1 modified)

## Accomplishments

- All 7 architectural layer directories under `src/screener/` exist with one-line module-docstring `__init__.py` files declaring role and import policy (D-13).
- `Settings(BaseSettings)` ships with all 7 D-15 env-driven fields, defaults from `CLAUDE.md` §10.2 (UNIVERSE='russell1000', RS_LOOKBACK_DAYS=252, RISK_PCT_PER_TRADE=0.0075, ACCOUNT_EQUITY=100_000.0), loading from `.env`.
- `obs.configure()` wires structlog to JSON output on stdout (timestamping + log-level binding), idempotent and called by every CLI stub.
- Typer CLI in `src/screener/cli.py` exposes all 9 v1 subcommands (refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit). `uv run screener --help` lists all 9; each subcommand exits 0 emitting a structured `[stub] <command> not yet implemented` log line.

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor mode):

1. **Task 1: config.py + obs.py + package marker** — `c79c46b` (feat)
2. **Task 2: layer markers + standalone module placeholders + .gitignore Rule 3 fix** — `80cd20f` (feat)
3. **Task 3: cli.py with full v1 typer surface** — `a8da3a2` (feat)

## Files Created/Modified

### Foundations (Task 1)
- `src/screener/__init__.py` — Package marker; one-line architecture docstring pointing at the layered DAG and `tests/test_architecture.py`.
- `src/screener/config.py` — `Settings(BaseSettings)` with all 7 D-15 fields and module-level `settings = Settings()` instance.
- `src/screener/obs.py` — `configure(level='INFO')` wiring structlog processors (contextvars + add_log_level + ISO TimeStamper + JSONRenderer) on stdout.

### Layer markers + standalone placeholders (Task 2)
- `src/screener/persistence.py` — Phase 2 (DAT-09) seam reservation.
- `src/screener/regime.py` — Phase 3 (REG-01..REG-04) seam reservation.
- `src/screener/sizing.py` — Phase 7 (SIZ-01..SIZ-05) seam reservation.
- `src/screener/data/__init__.py` — Only-I/O-layer marker.
- `src/screener/indicators/__init__.py` — Pure-function panel marker (SMAs not EMAs reminder embedded in docstring).
- `src/screener/signals/__init__.py` — Signal stack marker.
- `src/screener/publishers/__init__.py` — Fan-out marker.
- `src/screener/backtest/__init__.py` — Offline-only marker (persistence + stdlib only).
- `src/screener/catalysts/__init__.py` — M2 reserve seam.
- `src/screener/ml/__init__.py` — M2 reserve seam.
- `.gitignore` — modified: `/data/`, `/reports/`, `/runs.jsonl` anchored to repo root.

### CLI surface (Task 3)
- `src/screener/cli.py` — Typer composition root; 9 `@app.command(...)` decorations matching D-14 exactly; each body calls `_stub("<cmd>")` which itself calls `obs.configure()` then `log.info("stub", command=..., message="[stub] <cmd> not yet implemented")`.

## Decisions Made

- **Module-docstring-only enforcement (D-13):** Every layer placeholder is exactly one `ast.Constant` body element. Verified at acceptance time via `ast.parse(...)` walk. This keeps the architectural set locked without committing to public-API shapes Phase 2+ may want to revise.
- **CLI subcommand naming:** Used `@app.command("refresh-universe")` style (kebab-case CLI surface, snake_case Python identifiers). Decouples the user-facing subcommand contract from Python naming.
- **Stub idempotence:** Each `_stub(...)` call invokes `obs.configure()` rather than a single startup hook. Cheap and means each CLI run is self-contained — useful for the Plan 03 test harness, which will exec subcommands in subprocess.
- **`obs.py` filename:** Picked over `logconfig.py` and `logging.py` (Claude's Discretion in 01-CONTEXT.md). `logging.py` would shadow stdlib; `logconfig.py` is awkward. `obs.py` reads as "observability" cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] `.gitignore` `data/` rule blocked staging `src/screener/data/__init__.py`**
- **Found during:** Task 2 (`git add src/screener/data/__init__.py` failed with `paths are ignored by .gitignore`).
- **Issue:** `.gitignore` shipped in Plan 01-01 had unanchored `data/`, `reports/`, `runs.jsonl` rules intended for runtime output dirs at repo root. The unanchored `data/` pattern matched the source-layer directory `src/screener/data/` and prevented committing the layer marker.
- **Fix:** Anchored the three rules to repo root with leading slash: `/data/`, `/reports/`, `/runs.jsonl`. Added an inline comment explaining why anchoring matters so future contributors don't undo it.
- **Files modified:** `.gitignore`
- **Verification:** `git check-ignore -v src/screener/data/__init__.py` returns no match (expected); `/data/` rule still ignores future runtime output at repo root.
- **Committed in:** `80cd20f` (rolled into the Task 2 commit since it was required to land the layer-marker file).

## Authentication Gates

None — no external services touched in this plan.

## Verification Results

All four `<verification>` block gates passed end-to-end:

1. `uv run python -c "from screener.config import settings; from screener.obs import configure; configure(); import screener.{data,indicators,signals,publishers,backtest,catalysts,ml,persistence,regime,sizing}"` — exits 0.
2. `uv run screener --help` — lists all 9 v1 subcommands (kebab-case, with one-line descriptions).
3. Each `uv run screener <subcommand>` — exits 0 with `[stub] <subcommand> not yet implemented` JSON log line on stdout (verified for all 9).
4. `! grep -rn -E '(NotImplementedError|^def |^class )' src/screener/persistence.py src/screener/regime.py src/screener/sizing.py src/screener/*/__init__.py` — no matches.

## Threat Flags

None — Phase 1 stubs introduce no new attack surface beyond what the threat model already inventories. Stubs do not access `settings.FINNHUB_API_KEY` etc. (T-02-01 leak surface = 0). Each stub is 2 lines (configure + log) with no loops or I/O (T-02-04 DoS surface = 0).

## Known Stubs

By design — this plan ships only stubs (D-13/D-14). All 9 CLI subcommands log `[stub] <command> not yet implemented` and exit 0; layer files are docstring-only. The orchestrator is aware: Phase 1's intent is to establish the architectural seams that later phases fill in. Each stub points at the phase that will land its body:

| File | Body lands in |
|------|---------------|
| `src/screener/persistence.py` | Phase 2 (DAT-09) |
| `src/screener/data/*` | Phase 2 (DAT-01..03, 06..09) |
| `src/screener/indicators/*` | Phase 3 (IND-01..05) |
| `src/screener/regime.py` | Phase 3 (REG-01..04) |
| `src/screener/signals/*` (minervini, composite) | Phase 4 (SIG-01, SIG-04) |
| `src/screener/backtest/*` | Phase 5 (BCK-01..07) |
| `src/screener/signals/*` (qullamaggie, canslim) + patterns | Phase 6 |
| `src/screener/sizing.py` | Phase 7 (SIZ-01..05) |
| `src/screener/cli.py` subcommand bodies | Phases 2–8 (each replaces a `_stub(...)` line with real logic) |
| `src/screener/catalysts/*` | Phase 6 (limited) + M2 |
| `src/screener/ml/*` | M2 |

## Self-Check: PASSED

**Files exist:**
- `src/screener/__init__.py` — FOUND
- `src/screener/config.py` — FOUND
- `src/screener/obs.py` — FOUND
- `src/screener/cli.py` — FOUND
- `src/screener/persistence.py` — FOUND
- `src/screener/regime.py` — FOUND
- `src/screener/sizing.py` — FOUND
- `src/screener/data/__init__.py` — FOUND
- `src/screener/indicators/__init__.py` — FOUND
- `src/screener/signals/__init__.py` — FOUND
- `src/screener/publishers/__init__.py` — FOUND
- `src/screener/backtest/__init__.py` — FOUND
- `src/screener/catalysts/__init__.py` — FOUND
- `src/screener/ml/__init__.py` — FOUND
- `.gitignore` — modified (FOUND)

**Commits exist (verified via `git log --oneline`):**
- `c79c46b` (Task 1) — FOUND
- `80cd20f` (Task 2 + .gitignore fix) — FOUND
- `a8da3a2` (Task 3) — FOUND
