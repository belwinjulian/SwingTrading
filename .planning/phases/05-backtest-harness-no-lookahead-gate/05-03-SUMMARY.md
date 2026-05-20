---
phase: 05-backtest-harness-no-lookahead-gate
plan: 3
subsystem: backtest
tags: [vectorbt, walk-forward, report, disclosure-header, yaml-frontmatter, cli, typer, slippage-tiers, regime-attribution, commons-clause]

# Dependency graph
requires:
  - phase: 05-backtest-harness-no-lookahead-gate (Wave 1, plan 05-01)
    provides: "screener.backtest.vbt_runner.{run, BacktestResult, SLIPPAGE_TIERS}; screener.backtest.metrics.{per_regime_breakdown, per_playbook_breakdown, CANONICAL_REGIMES}; BacktestResult.all_regime_returns long-format DataFrame (B-3)"
provides:
  - "screener.backtest.report.render_report — atomic markdown writer for reports/backtest-YYYY-MM-DD.md"
  - "BCK-06 disclosure header (YAML frontmatter, 9 keys + Commons Clause caveat)"
  - "BCK-01 OOS Sharpe distribution table (per-window + min/median/max summary)"
  - "BCK-05 per-regime breakdown — 3-row table (Confirmed Uptrend / Uptrend Under Pressure / Correction) sourced from BacktestResult.all_regime_returns via metrics.per_regime_breakdown"
  - "C-2 iter 3 empty-input WARN line (verbatim from RESEARCH §A Q11) for user-visible diagnosis of empty all_regime_returns"
  - "BCK-04 per-playbook attribution — single 'leader_hold' row (D-12 Phase-5 stub); Phase 6 swap-in seam preserved via per_playbook_breakdown reference"
  - "screener.cli.backtest filled body — replaces _stub('backtest') with configure_logging + lazy run/render_report imports + --start/--end typer options (W-5) + terminal summary print + structured backtest_ok/backtest_failed events"
affects:
  - "Phase 5 Wave 3 (05-05) — backtest-audit CLI reads the same disclosure header for audit check #1"
  - "Phase 5 Wave 3 (05-04) — backfill_snapshots populates data/snapshots/ so make backtest can produce a real report"
  - "Phase 6 — VCP/Qullamaggie detector ships per-trade DataFrame with playbook_tag column; the per-playbook section will auto-populate additional rows without restructuring"
  - "Phase 8 — GitHub Actions cron parses the YAML frontmatter (slippage_tiers, period_selection) programmatically via yaml.safe_load"

# Tech tracking
tech-stack:
  added: []  # No new third-party libs; pure stdlib + intra-layer imports
  patterns:
    - "Single-source-of-truth constants: SLIPPAGE_TIERS imported from vbt_runner, NOT duplicated (Pitfall 7)"
    - "Inline-copy of atomic-write helper (D-17 architecture boundary forbids cross-layer import of publishers/_write_text_atomic)"
    - "Verbatim WARN-line constant (EMPTY_REGIME_RETURNS_WARN_LINE) ties user-visible report string to canonical research source (RESEARCH §A Q11)"
    - "Lazy import inside CLI body — backtest layer pulled only on subcommand invocation, preserves architecture test gate"
    - "Subprocess hardening pattern: list-form argv + shell=False + check=False + graceful fallback (T-5-02)"

key-files:
  created:
    - "src/screener/backtest/report.py (378 lines) — render_report + 9 helpers + 3 module constants"
  modified:
    - "src/screener/cli.py — backtest body filled (lines 240-291), 9-subcommand surface preserved"
    - "tests/test_cli_smoke.py — Rule 3: removed 'backtest' from PHASE_1_STUBS list, added test_backtest_subcommand_no_longer_stub mirroring Phase 4 score/report pattern"

