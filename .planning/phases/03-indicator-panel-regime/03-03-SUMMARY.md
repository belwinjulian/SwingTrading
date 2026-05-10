---
phase: 03-indicator-panel-regime
plan: "03"
subsystem: indicators
tags:
  - indicators
  - pure-functions
  - panel
  - tdd

dependency_graph:
  requires:
    - 03-01  # persistence.read_panel, write_ohlcv_atomic, write_universe_atomic, OhlcvPanelSchema
  provides:
    - indicators.build_panel(snapshot_date) — OHLCV panel + 10 indicator columns
    - indicators/trend.py — _safe_sma, sma_panel (SMA 10/20/50/150/200)
    - indicators/volatility.py — _safe_atr, atr_panel (ATR-14), adr_pct_panel (ADR%-20)
    - indicators/volume.py — _safe_obv, obv_panel, dryup_ratio_panel (D-09)
    - indicators/relative_strength.py — rs_panel (IBD RS raw + rating)
    - conftest fixtures: synthetic_short_history_panel, synthetic_multi_ticker_panel
  affects:
    - 03-04 (regime breadth_pct consumes the panel surface)
    - 03-05 (Minervini signal layer consumes sma_*, atr_14, rs_rating)
    - Future phases 4-6 (Trend Template, VCP, Qullamaggie all depend on this panel)

tech_stack:
  added: []
  patterns:
    - _safe_* wrapper: guards against pandas-ta-classic returning None on short input (< lookback length)
    - explicit concat loop: for ATR/OBV groupby.apply returns wide DataFrame; use for-loop + pd.concat(parts)
    - per-ticker groupby: groupby(level='ticker') prevents rolling bleed across tickers in MultiIndex
    - cross-sectional rank: groupby(level='date').rank(pct=True) for universe-relative RS percentile
    - nullable Int64: rs_rating stored as pd.Int64Dtype so NaN is preserved for short-history tickers

key_files:
  created:
    - src/screener/indicators/trend.py
    - src/screener/indicators/volatility.py
    - src/screener/indicators/volume.py
    - src/screener/indicators/relative_strength.py
    - tests/test_indicators_trend.py
    - tests/test_indicators_volatility.py
    - tests/test_indicators_volume.py
    - tests/test_indicators_rs.py
    - tests/test_indicators_panel.py
    - tests/test_indicators_purity.py
  modified:
    - src/screener/indicators/__init__.py
    - tests/conftest.py
    - pyproject.toml

decisions:
  - "Used explicit for-ticker concat loops in atr_panel and obv_panel instead of groupby.apply — groupby.apply on a DataFrame group returning a Series produces a wide (ticker x date) matrix not a long Series, causing ValueError on column assignment."
  - "Added pandas_ta_classic and pandas_ta_classic.* to mypy ignore_missing_imports in pyproject.toml — without this, mypy strict mode emitted no-any-return errors on every ta.sma/atr/obv call."
  - "test_indicators_panel.py uses a _make_universe_df() helper that provides all UniverseSchema columns (ticker, ticker_raw, name, sector, weight_pct) — the plan template only provided ticker/name/sector, which would fail write_universe_atomic's pandera validation."
  - "IND-02 grep gate: trend.py docstring rewrote 'do not introduce the substring ema' to 'do not add exponentially-weighted variants' to avoid the gate tripping on its own description."

metrics:
  duration: "~180 minutes (across two sessions)"
  completed: "2026-05-10T18:44:52Z"
  tasks_completed: 2
  files_created: 10
  files_modified: 3
  commits: 4
  test_coverage: "98% (95 stmts, 2 missed)"
---

# Phase 03 Plan 03: Indicator Panel Summary

Pure-function indicator panel delivering `build_panel(snapshot_date)` — OHLCV panel + 11 columns covering all 10 IND-01 indicator categories via 4 new modules and a wired orchestrator.

## What Was Built

### Modules Created

**`src/screener/indicators/trend.py`**
- `_safe_sma(close, length)` — wraps `ta.sma`, returns NaN-filled Series on short input (Pitfall 2 defense)
- `sma_panel(panel, lengths=(10,20,50,150,200))` — adds 5 sma_* columns via per-ticker groupby.apply
- Zero `ema` references anywhere (IND-02 CI gate prep for Plan 03-05)

