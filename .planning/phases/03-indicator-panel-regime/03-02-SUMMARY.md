---
phase: 03-indicator-panel-regime
plan: "02"
subsystem: macro-data-layer
tags:
  - data
  - macro
  - cli
  - tdd

dependency_graph:
  requires:
    - 03-01  # persistence write_macro_atomic, MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, Settings
    - 02-03  # ohlcv retry/invariant idiom (D-10 pattern)
  provides:
    - macro_data_layer  # refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields
    - refresh_macro_cli  # real CLI body for screener refresh-macro
    - make_macro_target  # Makefile macro: target
  affects:
    - 03-04  # regime module will consume macro parquets (spy.parquet, vix.parquet, nyad.parquet, yields.parquet)

tech_stack:
  added:
    - fredapi==0.5.2  # FRED DGS2/DGS10/T10Y2Y yields (already in pyproject, now used)
  patterns:
    - tenacity retry with 4-invariant gate (mirrors ohlcv.py D-10 pattern)
    - incremental-append via _incremental_start + _append_new_bars (D-06)
    - Stooq primary + R1000 breadth fallback (D-05)
    - T-3-02 safe error logging (error_type only, never str(e))
    - from X import Y binding awareness in monkeypatch (screener.data.macro.get_settings)

key_files:
  created:
    - src/screener/data/macro.py
    - tests/test_macro_refresh.py
  modified:
    - src/screener/data/__init__.py
    - src/screener/cli.py
    - Makefile
    - tests/test_cli_smoke.py

decisions:
  - "Use pd.Timestamp.now().normalize() (tz-naive) in _incremental_start to avoid TypeError comparing with existing.index.max() which is also tz-naive (discovered during D-06 incremental-append test)"
  - "Patch screener.data.macro.get_settings in tests — not screener.config.get_settings — because macro.py uses 'from screener.config import get_settings' creating a local binding unaffected by patching the config module"
  - "Merge main (03-01 Wave 1) into worktree before implementing; worktree branched from pre-03-01 commit and lacked write_macro_atomic, MacroOhlcvSchema, and Settings fields required by macro.py"

metrics:
  duration: "14m"
  completed_date: "2026-05-10"
  tasks_completed: 2
  files_changed: 6
---

# Phase 03 Plan 02: Macro Data Layer Summary

**One-liner:** Five-series macro refresh (SPY/QQQ yfinance OHLCV, VIX close-only, NYAD Stooq+R1000 breadth fallback, FRED DGS2/DGS10/T10Y2Y) wired into `screener refresh-macro` CLI and `make macro` Makefile target with tenacity retry, incremental-append (D-06), and T-3-02 FRED key safety.

## Tasks Completed

| Task | Type | Name | Commits | Files |
|------|------|------|---------|-------|
| 1 (RED) | test | Failing macro test suite (10 tests) | `dfd5daa` | tests/test_macro_refresh.py |
| 1 (merge) | chore | Merge 03-01 Wave 1 artifacts | `6232959` | persistence.py, config.py, data/__init__.py |
| 1 (GREEN) | feat | macro.py implementation | `df13921` | src/screener/data/macro.py, src/screener/data/__init__.py |
| 2 | feat | CLI + Makefile + test cleanup | `ecbce12` | src/screener/cli.py, Makefile, tests/test_cli_smoke.py, tests/test_macro_refresh.py |

## What Was Built

### src/screener/data/macro.py (new)

Five public refresh functions orchestrate the macro data pipeline:

- `refresh_spy` / `refresh_qqq` — yfinance OHLCV, tenacity-wrapped `_fetch_yf_macro`, incremental-append via `_incremental_start`
- `refresh_vix` — same as SPY/QQQ but projected to `[["close"]]` only before write (RESEARCH Pitfall 4: VIX volume is always 0)
- `refresh_nyad` — Stooq `$NYAD` primary with structured fallback to `_compute_breadth_fallback` on `StaleOrEmptyError`, `ParserError`, or > 5% NaN close (D-05); emits `nyad_source` event with `source='stooq'` or `source='r1000_proxy'`
- `refresh_yields` — FRED DGS2/DGS10 via fredapi, T10Y2Y computed as spread; graceful skip if `FRED_API_KEY` is empty with `skipping_yields_no_key` warning; stores NaN gaps as-received (RESEARCH Pitfall 5)

Three private helpers: `_fetch_yf_macro` (tenacity + 4-invariant gate), `_incremental_start` (max(date)+1d logic), `_append_new_bars` (concat + dedupe + sort)

T-3-02 mitigation applied throughout: every `except` block logs only `error_type=type(e).__name__`, never `error=str(e)`, to prevent FRED URL `?api_key=...` from appearing in logs.

### src/screener/cli.py (modified)

Replaced the `refresh-macro` stub (4 lines) with a real body:
- Lazy import of the 5 refresh functions inside the `try` block
- `--force` flag wired through
- Exception handler logs only `error_type` (T-3-02) then re-raises via `typer.Exit(code=1)`