key-decisions:
  - "Inline-copied _write_text_atomic from publishers/report.py rather than importing — D-17 forbids backtest/ importing publishers/. Both helpers remain POSIX-atomic at os.replace()."
  - "Used stdlib subprocess.run with list-form argv (not git lib) for preregistration hash — T-5-02 mitigation; no shell injection surface; check=False so subprocess failure falls back to 'unknown' rather than crashing the report."
  - "Rule 3 (auto-fix blocking issue): removed 'backtest' from PHASE_1_STUBS list in test_cli_smoke.py and added test_backtest_subcommand_no_longer_stub. The plan body filled the stub; without updating the stub list, the existing test 'test_each_phase1_stub_exits_zero_with_stub_log' fails. This matches the exact pattern Phase 4 used for score/report when those stubs were filled."
  - "Used Annotated[..., typer.Option(...)] pattern for --start/--end to match the existing cli.py style (refresh-universe, refresh-ohlcv already use Annotated)."

patterns-established:
  - "Single-source-of-truth disclosure: report module imports SLIPPAGE_TIERS from vbt_runner; render code accesses tuple indices to emit YAML. Any future tier change in vbt_runner automatically propagates to the report."
  - "WARN-line constants for user-visible diagnostics: EMPTY_REGIME_RETURNS_WARN_LINE pattern can be reused in Phase 5 plan 05-05 (audit warnings) and Phase 6+ when other report-level failure modes need user-visible surfacing."

requirements-completed:
  - BCK-04
  - BCK-05
  - BCK-06

# Metrics
duration: 8min
completed: 2026-05-16
---

# Phase 5 Plan 3: backtest/report.py + cli.backtest body Summary

**Render `reports/backtest-YYYY-MM-DD.md` with full BCK-06 YAML disclosure header, OOS Sharpe distribution, real BCK-05 3-row per-regime breakdown (B-3 fix), C-2 iter-3 empty-input WARN line, BCK-04 leader_hold stub row — and wire `screener backtest` CLI body to call vbt_runner.run + render_report with --start/--end W-5 options.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-16T21:46:04Z
- **Completed:** 2026-05-16T21:53:53Z
- **Tasks:** 2/2
- **Files created:** 1 (`src/screener/backtest/report.py`)
- **Files modified:** 2 (`src/screener/cli.py`, `tests/test_cli_smoke.py`)

## Accomplishments

- `src/screener/backtest/report.py` ships with `render_report` + atomic-write helper + section renderers (frontmatter, Sharpe distribution, per-regime, per-playbook) + module constants (`SURVIVORSHIP_CAVEAT`, `COMMONS_CLAUSE_CAVEAT`, `EMPTY_REGIME_RETURNS_WARN_LINE`).
- BCK-06 disclosure header carries all 9 required YAML keys (`backtest_date`, `universe_source_date`, `survivorship_caveat`, `slippage_tiers`, `period_selection`, `regime_gate`, `playbook_attribution`, `preregistration`, `library_license`) plus the verbatim Commons Clause caveat per RESEARCH §E L3.
- B-3 iter 2: per-regime section renders all 3 canonical regimes (Confirmed Uptrend / Uptrend Under Pressure / Correction) from `result.all_regime_returns` via `metrics.per_regime_breakdown`. Empty regimes render as `0 | — | — | —` (not omitted).
- C-2 iter 3: empty-input WARN line (`> ⚠ No regime-attributed returns produced. See 05-RESEARCH.md §A Q11.`) emitted verbatim when `all_regime_returns.empty`. Surfaces empty-input fallback as user-visible diagnostic; structural 3-row table still renders below for layout consistency.
- B-1: every log call in `backtest/report.py` uses stdlib f-string form; kwarg-pattern grep returns empty; smoke logging script runs without `TypeError`.
- `screener backtest` body wires `vbt_runner.run()` + `render_report()`; accepts `--start` (default 2016-01-01) and `--end` (default today) typer options (W-5) without adding a 10th subcommand. Terminal summary line + report path printed to stdout per D-14.
- 9-subcommand CLI surface preserved (D-18); `test_cli_smoke.py::test_help_lists_all_d14_subcommands` passes.
- Architecture test (`tests/test_architecture.py`) still passes — `backtest/report.py` imports only stdlib + intra-layer (`screener.backtest.vbt_runner`, `screener.backtest.metrics`); no `structlog`, no `config`, no `obs`, no `signals`/`indicators`/`data`/`publishers`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/screener/backtest/report.py** — `a505b6f` (feat)
2. **Task 2: Fill src/screener/cli.py backtest command body (+ Rule 3 test-list update)** — `59f90f9` (feat)

