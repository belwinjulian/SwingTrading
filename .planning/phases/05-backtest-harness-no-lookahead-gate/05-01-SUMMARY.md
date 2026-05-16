---
phase: 5
plan: 1
slug: backtest-harness-no-lookahead-gate
subsystem: backtest-harness
tags: [phase-5, wave-1, backtest, walkforward, slippage, vectorbt, no-lookahead, bck-01, bck-02, bck-03, bck-04, bck-05]
status: complete
completed: 2026-05-16
duration_minutes: 65
tasks_completed: 2
files_created: 3
files_modified: 3
dependency_graph:
  requires:
    - "Wave 0 (05-00): tests/conftest.py::synthetic_ohlcv_panel session fixture"
    - "Wave 0 (05-00): tests/test_walkforward_windows.py + tests/test_slippage_tiers.py skip-stub seeds"
    - "Phase 4: src/screener/persistence.py::read_panel() (single allowed internal import)"
    - "Phase 4: src/screener/publishers/snapshot.py (data/snapshots/<date>.parquet writer with regime_state column)"
    - "pyproject.toml: vectorbt 1.0.x, numpy 2.x, pandas 2.2.x (already installed)"
  provides:
    - "src/screener/backtest/walkforward.py::walk_forward_windows() - pure window-construction utility (BCK-01)"
    - "src/screener/backtest/metrics.py::oos_sharpe_distribution() (BCK-01)"
    - "src/screener/backtest/metrics.py::per_regime_breakdown() - long-format 3-row indexed DataFrame (BCK-05 / B-3)"
    - "src/screener/backtest/metrics.py::per_playbook_breakdown() - Phase 5 stub routes to leader_hold (BCK-04 / D-12)"
    - "src/screener/backtest/metrics.py::CANONICAL_REGIMES tuple"
    - "src/screener/backtest/vbt_runner.py::run(start, end, *, _lookahead=False) - public harness entry (BCK-01 + BCK-02 mutation surface)"
    - "src/screener/backtest/vbt_runner.py::BacktestResult dataclass with all_regime_returns (B-3)"
    - "src/screener/backtest/vbt_runner.py::WindowResult dataclass with regime_returns (B-3)"
    - "src/screener/backtest/vbt_runner.py::SLIPPAGE_TIERS tuple (D-11 single source of truth)"
    - "src/screener/backtest/vbt_runner.py::_build_slippage_panel() (BCK-03 / D-11)"
    - "src/screener/backtest/vbt_runner.py::_read_snapshot() (FND-04 monkeypatch seam)"
    - "src/screener/backtest/vbt_runner.py::_load_snapshots_in_range() (L10/L15 hard-fail guards)"
    - "src/screener/backtest/vbt_runner.py::_build_regime_returns_for_window() (C-2 hard-assert helper)"
    - "src/screener/backtest/vbt_runner.py::_validate_date() (T-5-01 regex gate)"
  affects:
    - "Plan 05-02 (FND-04 mutation test) - depends on _lookahead keyword-only param and _read_snapshot monkeypatch seam in vbt_runner"
    - "Plan 05-03 (report rendering) - depends on BacktestResult.all_regime_returns + metrics.per_regime_breakdown signature + SLIPPAGE_TIERS for disclosure header"
    - "Plan 05-04/05-05 - downstream CLI wiring + audit consume BacktestResult"
tech_stack:
  added:
    - "vectorbt 1.0.0 (already installed; first plan to call vbt.Portfolio.from_signals from production code)"
  patterns:
    - "vbt.Portfolio.from_signals with cash_sharing=True + group_by=np.zeros (L6, RESEARCH §A Q1) for single-portfolio aggregation across multi-ticker entries"
    - "ADV-tiered slippage via np.where chain (vectorized, no apply), NaN warmup filled with worst-tier default (L1, L5)"
    - "Signals execute at next-bar open via .shift(1, fill_value=False).astype(bool) - the literal FND-04/BCK-02 mutation surface (RESEARCH §A Q2)"
    - "stdlib logging.Logger with f-string event messages - NEVER structlog **kwargs (B-1 fix iter 2, RESEARCH §E L12)"
    - "Hard isinstance assert on pf.returns() with Q11 RESEARCH citation - replaces try/except graceful-degradation (C-2 fix iter 3)"
    - "Long-format DataFrame (date, regime_state, daily_return) for per-regime breakdown - B-3 fix iter 2 data shape"
