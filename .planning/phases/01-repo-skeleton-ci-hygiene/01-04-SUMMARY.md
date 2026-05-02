---
phase: 01-repo-skeleton-ci-hygiene
plan: 04
subsystem: infra
tags: [makefile, cli, typer, pre-registration, dag, fnd-02]

# Dependency graph
requires:
  - phase: 01-repo-skeleton-ci-hygiene
    provides: D-14 typer subcommand surface (refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit) shipped by Plan 02
provides:
  - Self-documenting Makefile that orchestrates the four-target user DAG (data, rank, report, backtest)
  - User-facing setup target wrapping uv sync --extra dev + pre-commit install
  - lint / typecheck / test / all / clean convenience targets
  - docs/strategy_v1_preregistration.md placeholder with the literal token <weights frozen at Phase 4 completion>
  - 6-row TBD weights table mirroring STATE.md targets (RS 25, Trend 20, Pattern 20, Volume 10, Earnings 15, Catalyst 10)
affects: [phase-02-data-foundation, phase-04-trend-template-and-composite, phase-05-backtest-harness, phase-08-ops-cron]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-documenting Makefile via awk-parsed `## description` comments"
    - "Makefile recipes shell out to `uv run screener <subcommand>` so targets work without an active venv"
    - "Pre-registration document precedes any backtest result (discipline against in-sample weight overfit)"

key-files:
  created:
    - "Makefile - 13 .PHONY targets, recipes route through D-14 typer CLI"
    - "docs/strategy_v1_preregistration.md - locks the literal token Phase 4 CI gate (deferred) will check"
  modified: []

key-decisions:
  - "Makefile uses TAB-indented recipes (Make grammar requirement) and is fully .PHONY (no real file deps until later phases)"
  - "Recipe contract is stable: Phase 2+ fills CLI bodies without touching the Makefile"
  - "make rank aliases the canonical CLI verb `screener score` (FND-02 names the user-facing target `rank`)"
  - "make data runs all four refresh-* subcommands sequentially, matching D-14 grouping"
  - "Pre-registration weights stored as TBD; Phase 4 CI gate that protects the literal token is deferred per CONTEXT.md Deferred Ideas"

patterns-established:
  - "Self-documenting Makefile help target: `awk 'BEGIN {FS = \":.*?## \"} ...'` parses `target: ## description` comments"
  - "User DAG -> CLI mapping: make data/rank/report/backtest -> uv run screener {refresh-*,score,report,backtest}"
  - "Pre-registration document is the discipline gate against PITFALLS.md #5 (in-sample overfit) and #13 (multiple-testing blindness)"

requirements-completed: [FND-02]

# Metrics
duration: 2min
completed: 2026-05-02
---

# Phase 01 Plan 04: Makefile + Pre-registration Doc Summary

**Wires the user-facing `make data && make rank && make report && make backtest` DAG to the D-14 typer CLI and ships the v1 strategy pre-registration placeholder that locks the Phase 4 weight-freeze contract.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-02T12:47:58Z
- **Completed:** 2026-05-02T12:49:54Z
- **Tasks:** 2 / 2
- **Files modified:** 2 (1 Makefile, 1 docs/)

## Accomplishments

- `make data && make rank && make report && make backtest` exits 0 from a clean checkout; FND-02 satisfied.
- All 13 Makefile targets are .PHONY, TAB-indented, and self-documenting via `make help`.
- Every user-facing target shells out to a real D-14 typer subcommand; each subcommand emits a structured `[stub]` log line in Phase 1 and exits 0.
- `docs/strategy_v1_preregistration.md` exists with the literal token `<weights frozen at Phase 4 completion>` verbatim and the 6-component TBD weights table.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author Makefile with self-documenting `help` target wired to typer subcommands** — `faf6f93` (feat)
2. **Task 2: Author docs/strategy_v1_preregistration.md placeholder** — `0546ff8` (docs)

## Files Created/Modified

- `Makefile` (created) — 13 .PHONY targets: `help`, `setup`, `data`, `rank`, `report`, `backtest`, `backtest-audit`, `journal`, `lint`, `typecheck`, `test`, `all`, `clean`. Recipes use `uv run screener <subcommand>` so they work without an active venv.
- `docs/strategy_v1_preregistration.md` (created) — Status placeholder, literal token, 6-row TBD weights table mirroring STATE.md targets, methodology summary (RS / Trend / Pattern / Volume / Earnings / Catalyst), Phase 4 freeze procedure, references to PITFALLS.md #5/#13, FND-05, and CLAUDE.md §2.7.

## Verification Output