### Makefile (modified)

Added `macro` to `.PHONY` and added the `macro:` target:
```makefile
macro:  ## Refresh macro inputs only (SPY, QQQ, ^VIX, NYSE A/D, FRED yields)
	uv run screener refresh-macro
```

### tests/test_macro_refresh.py (new — 10 tests)

| Test | Requirement |
|------|-------------|
| `test_yf_invariants_applied` | 4-invariant gate: lowercase + date index + close present |
| `test_yf_empty_raises_stale` | StaleOrEmptyError on empty yfinance response |
| `test_refresh_spy_writes_macro_parquet` | Round-trip write to tmp_path/macro/spy.parquet |
| `test_refresh_vix_drops_volume` | RESEARCH Pitfall 4: close-only projection |
| `test_nyad_fallback_to_r1000_proxy` | D-05: Stooq raises → r1000_proxy source event |
| `test_nyad_fallback_on_thin_stooq` | D-05: > 5% missing close → r1000_proxy fallback |
| `test_yields_parquet_columns` | Exactly {dgs2, dgs10, t10y2y} columns written |
| `test_yields_skipped_without_key` | Empty FRED_API_KEY → skipping_yields_no_key event |
| `test_no_secret_in_logs` | T-3-02: FRED key never in structlog or caplog |
| `test_refresh_spy_appends_only_new_bars` | D-06: incremental-append uses max(date)+1d as start |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing 03-01 Wave 1 artifacts**
- **Found during:** Task 1 implementation
- **Issue:** Worktree branched from `0e1bd26` (pre-03-01 commit). `persistence.py` lacked `write_macro_atomic`, `read_macro_spy`, MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema. Settings lacked FRED_API_KEY, MACRO_BACKFILL_START, MACRO_CACHE_DIR.
- **Fix:** `git merge main --no-commit --no-ff` auto-merged successfully; committed as chore(03-02)
- **Commit:** `6232959`

**2. [Rule 1 - Bug] tz-aware vs tz-naive timestamp comparison in _incremental_start**
- **Found during:** Task 1 GREEN (test_refresh_spy_appends_only_new_bars)
- **Issue:** `pd.Timestamp.utcnow().normalize()` returns tz-aware UTC timestamp; comparing with `existing.index.max()` (tz-naive) raises TypeError
- **Fix:** Changed to `pd.Timestamp.now().normalize()` (tz-naive, matches stored Parquet index)
- **Files modified:** `src/screener/data/macro.py`
- **Commit:** `ecbce12` (included in Task 2 commit)

**3. [Rule 2 - Critical] `from X import Y` local binding issue in test patches**
- **Found during:** Task 1 test iteration
- **Issue:** `monkeypatch.setattr("screener.config.get_settings", ...)` does not affect `macro.py`'s local `get_settings` binding set at import time via `from screener.config import get_settings`. Tests for `test_yields_parquet_columns` and `test_no_secret_in_logs` were patching the wrong reference.
- **Fix:** Changed all test patches to target `screener.data.macro.get_settings` directly
- **Files modified:** `tests/test_macro_refresh.py`

**4. [Rule 1 - Bug] Pre-existing ruff issues in test_cli_smoke.py**
- **Found during:** Task 2 ruff check
- **Issue:** `from unittest import mock` unused import (F401) and one long line (E501) were pre-existing in test_cli_smoke.py; surfaced when ruff checked the file as part of Task 2 delivery
- **Fix:** Removed unused import, split long assertion message across two f-strings, ran `ruff check --fix` for import ordering
- **Files modified:** `tests/test_cli_smoke.py`
- **Commit:** `ecbce12`

## Known Stubs

None. All five refresh functions are fully wired end-to-end. The `_compute_breadth_fallback` function derives real advance/decline data from the R1000 panel rather than returning placeholder values.

## Threat Flags

None identified beyond the T-3-02 threat already addressed in the plan. The FRED API key is handled with the dedicated `skipping_yields_no_key` path and the `error_type`-only logging pattern throughout.

## TDD Gate Compliance

- RED gate commit: `dfd5daa` — `test(03-02): add failing test suite for macro data layer`
- GREEN gate commit: `df13921` — `feat(03-02): implement src/screener/data/macro.py`
- REFACTOR: not needed; implementation was clean on first pass

## Self-Check: PASSED

Files created/modified exist:
- `src/screener/data/macro.py` — EXISTS
- `tests/test_macro_refresh.py` — EXISTS
- `src/screener/cli.py` — EXISTS (refresh-macro real body)
- `Makefile` — EXISTS (macro: target)
- `src/screener/data/__init__.py` — EXISTS
- `tests/test_cli_smoke.py` — EXISTS (refresh-macro removed from PHASE_1_STUBS)

Commits exist:
- `dfd5daa` — test RED
- `6232959` — merge chore
- `df13921` — feat GREEN
- `ecbce12` — feat Task 2

Test results: 19 tests passed (10 macro + 6 CLI smoke + 3 architecture)