key_files:
  created:
    - "src/screener/backtest/walkforward.py (60 lines, pure utility, stdlib + pandas only)"
    - "src/screener/backtest/metrics.py (199 lines)"
    - "src/screener/backtest/vbt_runner.py (444 lines)"
  modified:
    - "tests/test_walkforward_windows.py (Wave 0 3-skip stub -> 4 real tests, including worktree's >=2-window fixture-span override)"
    - "tests/test_slippage_tiers.py (Wave 0 3-skip stub -> 3 real tests)"
    - ".planning/phases/05-backtest-harness-no-lookahead-gate/05-RESEARCH.md (§A Q11: replaced placeholder with verbatim vbt 1.0.0 shape output)"
decisions:
  - "vectorbt 1.0.0's pf.returns() with cash_sharing+group_by returns pd.Series (not DataFrame as Q11 placeholder predicted) - hard isinstance assert handles both branches gracefully"
  - "Added a 4th walkforward test (>=2 windows for the conftest fixture span) per worktree's success-criteria override - uses 2024-01-31 end date so OOS=2023-12-31 fits cleanly"
  - "Renamed unused loop variable is_start -> _is_start (ruff B007) and replaced 2x unicode en-dash + 1x >= symbol with ASCII in test docstrings (ruff RUF002)"
  - "Added # noqa: PD010 to the 4 .unstack(level='ticker') call sites - precedent in src/screener/data/macro.py:422 (reshaping stacked MultiIndex; pivot_table is not equivalent)"
  - "Reformatted vbt_runner.py docstring's NEVER negative example from a code block to prose, so the B-1 kwarg-pattern grep gate returns empty (the example was tripping the regex even though it was a docstring teaching example)"
  - "Removed forward-quoted 'vbt.Portfolio' type annotation (we have from __future__ import annotations active - all annotations are strings by PEP 563, so quotes are redundant) per ruff UP037"
  - "Removed redundant int(len(...)) cast in metrics.per_regime_breakdown per ruff RUF046; switched subset.values -> subset.to_numpy() per ruff PD011"
threat_model_refs:
  - "T-5-01 (Tampering on user date strings) - mitigated: _validate_date regex enforced before Path() or pd.Timestamp() parse on start, end, and snapshot stems"
  - "T-5-03 (Tampering on snapshot parquet) - mitigated: defensive RuntimeError on NaN regime_state at re-read time; non-ISO snapshot stems skipped with warning log"
  - "T-5-04 (EoP via _lookahead production leakage) - mitigated: keyword-only argument (after *), underscore prefix, prominent docstring warning, visually flagged mutation-surface comment block (DO NOT REFACTOR). Plan 05-02 adds the automated FND-04 detection test."
requirements:
  complete:
    - "BCK-01 (walk-forward windows + OOS Sharpe distribution + ADV-tiered slippage harness scaffolding)"
    - "BCK-02 (next-bar-open execution via .shift(1, fill_value=False) on both entries AND exits in the run() else branch)"
    - "BCK-03 (ADV-tiered slippage panel 5/15/30 bps with NaN warmup defaulting to 30 bps)"
  partial:
    - "BCK-04 (per-playbook breakdown wired and tested; Phase 5 stub-routes all picks to leader_hold per D-12 - real qullamaggie_continuation/minervini_vcp rows ship in Phase 6)"
    - "BCK-05 (per-regime breakdown wired with long-format all_regime_returns + 3-row canonical output; plan 05-03 will render to markdown)"
metrics:
  duration: "~65 minutes"
  completed_date: "2026-05-16"
  baseline_tests_before: "134 passed, 13 skipped"
  baseline_tests_after: "141 passed, 7 skipped (+7 passing, -6 skipped: 3 walkforward + 3 slippage stubs flipped, +1 new fixture-span test added)"
  files_created: 3
  files_modified: 3
  lines_added_production: 703  # 60 + 199 + 444 (walkforward + metrics + vbt_runner)
---

# Phase 5 Plan 1: Backtest Harness Wave 1 - Walk-forward + Slippage + No-Look-Ahead Surface

