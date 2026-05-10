---
phase: "04"
plan: "02"
subsystem: signals
tags: [signals, trend-template, minervini, pure-function, tdd, sma-only, nan-safe]
dependency_graph:
  requires: [04-01]
  provides: [passes_trend_template function, trend_template_score column, passes_trend_template column]
  affects: [04-03-composite, 04-04-publishers]
tech_stack:
  added: []
  patterns: [pd.concat-based summation for mypy-safe Int64 series sum, groupby-shift per-ticker cond3, fillna-bool NaN coercion chain]
key_files:
  created:
    - src/screener/signals/minervini.py
    - tests/test_signals_minervini.py
  modified: []
decisions:
  - "Used pd.concat over built-in sum() for the 8-condition score sum — sum() on a generator of pd.Series returns Union[int, Series] per mypy; pd.concat+sum(axis=1) gives a clean Series type"
  - "Fixed test uptrend drift from 0.1% to 0.2% — 0.1% (1.001 daily) fails condition 6 (close >= 1.30 * low_52w) on a 300-bar panel because 1.30 * low_52w exceeds close at bar 300; 0.2% provides enough spread"
  - "Short-history test uses all-NaN indicator columns (not just NaN rs_rating) — even sma_50 produces a value at bar 50 on a 50-bar panel which allows cond5 to fire; setting all columns to NaN ensures score == 0 as specified"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-05-10"
  tasks_completed: 2
  files_changed: 2
---

# Phase 04 Plan 02: signals/minervini.py — SIG-01 Trend Template Gate Summary

**One-liner:** Pure-function `passes_trend_template(panel)` implementing all 8 Minervini SMA conditions with per-ticker shift (cond 3), NaN-safe boolean coercion (Pitfall 3), and Int64 scoring — 5 unit tests all green.

## What Was Built

### Task 1 + 2 (TDD): signals/minervini.py + tests/test_signals_minervini.py

Followed RED/GREEN/REFACTOR TDD cycle:
- **RED commit** (`c3bea66`): `tests/test_signals_minervini.py` written first; collection fails with `ModuleNotFoundError: screener.signals.minervini`
- **GREEN commit** (`7ee4b1a`): `src/screener/signals/minervini.py` created; all 5 tests pass; ruff + mypy clean

#### Module: src/screener/signals/minervini.py

Pure function `passes_trend_template(panel: pd.DataFrame) -> pd.DataFrame` — 90 lines, within the 60-110 bound specified.

**8 conditions implemented (lines 58-75):**

| Line | Cond | Formula |
|------|------|---------|
| 58 | 1 | `(close > sma_150) & (close > sma_200)` |
| 59 | 2 | `sma_150 > sma_200` |
| 60 | 3 | `sma_200 > sma_200.groupby(level="ticker").shift(22)` |
| 61 | 4 | `(sma_50 > sma_150) & (sma_50 > sma_200)` |
| 62 | 5 | `close > sma_50` |
| 63 | 6 | `close >= 1.30 * low_52w` |
| 64 | 7 | `close >= 0.75 * high_52w` |
| 65 | 8 | `rs_rating >= 70` |

**NaN-safety strategy (lines 68-73):**
```python
conds = [cond1, ..., cond8]
bool_conds: list[pd.Series] = [c.fillna(False).astype(bool) for c in conds]
score: pd.Series = pd.concat(
    [bc.astype("Int64") for bc in bool_conds], axis=1
).sum(axis=1).astype("Int64")
```
Any NaN in any input (insufficient history, missing column) causes that condition to be False and the score decremented by 1. Avoids the `pd.NA & bool` ambiguous error (Pitfall 3).

**Per-ticker shift for cond 3 (line 58):**
```python
sma_200_22d_ago = sma_200.groupby(level="ticker").shift(22)
```
Prevents naked `.shift(22)` MultiIndex bleed across tickers (Pitfall 2). Verified by `test_per_ticker_shift_no_bleed_pitfall_2`.

**Output columns:**
- `trend_template_score`: `pd.Int64Dtype()`, values in [0, 8]
- `passes_trend_template`: `bool`, True iff score == 8

#### Tests: tests/test_signals_minervini.py

5 tests, all pass in ~0.15s:

| Test | What it verifies |
|------|-----------------|
| `test_eight_conditions` | 300-bar uptrend (0.2% daily drift) → score 8 at last bar, passes True |
| `test_score_dtype_and_range` | `trend_template_score.dtype == pd.Int64Dtype()`, values in [0, 8] |
| `test_short_history_safe` | 50-bar all-NaN panel → score 0, passes False, no exception |
| `test_pass_rate_smoke` | 2-ticker fixture (AAA uptrend + BBB downtrend) → pass_rate == 0.5 |
| `test_per_ticker_shift_no_bleed_pitfall_2` | Adversarial unsorted 2-ticker panel; AAA scores 8, BBB scores <= 1 |

