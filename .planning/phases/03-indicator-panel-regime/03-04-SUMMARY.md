---
phase: 03-indicator-panel-regime
plan: "04"
subsystem: regime
tags:
  - regime
  - market-state
  - sizing-seam
  - distribution-days
  - tdd
  - hypothesis

dependency_graph:
  requires:
    - phase: 03-01
      provides: persistence.read_macro_spy, read_macro_vix, MacroOhlcvSchema, VixSchema, Settings REGIME_* fields
    - phase: 03-03
      provides: indicators.build_panel returning sma_200 column for breadth denominator
  provides:
    - regime.compute_for_date(date, panel) — 6-field Series (spy_above_200d, breadth_pct, distribution_days, vix_level, regime_state, regime_score)
    - regime.build_history(start, end) — 6-column DataFrame for Phase 5 backtest harness
    - regime._classify_state — D-01 priority chain (Correction > Pressure > Uptrend)
    - regime._compute_distribution_days — strict IBD rolling-25 counter
    - regime._regime_score — vectorized D-03 weighted blend in [0, 1]
    - regime.RegimeState — Literal type for the three discrete states
    - tests/test_regime.py — 13 unit tests covering D-01/D-02/D-03/Pitfall-11/REG-01..03
    - tests/test_regime_score.py — hypothesis property test for regime_score in [0, 1]
    - conftest fixtures: synthetic_spy_with_dist_days, synthetic_vix_calm
  affects:
    - 03-05 (golden-file regime tests for 2008-Q4/2020-Q1/2022-H1 consume regime.compute_for_date)
    - Phase 4 report banner (reads regime_state for traffic-light display)
    - Phase 5 backtest harness (BCK-05 consumes build_history for per-regime breakdown)
    - Phase 7 sizing (REG-03 seam: regime_score multiplies into base risk in sizing.py)

tech_stack:
  added: []
  patterns:
    - D-01 priority chain: Correction overrides everything — check Correction triggers first, then Uptrend, default Pressure
    - Pitfall-11 breadth denominator: use (close.notna() & sma_200.notna()) mask so post-IPO tickers without 200d history are excluded
    - vectorized _regime_score: single-pass formula on a DataFrame; call with 1-row frame from compute_for_date or multi-row from build_history
    - strict IBD distribution day: close/prev_close - 1 < -0.002 AND volume > prev_volume; rolling(window).sum().fillna(0).astype(int)
    - monkeypatch._macro_dir: integration tests use monkeypatch.setattr("screener.persistence._macro_dir", lambda: tmp_path) to isolate from real Parquet cache
    - hypothesis property test: @given(st.booleans(), st.floats(0,100), st.integers(0,20), st.floats(10,80)) verifies [0,1] invariant
    - type: ignore[arg-type] and type: ignore[misc] on two pandas .loc patterns that mypy cannot infer precisely but are correct at runtime

key_files:
  created:
    - tests/test_regime.py
    - tests/test_regime_score.py
  modified:
    - src/screener/regime.py
    - tests/conftest.py

key_decisions:
  - "Breadth denominator uses (close.notna() & sma_200.notna()) mask per Pitfall 11 — tested by test_breadth_pct_denominator_uses_valid_sma"
  - "Two mypy type: ignore annotations added for pandas .loc return types (arg-type on VIX close float cast; misc on string slice) — both are runtime-correct, not logic suppressions"
  - "test_regime_imports.py kept as a permanent smoke-test (verifies public API surface remains importable)"

requirements-completed:
  - REG-01
  - REG-02
  - REG-03

duration: 11min
completed: "2026-05-10"
---

# Phase 03 Plan 04: Regime Module Summary

**Three-state regime gate with continuous score — `compute_for_date` / `build_history` API backed by IBD distribution-day counter (D-02), D-01 Correction-priority classifier, and D-03 vectorized score blend**

## Performance

- **Duration:** ~11 minutes
- **Started:** 2026-05-10T18:56:00Z
- **Completed:** 2026-05-10T19:07:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4 (regime.py, conftest.py, test_regime.py new, test_regime_score.py new)

## Accomplishments

- Replaced 7-line stub with full `regime.py` body: 3 pure helpers + RegimeState type + `compute_for_date` + `build_history`
- D-01 priority chain encoded verbatim: Correction overrides Pressure regardless of breadth/VIX/dist when any Correction trigger fires (SPY < 200d, dist ≥ 9, VIX ≥ 30)
- D-02 distribution-day formula: strict IBD definition with rolling-25 window; volume filter correctly excludes non-higher-volume down days
- D-03 score weights: 0.30 spy + 0.40 breadth + 0.20 dist + 0.10 vix; vectorized; naturally in [0, 1] by construction
- Pitfall-11 breadth denominator: uses `has_data = close.notna() & sma_200.notna()` mask so post-IPO tickers without 200d history don't dilute breadth
- structlog `regime_computed` event emitted on every `compute_for_date` call with date/state/score
- 13 unit tests in `test_regime.py` + 1 hypothesis property test in `test_regime_score.py`; full suite 87 passed, 2 skipped

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | TDD RED gate: regime imports failing | `b29f278` | tests/test_regime_imports.py |
| 1 | Replace regime.py stub with full body | `0428462` | src/screener/regime.py |
| 2 | Add regime tests + conftest fixtures | `06df8d1` | tests/test_regime.py, tests/test_regime_score.py, tests/conftest.py |