_Total: 2 commits across 3 files. Final SUMMARY commit follows._

## Files Created/Modified

- **Created:** `src/screener/backtest/report.py` (378 lines) — `render_report`, `_write_text_atomic`, `_resolve_universe_source_date`, `_resolve_preregistration_hash`, `_render_frontmatter`, `_render_sharpe_distribution_section`, `_render_per_regime_section`, `_render_per_playbook_section`, `_format_metric`, `_is_nan`, plus `COMMONS_CLAUSE_CAVEAT`, `SURVIVORSHIP_CAVEAT`, `EMPTY_REGIME_RETURNS_WARN_LINE` constants.
- **Modified:** `src/screener/cli.py` — `backtest` body filled (replaced `_stub("backtest")`); added `--start`/`--end` `Annotated[..., typer.Option(...)]` parameters; lazy imports of `run` and `render_report` inside body; terminal summary print + `backtest_ok`/`backtest_failed` structured events.
- **Modified:** `tests/test_cli_smoke.py` — removed `"backtest"` from `PHASE_1_STUBS` list (Rule 3 fix; mirrors Phase 4 score/report); added `test_backtest_subcommand_no_longer_stub` for independent exit-coverage.

## Decisions Made

- **Inline-copied `_write_text_atomic` from `publishers/report.py`** rather than importing — D-17 forbids `backtest/` from importing `publishers/`. Both helpers remain POSIX-atomic at the `os.replace()` step; the report variant matches publishers/report.py iter-3 (write-inside-with) discipline.
- **Used `subprocess.run` with list-form argv + `check=False`** for the preregistration hash lookup — T-5-02 mitigation; no shell injection surface; graceful fallback to `"unknown"` if git is unavailable or the doc has no commits.
- **Rule 3 fix to test_cli_smoke.py** — when filling the `backtest` stub, the `PHASE_1_STUBS` list must lose `"backtest"` so `test_each_phase1_stub_exits_zero_with_stub_log` no longer expects a `[stub]` line from it. Added `test_backtest_subcommand_no_longer_stub` for independent positive coverage (matches the Phase 4 `score`/`report` precedent in the same file).
- **Used `Annotated[..., typer.Option(...)]` syntax** for `--start`/`--end` to match the existing `refresh-universe` / `refresh-ohlcv` style in cli.py. Default value follows the `= "2016-01-01"` / `= None` form expected by typer for Annotated options.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] tests/test_cli_smoke.py PHASE_1_STUBS list out of sync after backtest body filled**

- **Found during:** Task 2 verification (`pytest tests/test_cli_smoke.py -v`)
- **Issue:** `test_each_phase1_stub_exits_zero_with_stub_log` loops `PHASE_1_STUBS = [..., "backtest", ...]` and asserts each subcommand exits 0 with a `[stub]` log message. After Task 2 filled the `backtest` body, the test fails with `assert 1 == 0` because `screener backtest` now exits 1 (RuntimeError when `data/snapshots/` is empty — expected per L10 hard-fail).
- **Fix:** Removed `"backtest"` from `PHASE_1_STUBS`; added `test_backtest_subcommand_no_longer_stub` mirroring the existing Phase 4 `test_score_subcommand_no_longer_stub` and `test_report_subcommand_no_longer_stub` pattern (same file). Confirms that invoking `backtest` does NOT emit a `[stub]` log line, while still letting the harness fail loudly on missing data.
- **Files modified:** `tests/test_cli_smoke.py`
- **Verification:** `uv run --extra dev pytest tests/test_cli_smoke.py -q` → 10 passed (was 8 before + 1 failed; now 10 passed). Architecture test still passes.
- **Committed in:** `59f90f9` (part of Task 2 commit; the test-list and the body change are coupled — same Rule 3 mechanism Phase 4 used for `score`/`report`).
- **Why not Rule 4 (architectural):** This is the same surface-locked stub-list maintenance pattern Phase 4 established (`score` removed from list, replaced with `test_score_subcommand_no_longer_stub`); no architectural decision required.