## Deviations from Plan

### Auto-fixed Issues (Rule 1 — Bug in Specified Test Parameters)

**1. [Rule 1 - Bug] Uptrend drift 0.1% insufficient for condition 6**
- **Found during:** Task 1 GREEN phase (test_eight_conditions failed with score 7)
- **Issue:** Plan specified `1.001 ** np.arange(n_bars)` (0.1% daily drift). With 300 bars, `close = 134.8`, `low_52w = 104.9`, `1.30 * low_52w = 136.4 > 134.8` — condition 6 fails, score is 7 not 8. This is mathematically unavoidable: `(1.001)^251 ≈ 1.285 < 1.30` so 252-bar lookback never satisfies cond 6 with 0.1% drift.
- **Fix:** Changed `_make_uptrend_panel` to use `1.002 ** np.arange(n_bars)` (0.2% daily drift); `(1.002)^251 ≈ 1.66 > 1.30` — cond 6 passes comfortably.
- **Files modified:** `tests/test_signals_minervini.py`
- **Commit:** `7ee4b1a`

**2. [Rule 1 - Bug] Short-history test with mixed NaN/real columns still scores 1**
- **Found during:** Task 2 GREEN phase (test_short_history_safe failed with score 1 at last bar)
- **Issue:** Plan's `_make_uptrend_panel("AAA", n_bars=50)` has real `sma_50` values. At bar 50, `close > sma_50` (cond 5) fires because close > mean of rising series. Score is 1 at the last bar, not 0.
- **Fix:** Short-history test now constructs a panel with ALL indicator columns as NaN (sma_50, sma_150, sma_200, high_52w, low_52w, rs_rating=pd.NA). This correctly simulates what `build_panel` produces during warmup: all SMAs NaN until their lookback is satisfied.
- **Files modified:** `tests/test_signals_minervini.py`
- **Commit:** `7ee4b1a`

**3. [Rule 1 - Bug] mypy --strict: sum() over generator returns Union[int, Series]**
- **Found during:** Task 1 verification (mypy error on `(score == 8).fillna(False)`)
- **Issue:** `sum(bc.astype("Int64") for bc in bool_conds)` types as `Series[int] | Literal[0]` under mypy --strict; can't call `.fillna()` on the union.
- **Fix:** Replaced with `pd.concat([bc.astype("Int64") for bc in bool_conds], axis=1).sum(axis=1).astype("Int64")` which gives a typed `pd.Series`.
- **Files modified:** `src/screener/signals/minervini.py`
- **Commit:** `7ee4b1a`

## CI Gate Status

| Gate | Result |
|------|--------|
| IND-02: `grep -ilE "ema" src/screener/signals/minervini.py` | PASS (0 matches) |
| D-16: `test_layer_import_contract` | PASS |
| D-16: `test_indicators_signals_pure_no_io_imports` | PASS |
| mypy: `uv run mypy src/screener/signals/minervini.py` | PASS (Success: no issues) |
| ruff: changed files | PASS (All checks passed) |
| 102 total tests, 0 failures, 2 skipped | PASS |

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED: `test(04-02)` commit with failing tests | `c3bea66` | PASS |
| GREEN: `feat(04-02)` commit with implementation | `7ee4b1a` | PASS |
| REFACTOR: no refactoring needed | — | N/A |

## Stub Tracking

No stubs. All implemented functions are fully functional:
- `passes_trend_template` computes real conditions on real panel data
- All 8 conditions are the verbatim CLAUDE.md formulas
- Score is a real sum, not a placeholder

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns. `signals/minervini.py` is a pure function (no I/O, no network). Threat model mitigations applied:
- **T-4-06 (Tampering):** NaN-safe coercion (`.fillna(False).astype(bool)`) ensures malformed rows fail the gate (score 0) without corrupting other rows. Pure-function semantics make failure local.
- **T-4-07 (Info Disclosure):** No structured log output; pandera validation is upstream at the read boundary.

## Self-Check: PASSED

Verified files exist:
- `src/screener/signals/minervini.py` contains `def passes_trend_template` ✓
- `src/screener/signals/minervini.py` contains `trend_template_score` ✓
- `src/screener/signals/minervini.py` contains `passes_trend_template` (twice: function def + column assignment) ✓
- `src/screener/signals/minervini.py` contains `groupby(level="ticker").shift(22)` ✓
- `src/screener/signals/minervini.py` contains `fillna(False)` ✓
- `tests/test_signals_minervini.py` contains all 5 required test functions ✓

Verified commits exist:
- `c3bea66` — test(04-02): add failing SIG-01 Trend Template tests (RED) ✓
- `7ee4b1a` — feat(04-02): implement passes_trend_template (GREEN) ✓