## Files Created/Modified

- `src/screener/regime.py` — replaced 7-line stub with full body; 5 functions + RegimeState Literal; structlog event; mypy strict + ruff clean
- `tests/test_regime.py` — 13 tests: 5 `_classify_state` D-01 cases, 2 distribution-day cases, 2 score boundary cases, 4 `compute_for_date` integration tests including Pitfall-11 breadth denominator
- `tests/test_regime_score.py` — first hypothesis property test in the project; verifies `_regime_score` ∈ [0, 1] over 100 random inputs
- `tests/conftest.py` — added `synthetic_spy_with_dist_days` (50-bar SPY with exactly 4 strict-IBD dist days injected in last 25) and `synthetic_vix_calm` (VIX constant 15) under Phase 3 regime fixtures header

## Decisions Made

1. **Two `type: ignore` annotations in regime.py** — `vix.loc[date, "close"]` returns a type that mypy infers as a complex union (not directly `float`), and `df.loc[str(start):str(end)]` uses a string slice that mypy cannot verify. Both annotations are narrow and correct at runtime; no logic is being suppressed.

2. **Module docstring uses plain-language formula description** — avoids repeating the exact weight constants verbatim in the docstring (which would cause the D-03 acceptance criteria grep counts to return 2 instead of 1). The weight constants appear exactly once in the `_regime_score` function body.

3. **test_regime_imports.py kept as a permanent smoke test** — verifies the 6 public symbols remain importable after any future refactor of `regime.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy `arg-type` on `vix.loc[date, "close"]`**
- **Found during:** Task 1, mypy verification
- **Issue:** `vix.loc[date, "close"]` returns a pandas union type; `float()` constructor does not accept it without a type: ignore annotation under mypy strict mode
- **Fix:** Added `# type: ignore[arg-type]` on the VIX close cast line
- **Files modified:** `src/screener/regime.py`
- **Commit:** `0428462`

**2. [Rule 1 - Bug] mypy `misc` on string-slice `.loc[]`**
- **Found during:** Task 1, mypy verification
- **Issue:** `df.loc[str(start):str(end)]` in `build_history` triggers "Slice index must be an integer, SupportsIndex or None" under strict mypy
- **Fix:** Added `# type: ignore[misc]` on the date-range slice line
- **Files modified:** `src/screener/regime.py`
- **Commit:** `0428462`

---

**Total deviations:** 2 auto-fixed (both Rule 1 - mypy type precision)
**Impact on plan:** Both fixes are correct at runtime; no logic changed. No scope creep.

## Issues Encountered

- `dev` extras not installed in the worktree venv by default — ran `uv sync --extra dev` to install `mypy` and `ruff` before running acceptance criteria. One-time setup; not a recurring issue.

## Known Stubs

None — all regime computations are fully implemented with real pandas math. No placeholder returns or TODO paths.

## Threat Surface Scan

T-3-01 (mitigate) from the plan's threat model is addressed:
- `compute_for_date` reads SPY and VIX via `read_macro_spy()` and `read_macro_vix()` which both go through pandera-lazy-validated persistence readers — the schema validation is the trust boundary
- Breadth denominator uses `close.notna() & sma_200.notna()` mask per Pitfall 11, preventing biased breadth

No new threat flags — no new network endpoints, auth paths, or trust boundaries were introduced. `regime.py` reads only from pre-validated Parquet caches via `persistence`.

## Next Phase Readiness

- `compute_for_date(date, panel)` and `build_history(start, end)` are production-ready for Phase 4 report banner and Phase 5 backtest harness
- `regime_score` float field is the REG-03 seam; Phase 7 `sizing.py` wires it into base risk multiplication
- Plan 03-05 can proceed: it needs `compute_for_date` for the three golden-file regime tests (2008-Q4, 2020-Q1, 2022-H1) and the SMA-not-EMA CI grep gate

## Self-Check: PASSED

Files exist:
- src/screener/regime.py: FOUND (254 lines, full body)
- tests/test_regime.py: FOUND (13 tests)
- tests/test_regime_score.py: FOUND (hypothesis property test)
- tests/conftest.py: FOUND (fixtures added)

Commits exist:
- b29f278: FOUND (RED test)
- 0428462: FOUND (feat regime.py)
- 06df8d1: FOUND (feat tests)

---
*Phase: 03-indicator-panel-regime*
*Completed: 2026-05-10*
