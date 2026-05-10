---
phase: "04"
plan: "01"
subsystem: indicators, persistence, config, tests
tags: [indicators, trend, high_52w, low_52w, persistence, schema, settings, fixtures, wave-0]
dependency_graph:
  requires: [03-03, 03-04]
  provides: [high_52w, low_52w columns in build_panel, RankingSnapshotSchema, write_snapshot_atomic, Phase 4 Settings fields, conftest fixtures]
  affects: [04-02-minervini, 04-03-composite, 04-04-publishers]
tech_stack:
  added: []
  patterns: [groupby.rolling.droplevel per-ticker rolling, pandera DataFrameModel schema extension, pydantic-settings additive block, lazy fixture imports]
key_files:
  created:
    - data/snapshots/.gitkeep
  modified:
    - src/screener/indicators/trend.py
    - src/screener/indicators/__init__.py
    - src/screener/persistence.py
    - src/screener/config.py
    - .gitignore
    - tests/conftest.py
    - tests/test_indicators_panel.py
    - tests/test_persistence.py
decisions:
  - "high_52w/low_52w use groupby(level='ticker').rolling(252).max/min().droplevel(0) — mirrors dryup_ratio_panel idiom for per-ticker correctness (no MultiIndex bleed)"
  - "TREND_TEMPLATE_PASS_RATE_WARN == TREND_TEMPLATE_PASS_RATE_HARD_FAIL == 0.25 intentionally — both fire at >0.25 per D-07/D-08; two fields allow paper-trade tuning"
  - "RankingSnapshotSchema uses strict=True, coerce=False; isin enforcement on pivot_zone and regime_state for tamper-evidence"
  - "Phase 4 conftest fixtures use lazy imports inside body (not at module level) so collection does not fail before signals modules land in 04-02/04-03"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-05-10"
  tasks_completed: 4
  files_changed: 8
---

# Phase 04 Plan 01: Foundation — high_52w/low_52w, Settings, RankingSnapshotSchema, Conftest Fixtures Summary

**One-liner:** Wave 0 foundation: high_52w/low_52w pure functions wired into build_panel, 5 Phase 4 Settings fields, RankingSnapshotSchema + write_snapshot_atomic with path-traversal defense, and 3 conftest fixtures enabling Wave 2 and Wave 3 plans.

## What Was Built

### Task 1: high_52w / low_52w panel functions

Added two pure functions to `src/screener/indicators/trend.py`:
- `high_52w_panel(panel, length=252)`: per-ticker rolling max of `high` over 252 bars using `groupby(level="ticker")["high"].rolling(252).max().droplevel(0)` — prevents MultiIndex bleed across tickers
- `low_52w_panel(panel, length=252)`: per-ticker rolling min of `low` over 252 bars, same pattern

Updated `src/screener/indicators/__init__.py`:
- Import: `from screener.indicators.trend import high_52w_panel, low_52w_panel, sma_panel`
- `build_panel` chain: two new lines after `rs_panel(panel)` call
- Docstring updated: 11 indicator columns → 13 (`high_52w, low_52w` appended)

Updated `tests/test_indicators_panel.py`:
- `REQUIRED_NEW_COLS` set extended with `"high_52w"` and `"low_52w"`
- Added `test_build_panel_high_52w_low_52w_per_ticker_rolling`: asserts per-ticker rolling correctness (high_52w at tail == max(high[-252:])) for all 5 synthetic tickers, and independence from other tickers

IND-02 grep gate: `grep -ilE "ema" src/screener/indicators/trend.py` returns no matches.

### Task 2: Settings Phase 4 fields + gitignore + .gitkeep

Added to `src/screener/config.py` (after `REGIME_VIX_CONFIRMED`):
```python
SNAPSHOT_DIR: Path = Path("data/snapshots")
REPORT_DIR: Path = Path("reports")
REPORT_TOP_N: int = 15
TREND_TEMPLATE_PASS_RATE_WARN: float = 0.25
TREND_TEMPLATE_PASS_RATE_HARD_FAIL: float = 0.25
```

Updated `.gitignore`:
- `!/data/snapshots/` — allow directory
- `data/snapshots/*.parquet` — ignore Parquet files (not committed locally)
- `!/data/snapshots/.gitkeep` — preserve anchor

Created `data/snapshots/.gitkeep` (empty anchor file).

### Task 3: Persistence additions

Added to `src/screener/persistence.py`:
- `import re` (stdlib, required for _assert_safe_snapshot_date regex)
- `RankingSnapshotSchema`: 16-column pandera DataFrameModel with `strict=True, coerce=False`; `isin` enforcement on `pivot_zone` (in-zone/chase, skip/unknown) and `regime_state` (Confirmed Uptrend/Uptrend Under Pressure/Correction); numeric range bounds on all score components
- `_snapshot_dir()`: resolves SNAPSHOT_DIR from Settings with fallback to `"data/snapshots"`
- `_assert_safe_snapshot_date(snapshot_date)`: T-4-01 path-traversal defense via `re.match(r"^\d{4}-\d{2}-\d{2}$", ...)` — raises `ValueError("Unsafe snapshot_date...")` on non-YYYY-MM-DD input
- `write_snapshot_atomic(df, snapshot_date)`: validates + atomically writes to `data/snapshots/<date>.parquet` with same D-11 contract as `write_rs_snapshot_atomic`