`make help` lists 13 targets (filtered for the 6 plan-required targets):

```
  help               List available targets with descriptions
  setup              Install dependencies (uv sync --extra dev) and pre-commit hooks
  data               Refresh universe, OHLCV, macro, and fundamentals (Phase 1: stub no-ops)
  rank               Compute composite scores + playbook tags over the universe (Phase 1: stub)
  report             Render the daily Markdown report (Phase 1: stub)
  backtest           Run vectorbt walk-forward backtest (Phase 1: stub)
  backtest-audit     Run the forensic checklist (no-look-ahead, weight-pre-reg hash, universe date)
  journal            Append actionable picks to data/journal.sqlite (Phase 1: stub)
  lint               Run ruff format --check and ruff check
  typecheck          Run mypy --strict on the math modules (signals/, indicators/, regime, sizing)
  test               Run pytest (with coverage gate from pyproject.toml)
  all                Run the daily DAG (data -> rank -> report)
  clean              Remove caches and build artifacts (does NOT remove uv.lock or data/)
```

`make data && make rank && make report && make backtest` exit 0 with 7 stub log lines (4 from `data`, 1 each from `rank`, `report`, `backtest`):

```
{"command": "refresh-universe", "message": "[stub] refresh-universe not yet implemented", ...}
{"command": "refresh-ohlcv", "message": "[stub] refresh-ohlcv not yet implemented", ...}
{"command": "refresh-macro", "message": "[stub] refresh-macro not yet implemented", ...}
{"command": "refresh-fundamentals", "message": "[stub] refresh-fundamentals not yet implemented", ...}
{"command": "score", "message": "[stub] score not yet implemented", ...}
{"command": "report", "message": "[stub] report not yet implemented", ...}
{"command": "backtest", "message": "[stub] backtest not yet implemented", ...}
```

Literal-token grep on the pre-registration doc:

```
$ grep -F '<weights frozen at Phase 4 completion>' docs/strategy_v1_preregistration.md
`<weights frozen at Phase 4 completion>`
2. Replace the literal token `<weights frozen at Phase 4 completion>` with the date, e.g., `Frozen on 2026-MM-DD`.
```

## Decisions Made

None beyond the plan — all decisions (recipe contract, .PHONY everywhere, awk help pattern, pre-registration doc structure) were locked in CONTEXT.md and the plan body. Plan executed verbatim.

## Deviations from Plan

None — plan executed exactly as written. Both task action blocks contained literal file content; both were written verbatim.

## Issues Encountered

None.

## Threat Surface Notes

No new threat surface beyond what the plan's `<threat_model>` already covers (T-04-01..04). Specifically:

- **T-04-01 (Makefile recipe drift)**: Mitigation in place — `tests/test_cli_smoke.py` (Plan 03) locks the D-14 subcommand surface; if a subcommand is renamed, the smoke test fails before the Makefile recipe breaks in CI.
- **T-04-02 (pre-registration token removed)**: CI grep gate deferred to Phase 4 per CONTEXT.md "Deferred Ideas". Phase 1 ships only the placeholder.
- **T-04-03 (recipe echoes secrets)**: Phase 1 stubs do not access `.env`; recipes echo only command names. Phase 2+ revisits.
- **T-04-04 (recipe runs forever)**: Phase 1 stubs return within ~100 ms each; full DAG completes in < 1 s.

## Self-Check: PASSED

- `Makefile` exists: FOUND
- `docs/strategy_v1_preregistration.md` exists: FOUND
- Commit `faf6f93` (feat 01-04 Makefile): FOUND in git log
- Commit `0546ff8` (docs 01-04 preregistration): FOUND in git log
- `make help` lists ≥ 6 target lines: FOUND (13 lines, well above the gate)
- End-to-end DAG `make data && make rank && make report && make backtest` exit 0: FOUND
- Literal token `<weights frozen at Phase 4 completion>` present: FOUND (2 occurrences)

## Next Phase Readiness

- FND-02 met. Phase 2 can extend Makefile recipes' bodies (via the typer CLI subcommands) without touching the Makefile contract.
- The pre-registration doc is the contract Phase 4 will fulfill: `<weights frozen at Phase 4 completion>` replaced with concrete weights + commit hash, TBD cells filled in, freeze CI grep gate added at that time.
- Wave 4 (Plan 05: CI workflow + branch protection) is the only remaining Phase 1 plan. The CI workflow defined there will exercise `make lint`, `make typecheck`, `make test` — all already routed through `uv run` so the recipe layer is reusable.

---
*Phase: 01-repo-skeleton-ci-hygiene*
*Completed: 2026-05-02*