**No other deviations.** The plan executed as written. The plan's verify block predicted `screener backtest 2>&1 | tail -5` would log `backtest_failed error_type=RuntimeError`; the actual error type is `FileNotFoundError` (raised by `read_panel(end)` before `_load_snapshots_in_range` is reached, because `data/ohlcv/` is also empty in the worktree). Both errors are caught by the same `except Exception` block, log `backtest_failed`, and exit 1. The plan's contract ("exit 1 + structured failure event") is satisfied; the specific error_type depends on which empty-data check fires first.

## Smoke-Test Outputs

### Non-empty `all_regime_returns` render — first 30 lines of `/tmp/test-backtest-report.md`

```markdown
---
backtest_date: 2026-05-16
universe_source_date: 2026-04-27
survivorship_caveat: |
  Universe is the iShares IWB constituent list as of universe_source_date.
  Historical members of Russell 1000 who were delisted before that date are NOT in the test set.
  This introduces a known upward bias of ~1-2% CAGR.
  Mitigation: walk-forward OOS sliding window reduces single-period overfit.
slippage_tiers:
  - adv_gt: 50000000  # $50M
    bps: 5
  - adv_range: [5000000, 50000000]  # $5M-$50M
    bps: 15
  - adv_lt: 5000000  # $5M
    bps: 30
period_selection:
  is_years: 3
  oos_years: 1
  slide_years: 1
  windows_count: 0
regime_gate:
  type: soft
  formula: composite_score *= regime_score  # see publishers/pipeline.apply_regime_gate
playbook_attribution:
  status: stubbed
  note: All picks tagged 'leader_hold' until Phase 6 ships VCP/Qullamaggie detectors.
preregistration:
  weights_hash: abc123
  doc: docs/strategy_v1_preregistration.md
library_license:
```

### Empty-case (`pd.DataFrame()`) render — Per-Regime section (lines 44–55 of `/tmp/test-backtest-report-empty.md`)