Added to `tests/test_persistence.py`:
- `_make_ranking_snapshot_df()` helper with all 16 columns
- `test_ranking_snapshot_schema_accepts_valid_frame`: validates a well-formed frame (2 rows)
- `test_ranking_snapshot_rejects_bad_pivot_zone`: asserts SchemaError on `pivot_zone="BOGUS"`
- `test_assert_safe_snapshot_date_rejects_traversal`: tests silent pass, path traversal, and non-zero-padded rejection

### Task 4: Phase 4 conftest fixtures

Added to `tests/conftest.py` (after Phase 3 block):
- `synthetic_panel_for_trend_template` (session-scope): runs full build_panel indicator chain (sma + atr + adr + obv + dryup + rs + high_52w + low_52w) on `synthetic_multi_ticker_panel`; 260-bar tickers satisfy 252-bar warmup for high_52w/low_52w
- `synthetic_scored_panel` (session-scope): lazy-imports `signals.minervini` and `signals.composite` (Plans 04-02/04-03); returns single-date cross-section with composite_score, pivot_zone, regime_state, regime_score — matches shape for publisher tests
- `synthetic_high_pass_rate_panel` (function-scope): lazy-imports `signals.minervini.passes_trend_template`; function-scope allows mutation in D-08 gate tests

All lazy imports inside fixture bodies prevent collection-time failures.

## Test Coverage

| Test | Status |
|------|--------|
| test_build_panel_returns_10_new_cols (now 13 cols) | PASS |
| test_build_panel_high_52w_low_52w_per_ticker_rolling (NEW) | PASS |
| test_ranking_snapshot_schema_accepts_valid_frame (NEW) | PASS |
| test_ranking_snapshot_rejects_bad_pivot_zone (NEW) | PASS |
| test_assert_safe_snapshot_date_rejects_traversal (NEW) | PASS |
| All 72 pre-existing Phase 3 tests | PASS (zero regressions) |
| test_ci_ema_grep_gate (IND-02) | PASS |
| test_layer_import_contract (D-16) | PASS |

Total at completion: 99 tests collected, all passing (coverage gate met on full suite run).

## Deviations from Plan

### Pre-existing Issue (Out of Scope)

**Pre-existing mypy error in `_rs_rating_dtype` classmethod (line 213 in original persistence.py):**
- Issue: `Returning Any from function declared to return "bool"  [no-any-return]`
- This error existed BEFORE Plan 04-01 (verified by running mypy on the original file)
- Not caused by any changes in this plan
- Not fixed: out of scope per deviation rules (pre-existing, unrelated file area)
- Logged to `deferred-items.md` for tracking

None - all plan actions executed exactly as specified. The conftest fixtures use `# noqa: PLC0415` comments in the plan template, which ruff auto-removed (ruff doesn't recognize `PLC0415` as an applicable suppression — the imports are inside functions, not at module level, so ruff doesn't flag them).

## Stub Tracking

No stubs found. All implemented functions are fully functional:
- `high_52w_panel` and `low_52w_panel` compute real rolling windows
- `RankingSnapshotSchema` enforces real column constraints
- `write_snapshot_atomic` performs real atomic writes
- Conftest fixtures that depend on Plan 04-02/04-03 signals use lazy imports (correctly deferred, not stubbed)

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond:
- `data/snapshots/<date>.parquet` write path — mitigated by `_assert_safe_snapshot_date` (T-4-01) and `RankingSnapshotSchema` (T-4-02), both in the plan's threat model

## CI Gate Status

| Gate | Result |
|------|--------|
| IND-02: `grep -ilE "ema" src/screener/indicators/trend.py` | PASS (0 matches) |
| D-16: `test_layer_import_contract` | PASS |
| Architecture: `test_indicators_signals_pure_no_io_imports` | PASS |
| mypy (indicators/, config.py) | PASS (clean) |
| ruff (changed files only) | PASS (clean) |
| 99 tests collected, 0 import errors at collection | PASS |

## Self-Check: PASSED

Verified files exist:
- `src/screener/indicators/trend.py` contains `def high_52w_panel` and `def low_52w_panel`
- `src/screener/indicators/__init__.py` contains `high_52w_panel` and `low_52w_panel`
- `src/screener/persistence.py` contains `class RankingSnapshotSchema`, `def write_snapshot_atomic`, `def _snapshot_dir`, `def _assert_safe_snapshot_date`
- `src/screener/config.py` contains `REPORT_TOP_N`
- `.gitignore` contains `data/snapshots/`
- `data/snapshots/.gitkeep` exists
- `tests/conftest.py` contains `def synthetic_panel_for_trend_template`, `def synthetic_scored_panel`, `def synthetic_high_pass_rate_panel`

Verified commits exist:
- `faac419` — Task 1: indicators/trend.py + __init__.py + test_indicators_panel.py
- `31c462a` — Task 2: config.py + .gitignore + data/snapshots/.gitkeep
- `dc768b5` — Task 3: persistence.py + test_persistence.py
- `349d097` — Task 4: tests/conftest.py