**One-liner:** Built the vectorbt 1.0 walk-forward harness core (walkforward.py + metrics.py + vbt_runner.py, 703 production LOC) delivering BCK-01 (3yr IS / 1yr OOS sliding windows + OOS Sharpe distribution), BCK-02 (next-bar-open execution surface for FND-04), BCK-03 (ADV-tiered 5/15/30 bps slippage panel with NaN warmup default), and the BCK-04/BCK-05 data plumbing (long-format `all_regime_returns` for plan 05-03's per-regime renderer). D-17 architecture invariant intact (zero forbidden imports); B-1/B-3/C-2 iter-2/3 fixes applied verbatim; vectorbt 1.0.0's `pf.returns()` returns `pd.Series` (not `pd.DataFrame` as Q11 placeholder predicted) - hard isinstance assert handles both branches.

## Tasks Completed

| # | Name | Commit | Files | Tests |
|---|------|--------|-------|-------|
| 1 | walkforward.py + 4 BCK-01 unit tests (incl. worktree's fixture-span override) | `161d26e` | `src/screener/backtest/walkforward.py` (new), `tests/test_walkforward_windows.py` (filled) | 4 walkforward + 3 architecture pass |
| 2 | vbt_runner.py + metrics.py + 3 BCK-03 slippage tests | `e3ad1fe` | `src/screener/backtest/vbt_runner.py` (new), `src/screener/backtest/metrics.py` (new), `tests/test_slippage_tiers.py` (filled), `05-RESEARCH.md` §A Q11 (placeholder replaced) | 3 slippage + 4 walkforward + 3 architecture pass; 141 total pass / 7 skipped (baseline was 134/13) |

## Files Created / Modified

### Created (3)

| Path | Lines | Layer | Purpose |
|------|-------|-------|---------|
| `src/screener/backtest/walkforward.py` | 60 | backtest | Pure window-construction (stdlib + pandas only) - BCK-01 |
| `src/screener/backtest/metrics.py` | 199 | backtest | OOS Sharpe distribution, per-regime & per-playbook breakdowns - BCK-01/04/05 |
| `src/screener/backtest/vbt_runner.py` | 444 | backtest | vbt.Portfolio.from_signals harness with FND-04 _lookahead surface - BCK-01/02/03 |

### Modified (3)

| Path | Change |
|------|--------|
| `tests/test_walkforward_windows.py` | Wave 0 3-skip stub replaced with 4 real tests (canonical 7-window count + boundary equality + empty-too-short + worktree's >=2-windows-for-conftest-fixture-span override) |
| `tests/test_slippage_tiers.py` | Wave 0 3-skip stub replaced with 3 real tests (5 bps for $60M ADV / 30 bps for $4M ADV / 30 bps default for first 19 NaN warmup bars) |
| `.planning/phases/05-backtest-harness-no-lookahead-gate/05-RESEARCH.md` | §A Q11 placeholder replaced with verbatim vbt 1.0.0 actual output - documented Series-vs-DataFrame deviation |

## Exports (downstream consumers)

**Plan 05-02 (FND-04 mutation test) consumes:**
- `screener.backtest.vbt_runner.run(start, end, *, _lookahead=False)` - the public entry point
- `screener.backtest.vbt_runner._read_snapshot` - the documented monkeypatch seam
- `screener.backtest.vbt_runner._load_snapshots_in_range` - synthetic-panel injection point

**Plan 05-03 (markdown report renderer) consumes:**
- `screener.backtest.vbt_runner.BacktestResult.all_regime_returns` - long-format frame
- `screener.backtest.metrics.per_regime_breakdown(all_regime_returns)` - returns 3 canonical rows
- `screener.backtest.metrics.per_playbook_breakdown(trades)` - Phase 5 stub (leader_hold only)
- `screener.backtest.vbt_runner.SLIPPAGE_TIERS` - single source of truth for disclosure header
- `screener.backtest.metrics.CANONICAL_REGIMES` - canonical regime tuple

**Plan 05-04/05-05 (CLI + audit) consume:**
- `screener.backtest.vbt_runner.run` + entire `BacktestResult` shape
- `screener.backtest.metrics.oos_sharpe_distribution`

## Verification Results

| Check | Status | Detail |
|-------|--------|--------|
| `pytest tests/test_walkforward_windows.py -v --no-cov` | PASS | 4 tests pass (3 plan + 1 worktree override) |
| `pytest tests/test_slippage_tiers.py -v --no-cov` | PASS | 3 tests pass |
| `pytest tests/test_architecture.py -q --no-cov` | PASS | 3 tests pass including `test_backtest_does_not_import_data_layer` |
| Full suite `pytest -q --no-cov` | PASS | 141 passed, 7 skipped (baseline 134/13 + 7 new tests passing + 6 stubs removed) |
| `ruff check src/screener/backtest/ tests/test_walkforward_windows.py tests/test_slippage_tiers.py` | PASS | All checks passed |
| `mypy src/screener/indicators/ src/screener/signals/` | PASS | No issues found (backtest/ not in mypy scope per pyproject; covered by ruff + tests) |
| Forbidden-import grep (`structlog|screener.(config\|obs\|signals\|indicators\|regime\|sizing\|publishers\|data)` in `src/screener/backtest/`) | PASS | Empty - D-17 invariant intact |
| B-1 kwarg-pattern grep (`log.(info\|warning\|error\|debug)("[a-z_]+",`) in vbt_runner.py + metrics.py) | PASS | Empty - no stdlib Logger kwarg violations |
| B-1 logging smoke (`log.info(f"...")` invocations succeed without TypeError) | PASS | All 4 log call sites verified |
| C-2 helper-body grep (assert isinstance + Q11 citation each 1x; try / except Exception each 0x) | PASS | assert=1, Q11=1, try=0 |
| `_lookahead` mutation-surface grep (`if _lookahead`) | PASS | Match at vbt_runner.py:329 (inside run()) |
| `.shift(1, fill_value=False)` grep (mutation surface in else branch) | PASS | Matches at vbt_runner.py:333 + 334 (entries + exits in else branch) |
| `direction='longonly'` grep (L13) | PASS | Match at vbt_runner.py:350 |
| `cash_sharing=True` + `group_by=np.zeros` (L6) | PASS | Both match |
| Q11 shape-verification command run + actual output committed to RESEARCH.md | PASS | See §A Q11 - actual output is `pd.Series (10,)` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] vectorbt 1.0.0 `pf.returns()` API shape differs from Q11 placeholder prediction**

- **Found during:** Task 2 GREEN — Q11 shape-verification command on first successful run.
- **Issue:** RESEARCH §A Q11 placeholder claimed `pf.returns()` on a `cash_sharing=True` + `group_by=np.zeros(...)` Portfolio returns `<class 'pandas.core.frame.DataFrame'> (10, 1) Int64Index([0], dtype='int64')`. Actual vectorbt 1.0.0 output is `<class 'pandas.core.series.Series'> (10,) None`. The grouped Portfolio collapses further to a Series, not a DataFrame.
- **Resolution:** No code change needed — the C-2 hard assert `isinstance(pf_returns, (pd.Series, pd.DataFrame))` plus existing branching (`if isinstance(pf_returns, pd.DataFrame): take iloc[:, 0]; else: pass-through`) handles both shapes by design. Committed the actual verbatim output back to `05-RESEARCH.md §A Q11` (replacing the placeholder) with an "Important deviation" note explaining why both isinstance branches matter going forward.
- **Files modified:** `.planning/phases/05-backtest-harness-no-lookahead-gate/05-RESEARCH.md`
- **Commit:** `e3ad1fe`

**2. [Rule 3 - Blocking] Plan's docstring NEVER-example tripped the B-1 kwarg-pattern grep gate**

- **Found during:** Task 2 verification — B-1 grep returned a positive match at vbt_runner.py:17.
- **Issue:** The plan's verbatim module docstring contained an indented code-block negative example `log.info("run_start", start=start, end=end, ...)` inside a `NEVER::` reStructuredText directive. The B-1 quality gate `grep -nE 'log.(info|warning|error|debug)("[a-z_]+",' src/screener/backtest/vbt_runner.py` matched this docstring line even though it is teaching-by-counterexample, not real code.
- **Resolution:** Refactored the docstring's NEVER example from a code block into prose: "NEVER the structlog-style `log.info(event, key=value)` call signature, which raises `TypeError` on the stdlib Logger." The pedagogical content is preserved; the grep gate now returns empty.
- **Files modified:** `src/screener/backtest/vbt_runner.py`
- **Commit:** `e3ad1fe`

**3. [Rule 3 - Blocking] Plan's verbatim code violated 6 ruff rules (PD010, PD011, RUF046, UP037, I001, B007, RUF002)**

- **Found during:** Task 1 and Task 2 ruff checks.
- **Issues + fixes:**
  - **B007** (unused loop variable): renamed `for is_start, is_end, ...` → `for _is_start, is_end, ...` in tests/test_walkforward_windows.py
  - **RUF002** (ambiguous unicode in docstring): replaced 2x `–` (en-dash) and 1x `≥` (greater-or-equal) with ASCII equivalents in test docstring (precedent: Wave 0 fixture, 05-00 SUMMARY decision #2)
  - **I001** (import ordering): re-sorted vbt_runner.py imports so `screener.backtest.walkforward` precedes `screener.persistence` (alphabetical within the internal-imports block)
  - **PD010** (prefer .pivot_table over .unstack): added `# noqa: PD010` to the 4 `.unstack(level="ticker")` call sites — these are reshape operations on a stacked MultiIndex; pivot_table is not equivalent. Precedent: `src/screener/data/macro.py:422`.
  - **UP037** (remove quotes from type annotation): `pf: "vbt.Portfolio"` → `pf: vbt.Portfolio` (PEP 563 is active via `from __future__ import annotations`, so quotes are redundant)
  - **RUF046** (unnecessary int cast): `n_days = int(len(subset))` → `n_days = len(subset)` (len() already returns int)
  - **PD011** (prefer .to_numpy()): `subset.values` → `subset.to_numpy()`
- **Files modified:** `tests/test_walkforward_windows.py`, `src/screener/backtest/vbt_runner.py`, `src/screener/backtest/metrics.py`
- **Commits:** `161d26e` (Task 1 ruff fixes), `e3ad1fe` (Task 2 ruff fixes)

**4. [Rule 2 - Worktree success-criteria override] Added 4th walkforward test for conftest fixture span**

- **Found during:** Plan execution — worktree-spawn message explicitly states "tests/test_walkforward_windows.py replaces its Wave 0 skip with real assertions (>=7 windows for 2016..2025; >=2 windows for the conftest fixture span)".
- **Issue:** The plan body only specifies 3 walkforward tests (count / boundaries / empty); the worktree's success criteria adds a 4th test requirement for the conftest fixture span.
- **Resolution:** Added `test_walkforward_at_least_two_windows_for_conftest_fixture_span` using end-date `2024-01-31` (within the 1300-bday fixture's calendar span) — the test asserts `len(windows) >= 2` which holds since the function produces `[(2019..2021, 2022), (2020..2022, 2023)]` for that range. Wave 0 SUMMARY anticipated this need and documented it as Plan 05-01's responsibility (deviation #1 in 05-00-SUMMARY).
- **Files modified:** `tests/test_walkforward_windows.py`
- **Commit:** `161d26e`

### Out-of-Scope Discoveries (NOT fixed)

- **`pytest -q` runtime is ~100s for the full suite.** First-time vectorbt JIT compilation accounts for most of the cost (no test in this plan depends on vbt across multiple invocations). Subsequent runs would be faster. Not a regression of this plan.
- The full pre-existing `ruff check tests/` runs from the 05-00 SUMMARY (19 errors in other test files) are still present. Same rationale as 05-00: out of scope; we only touched test_walkforward_windows.py + test_slippage_tiers.py + production source under src/screener/backtest/.

## Authentication Gates

None. Backtest harness is offline (D-17): reads disk artifacts only, no network/auth surface.

## Key Decisions Made

- **Q11 RESEARCH.md update committed inline with Task 2** rather than as a separate commit — the actual output verification is part of the GREEN gate per the plan's "first GREEN run" directive, and the discovery (Series, not DataFrame) is part of why C-2's hard assert is correct.
- **Honored plan verbatim where possible.** Three small departures: (1) ruff fixes (8 rules) noted above, (2) docstring NEVER-example reformat to satisfy the B-1 grep gate, (3) added 4th walkforward test per worktree success-criteria override. All other 660+ lines of production code match the plan's `<action>` blocks character-for-character.
- **No mypy run on `src/screener/backtest/` was added** — per project pyproject scope, mypy runs on `indicators/` and `signals/` only. Backtest layer is covered by ruff (type-aware lint) + pytest (runtime correctness via test_architecture and the new BCK tests).

## Known Stubs

- `per_playbook_breakdown` (metrics.py): Phase 5 stub per D-12 — all picks are tagged `leader_hold`. Phase 6 will add real `qullamaggie_continuation` and `minervini_vcp` rows without structural change. This is intentional and called out in the function's docstring.

No unintentional stubs that would prevent plan goal achievement.

## Threat Flags

None. All new surface is enumerated in the plan's `<threat_model>` block (T-5-01, T-5-03, T-5-04) and mitigated in the implementation:
- T-5-01: `_validate_date` regex on every user-supplied date string
- T-5-03: defensive `RuntimeError` on NaN regime_state; non-ISO snapshot stems skipped
- T-5-04: keyword-only `*` separator + underscore prefix + DO NOT REFACTOR visual flag; automated FND-04 detection lands in plan 05-02

## TDD Gate Compliance

Plan frontmatter declares `type: execute` (not `type: tdd`), but each individual task carries `tdd="true"`. RED/GREEN cycle observed for both tasks:

- **Task 1 RED:** `pytest tests/test_walkforward_windows.py -v --no-cov` → `ModuleNotFoundError: No module named 'screener.backtest.walkforward'` ✓
- **Task 1 GREEN:** Same command after creating walkforward.py → 4/4 pass ✓
- **Task 1 REFACTOR:** Ruff fixes (rename `_is_start`, ASCII docstring) — tests still 4/4 pass ✓
- **Task 2 RED:** `pytest tests/test_slippage_tiers.py -v --no-cov` → `ModuleNotFoundError: No module named 'screener.backtest.vbt_runner'` ✓
- **Task 2 GREEN:** Same command after creating vbt_runner.py + metrics.py → 3/3 pass ✓
- **Task 2 REFACTOR:** Ruff fixes (imports, noqa PD010, UP037, RUF046, PD011) + docstring NEVER-example reformat — tests still 3/3 pass ✓

Per-task commits use `feat(05-01): ...` rather than separate `test(...)` + `feat(...)` because each task ships its production file and its filling-the-stub test atomically (the test cannot import the new symbol until the production file exists, so a separate `test:` commit would not compile).

## Commits

1. `161d26e` - `feat(05-01): add walk_forward_windows + BCK-01 unit tests` (2 files, +130/-15)
2. `e3ad1fe` - `feat(05-01): add vbt_runner + metrics + BCK-03 slippage tests` (4 files, +669/-17)

## Self-Check: PASSED

**Created files (verified on disk):**
- FOUND: `src/screener/backtest/walkforward.py`
- FOUND: `src/screener/backtest/metrics.py`
- FOUND: `src/screener/backtest/vbt_runner.py`

**Modified files (verified on disk):**
- FOUND: `tests/test_walkforward_windows.py` (no `pytest.skip` calls remaining)
- FOUND: `tests/test_slippage_tiers.py` (no `pytest.skip` calls remaining)
- FOUND: `.planning/phases/05-backtest-harness-no-lookahead-gate/05-RESEARCH.md` (Q11 actual output committed)

**Commits exist in git log:**
- FOUND: `161d26e` (Task 1)
- FOUND: `e3ad1fe` (Task 2)

**Behavioral assertions:**
- PASS: 4 walkforward + 3 slippage tests pass (BCK-01 + BCK-03 unit coverage)
- PASS: `test_architecture.py` 3/3 (D-17 invariant intact)
- PASS: Full suite 141 passed / 7 skipped (vs. baseline 134/13 — net +7 passing, -6 skipped)
- PASS: B-1 grep gate empty (no stdlib Logger kwarg violations)
- PASS: C-2 grep gate (1x assert + 1x Q11 citation + 0x try/except in helper body)
- PASS: Forbidden-import grep empty (no structlog / no screener.{config,obs,signals,indicators,data})
- PASS: `_lookahead` + `.shift(1, fill_value=False)` mutation surface present in run() else branch
- PASS: Q11 verification command run; actual output committed to RESEARCH.md (Series, not DataFrame as placeholder predicted)