```markdown
## Per-Regime Breakdown (BCK-05)

Per-day OOS portfolio return attributed to the regime active on that date (sourced from `regime_state` in `data/snapshots/*.parquet`, D-13). Empty rows indicate no OOS days observed in that regime.

> ⚠ No regime-attributed returns produced. See 05-RESEARCH.md §A Q11.

| Regime | N Days | Total Return | Sharpe | Win Rate |
|--------|--------|--------------|--------|----------|
| Confirmed Uptrend | 0 | — | — | — |
| Uptrend Under Pressure | 0 | — | — | — |
| Correction | 0 | — | — | — |
```

**Confirms:** WARN line PRESENT verbatim (C-2 iter 3) AND all 3 fallback rows render with `0 | — | — | —` for structural consistency.

## Verification Evidence

### Success criteria 1: `pytest tests/test_cli_smoke.py tests/test_architecture.py` exits 0

```
uv run --extra dev pytest tests/test_cli_smoke.py tests/test_architecture.py --no-cov
13 passed in <X>s
rc=0
```

(Coverage gate FAIL from pytest-cov is the project-wide 80% threshold; running these two files in isolation hits 28% which doesn't influence the actual test exit code.)

### Success criterion 2: smoke render produces valid markdown with all 9 YAML keys

All 9 YAML keys present in `/tmp/test-backtest-report.md`: `backtest_date:`, `universe_source_date:`, `survivorship_caveat:`, `slippage_tiers:`, `period_selection:`, `regime_gate:`, `playbook_attribution:`, `preregistration:`, `library_license:`. Commons Clause caveat string present in `library_license.caveat`. Verified by grep loop in smoke script.

### Success criterion 3 (B-3): all 3 canonical regime rows render

Non-empty render: `OK row: Confirmed Uptrend`, `OK row: Uptrend Under Pressure`, `OK row: Correction` (smoke script).

Empty render: all 3 rows present as `| <regime> | 0 |` lines (smoke script grep).

### Success criterion 4 (B-1): no kwarg-pattern log calls

```
grep -nE '^\s*log\.(info|warning|error|debug)\("[a-z_]+",' src/screener/backtest/report.py
(empty)
```

Smoke logging script (`logging.basicConfig(...)` + `report.log.info(f'smoke_test path=/tmp/foo n=5 median=1.23')`) → printed "logging ok"; no TypeError.

### Success criterion 5 (C-2 iter 3): WARN line in empty case, absent in non-empty case

Empty smoke test: WARN line PRESENT verbatim → `OK: C-2 WARN line PRESENT (empty all_regime_returns) - iter 3 fix verified`.

Non-empty smoke test: WARN line ABSENT → `OK: C-2 WARN line ABSENT (non-empty all_regime_returns)`.

### Success criterion 6: `screener backtest` with no snapshots exits 1 + logs failure

```
$ uv run screener backtest > /dev/null 2>&1; echo "exit=$?"
exit=1

$ uv run screener backtest 2>&1 | tail -2
run_start start=2016-01-01 end=2026-05-16 n_windows=7 lookahead=False
{"error_type": "FileNotFoundError", "event": "backtest_failed", "level": "error", "timestamp": "2026-05-16T21:52:59.013286Z"}
```

Exit 1, structured `backtest_failed` event, `error_type` only (no `error=str(e)` leak per T-3-02). The plan's verify section predicted `RuntimeError`, but in the worktree `data/ohlcv/` is also empty so `read_panel(end)` raises `FileNotFoundError` BEFORE `_load_snapshots_in_range` is reached. Both errors are caught by the same `except Exception` block and exit 1; the plan's contract ("exit 1 + structured failure event") is satisfied either way.

### Success criterion 7 (W-5): `--start` and `--end` options accepted

```
$ uv run screener backtest --start 2020-01-01 --end 2024-12-31 2>&1 | tail -2
run_start start=2020-01-01 end=2024-12-31 n_windows=2 lookahead=False
{"error_type": "FileNotFoundError", "event": "backtest_failed", ...}
```

Typer accepted both options without `BadParameter`; the harness computed `n_windows=2` for the narrowed range (2020-2024 = 5 years = 2 OOS windows after 3-yr IS warmup). Confirms W-5 wiring is live.

### Success criterion 8: 9-subcommand surface preserved (D-18)

`test_help_lists_all_d14_subcommands` passes. `screener --help` lists exactly the original 9 subcommands: `refresh-universe`, `refresh-ohlcv`, `refresh-macro`, `refresh-fundamentals`, `score`, `report`, `journal`, `backtest`, `backtest-audit`. The `--start`/`--end` options are added to the existing `backtest` subcommand (W-5), not as a new command.

### Success criterion 9: BCK-06 5 required disclosure fields present

`universe_source_date`, `survivorship_caveat`, `slippage_tiers`, `period_selection`, `regime_gate` all present in the rendered YAML (verified by smoke grep). Plus 4 extras: `backtest_date`, `playbook_attribution`, `preregistration`, `library_license`.

## Architectural Contract Compliance

- **D-17 (backtest/ imports persistence + stdlib only):** `report.py` imports `stdlib + screener.backtest.vbt_runner + screener.backtest.metrics` only (intra-layer is allowed). No `structlog`, no `config`, no `obs`, no `signals`/`indicators`/`data`/`publishers`. Verified by `grep -RnE "^(from|import) (structlog|screener\.(config|obs|signals|indicators|regime|sizing|publishers|data))" src/screener/backtest/report.py` → empty (only a docstring-text match on line 14 referencing the `log.info("event", key=...)` antipattern).
- **D-18 (9-subcommand surface locked):** No new subcommand added; `--start`/`--end` are options on the existing `backtest` subcommand. `tests/test_cli_smoke.py::test_help_lists_all_d14_subcommands` passes.
- **D-14 (terminal summary + file):** `make backtest` (equivalent: `uv run screener backtest`) writes `reports/backtest-{end}.md` and prints two stdout lines (`Sharpe distribution: ...` summary + `Report written: ...`).
- **D-15 (user commits the report manually):** `render_report` writes the file but the CLI does NOT auto-commit. Consistent with `make report` (Phase 4) behavior.
- **B-1 fix iter 2:** all log calls in `backtest/report.py` use stdlib f-string form; grep `^\s*log\.(info|warning|error|debug)\("[a-z_]+",` returns empty.
- **B-3 fix iter 2:** `_render_per_regime_section` consumes `result.all_regime_returns` via `metrics.per_regime_breakdown`; always renders 3 canonical regime rows.
- **C-2 fix iter 3:** `EMPTY_REGIME_RETURNS_WARN_LINE` emitted verbatim from RESEARCH §A Q11 when `all_regime_returns.empty`.
- **T-3-02 carry-forward:** CLI body logs `error_type=type(e).__name__` only — `grep "error=str(e)" src/screener/cli.py | <inside backtest body>` returns 0.
- **T-5-02 (subprocess.run hardening):** list-form argv, `shell=False` (default), `check=False`, graceful `"unknown"` fallback.

## Known Stubs

- **D-12 leader_hold per-playbook row:** `_render_per_playbook_section` emits a single `leader_hold` row aggregating all trades. Phase 6 will ship a real per-trade DataFrame with `playbook_tag`; the existing reference to `per_playbook_breakdown` (`_ = per_playbook_breakdown`) preserves the wiring point so Phase 6 can swap in real rows without restructuring this section. **Intentional, documented in plan and section header text.**
- **Phase 5 stub note in disclosure header `playbook_attribution.note`:** "All picks tagged 'leader_hold' until Phase 6 ships VCP/Qullamaggie detectors." **Intentional, machine-readable; Phase 6 plan can detect this status via YAML parse.**

No unintentional stubs.

## Threat Flags

No new threat surface introduced beyond what the plan's `<threat_model>` already mitigated (T-5-02 subprocess argv, T-5-03 universe stem). The `subprocess.run` call is the only new external surface (reads local git log) — mitigated by list-form argv, `shell=False`, `check=False`. The filesystem write to `reports/` uses the same atomic-rename pattern as `publishers/report.py`. No new auth, network, or schema surface.

## TDD Gate Compliance

N/A — this plan's tasks are both `type="auto" tdd="false"`. The TDD gate was satisfied at the harness level by plan 05-02 (test_backtest_no_lookahead.py mutation test, which is the FND-04 CI gate). This plan ships render code which is exercised by the smoke tests in the verify block (not standalone pytest tests — Phase 5 elected to defer dedicated report-rendering pytest cases to a future plan; the smoke tests cover the same contracts).

## Self-Check: PASSED

- [x] `src/screener/backtest/report.py` exists at expected path (378 lines, FOUND)
- [x] `src/screener/cli.py` modified, `backtest` body filled (FOUND, line 240)
- [x] `tests/test_cli_smoke.py` modified, `PHASE_1_STUBS` updated (FOUND)
- [x] Commit `a505b6f` exists in git log (FOUND)
- [x] Commit `59f90f9` exists in git log (FOUND)
- [x] No deletions in any commit (`git diff --diff-filter=D` empty for both)
- [x] All 13 tests pass (`tests/test_cli_smoke.py` + `tests/test_architecture.py`) — exit 0
- [x] Ruff clean on both modified files (`uv run --extra dev ruff check src/screener/backtest/report.py src/screener/cli.py` → All checks passed)
- [x] Non-empty smoke render produces all 3 regime rows + NO WARN line
- [x] Empty smoke render produces all 3 regime rows + WARN line verbatim
- [x] B-1 grep returns empty (no real kwarg violations; only docstring text mention)
- [x] EMPTY_REGIME_RETURNS_WARN_LINE constant defined + emitted (grep -c ≥2)
- [x] CLI `screener backtest` exit 1 + `backtest_failed` event on missing data (verified)
- [x] CLI `screener backtest --start 2020-01-01 --end 2024-12-31` accepted (W-5 verified)
- [x] 9-subcommand surface preserved (`test_help_lists_all_d14_subcommands` passes)