**`src/screener/indicators/volatility.py`**
- `_safe_atr(h, low, c, length)` — wraps `ta.atr` (Wilder's smoothing, mamode="rma"), NaN on short input
- `atr_panel(panel, length=14)` — adds `atr_14` column using explicit concat loop (not groupby.apply — see Deviations)
- `adr_pct_panel(panel, length=20)` — adds `adr_pct` column; formula: `100 * ((high/low).rolling(20).mean() - 1)`; verified: high=105/low=95 → 10.526%

**`src/screener/indicators/volume.py`**
- `_safe_obv(close, volume)` — wraps `ta.obv`, NaN on short input
- `obv_panel(panel)` — adds `obv` column using explicit concat loop
- `dryup_ratio_panel(panel, length=50)` — adds `dryup_ratio = volume / SMA(volume, 50)` per D-09; constant volume → ratio = 1.0

**`src/screener/indicators/relative_strength.py`**
- `rs_panel(panel)` — adds `rs_raw` (float) and `rs_rating` (Int64Dtype)
- Formula: `rs_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`
- Per-ticker shifts via `groupby(level="ticker").shift()` (Pitfall 8 — no naked .shift())
- Cross-sectional percentile: `groupby(level="date").rank(pct=True) * 99`
- NaN for tickers with < 252 trading days of history
- `rs_rating.dtype == pd.Int64Dtype()` (Pitfall 9 — nullable integer)

**`src/screener/indicators/__init__.py`** (modified)
- Exports `build_panel(snapshot_date)` — chains persistence.read_panel → sma_panel → atr_panel → adr_pct_panel → obv_panel → dryup_ratio_panel → rs_panel
- Adds 11 columns total: sma_10/20/50/150/200, atr_14, adr_pct, obv, dryup_ratio, rs_raw, rs_rating

### Test Files Created

| File | Tests | What It Covers |
|------|-------|----------------|
| tests/test_indicators_trend.py | 2 | _safe_sma NaN return, sma_panel 5 columns |
| tests/test_indicators_volatility.py | 2 | ADR% canonical 10.526%, atr_14 column |
| tests/test_indicators_volume.py | 2 | obv column, dryup_ratio=1.0 for constant volume |
| tests/test_indicators_rs.py | 3 | RS range [1,99] + Int64Dtype, NaN on short, per-ticker shift isolation |
| tests/test_indicators_panel.py | 3 | build_panel 10 new cols, MultiIndex preserved, 50-bar NaN warmup |
| tests/test_indicators_purity.py | 2 | no input mutation, idempotent output |

### Conftest Fixtures Added

- `synthetic_short_history_panel`: 50-bar single-ticker panel (ticker=SHORT) — exercises SMA150/200 NaN warmup (D-08)
- `synthetic_multi_ticker_panel`: 5 tickers (AAA-EEE) x 260 business days — RS rating defined for all; distinct drift rates produce distinguishable RS values

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] groupby.apply returns wide DataFrame for ATR and OBV**
- **Found during:** Task 1, GREEN phase
- **Issue:** Plan template used `groupby(level="ticker").apply(_per_ticker)` where `_per_ticker` receives a DataFrame group and returns a Series. Pandas returns a 2D wide (ticker x date) DataFrame, causing `ValueError: Cannot set a DataFrame with multiple columns to the single column atr_14`.
- **Fix:** Replaced with explicit `for _ticker, g in panel.groupby(level="ticker")` loop + `pd.concat(parts)` for both `atr_panel` and `obv_panel`.
- **Files modified:** `src/screener/indicators/volatility.py`, `src/screener/indicators/volume.py`
- **Commit:** 297424d

**2. [Rule 1 - Bug] IND-02 gate tripped by its own description**
- **Found during:** Task 1, verification
- **Issue:** The plan's docstring template for trend.py included "do not introduce the substring 'ema'" which itself contained `ema` (case-insensitive). `grep -ic "ema" trend.py` returned 1, failing the gate.
- **Fix:** Rewrote docstring to "all moving averages must be simple (non-exponential) rolling means; do not add exponentially-weighted variants here."
- **Files modified:** `src/screener/indicators/trend.py`
- **Commit:** 297424d

**3. [Rule 2 - Missing Critical] mypy strict required pandas_ta_classic in ignore_missing_imports**
- **Found during:** Task 1, mypy verification
- **Issue:** `pandas_ta_classic` not listed in pyproject.toml `ignore_missing_imports` caused `no-any-return` mypy errors on all `ta.sma/atr/obv` calls.
- **Fix:** Added `"pandas_ta_classic"` and `"pandas_ta_classic.*"` to the mypy overrides in pyproject.toml.
- **Files modified:** `pyproject.toml`
- **Commit:** 297424d

**4. [Rule 1 - Bug] write_universe_atomic requires full UniverseSchema columns**
- **Found during:** Task 2, implementation
- **Issue:** Plan template provided `pd.DataFrame({"ticker": ..., "name": ..., "sector": ...})` to `write_universe_atomic`, but `UniverseSchema` requires `ticker`, `ticker_raw`, `name`, `sector`, `weight_pct`. The write would fail pandera validation.
- **Fix:** Added `_make_universe_df(tickers)` helper in `test_indicators_panel.py` that provides all required columns.
- **Files modified:** `tests/test_indicators_panel.py`
- **Commit:** 7b84ea4

## TDD Gate Compliance

Task 1:
- RED: `720dc5c` — failing tests for 4 indicator modules (ImportError — modules not yet created)
- GREEN: `297424d` — 4 indicator modules created; 12 tests pass

Task 2:
- RED: `5ed6abf` — failing tests for build_panel (ImportError — not yet in __init__.py)
- GREEN: `7b84ea4` — build_panel wired; all 17 indicator + architecture tests pass

## Test Results

```
17 passed, 0 failed — indicator + architecture tests
62 passed, 2 skipped, 0 failed — full suite (not slow, not integration)
98% coverage on indicators/ (95 stmts, 2 missed in uncovered branches)
```

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries were introduced. The `build_panel` function is a pure DataFrame transform chain — it calls `persistence.read_panel` which already exists and is covered by the 03-01 threat model. No new threat flags.

## Known Stubs

None — all indicator computations are fully implemented with real pandas/pandas-ta-classic math. No placeholder returns or TODO paths.

## Self-Check: PASSED

Files exist:
- src/screener/indicators/trend.py: FOUND
- src/screener/indicators/volatility.py: FOUND
- src/screener/indicators/volume.py: FOUND
- src/screener/indicators/relative_strength.py: FOUND
- src/screener/indicators/__init__.py: FOUND (build_panel)
- tests/test_indicators_panel.py: FOUND
- tests/test_indicators_purity.py: FOUND

Commits exist:
- 720dc5c: FOUND (test RED task 1)
- 297424d: FOUND (feat GREEN task 1)
- 5ed6abf: FOUND (test RED task 2)
- 7b84ea4: FOUND (feat GREEN task 2)
