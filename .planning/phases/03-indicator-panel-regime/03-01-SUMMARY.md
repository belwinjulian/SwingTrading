---
phase: 03-indicator-panel-regime
plan: "01"
subsystem: persistence
tags:
  - settings
  - schemas
  - persistence
  - pandera
  - atomic-write

dependency_graph:
  requires:
    - 01-01  # persistence.py atomic-write primitive
    - 02-02  # Settings additive extension pattern (D-20)
  provides:
    - MacroOhlcvSchema
    - VixSchema
    - YieldsSchema
    - NyadMacroSchema
    - RsSnapshotSchema
    - write_rs_snapshot_atomic
    - write_macro_atomic
    - read_rs_snapshot
    - read_macro_spy/qqq/vix/yields/nyad
    - _macro_dir
    - _rs_snapshot_dir
    - Settings D-12 fields (MACRO_CACHE_DIR, RS_SNAPSHOT_DIR, MACRO_BACKFILL_START, REGIME_*)
  affects:
    - 03-02  # macro data layer imports write_macro_atomic / read_macro_*
    - 03-03  # indicator panel imports RsSnapshotSchema / write_rs_snapshot_atomic
    - 03-04  # regime module reads macro via read_macro_spy/vix/nyad/yields
    - 03-05  # CI tests use these primitives

tech_stack:
  added: []
  patterns:
    - pandera DataFrameModel with custom @pa.check for exact dtype enforcement
    - getattr-with-default resolver helpers for cross-wave Settings race safety
    - Empty-frame fallback in read_macro_* (D-06 incremental refresh pattern)

key_files:
  created:
    - tests/test_rs_snapshot.py
  modified:
    - src/screener/config.py
    - src/screener/persistence.py
    - .env.example
    - tests/conftest.py
    - tests/test_persistence.py

decisions:
  - "Added custom @pa.check to RsSnapshotSchema to enforce pd.Int64Dtype vs int64 (Pitfall 9) — pandera 0.31.1 coerce=False does not distinguish these types at the annotation level alone"
  - "read_macro_* functions return schema-shaped empty DataFrames (not raise FileNotFoundError) to support D-06 incremental refresh pattern without path.exists() guards at call sites"
  - "test_read_macro_spy_validates catches both SchemaError and SchemaErrors because validate_at_read uses lazy=True which raises SchemaErrors (plural), not SchemaError (singular)"

metrics:
  duration: "~12 minutes"
  completed_date: "2026-05-10"
  tasks_completed: 3
  files_changed: 6
  tests_added: 9
  total_tests: 48
---

# Phase 3 Plan 01: Settings and Schemas Summary

## One-Liner

5 pandera schemas (MacroOhlcv, Vix, Yields, Nyad, RsSnapshot) + 8 persistence helpers (atomic writers + empty-frame readers) + 8 typed Settings fields (D-12), all with full atomic-write crash safety verified by 9 new tests.

## What Was Built

### Settings Extensions (src/screener/config.py)

Added 8 new typed fields under `# Phase 3 (D-12)` comment block:

| Field | Type | Default |
|-------|------|---------|
| `MACRO_CACHE_DIR` | `Path` | `Path("data/macro")` |
| `RS_SNAPSHOT_DIR` | `Path` | `Path("data/rs_snapshots")` |
| `MACRO_BACKFILL_START` | `str` | `"2005-01-01"` |
| `REGIME_BREADTH_THRESHOLD` | `float` | `0.60` |
| `REGIME_DIST_DAYS_PRESSURE` | `int` | `5` |
| `REGIME_DIST_DAYS_CORRECTION` | `int` | `9` |
| `REGIME_VIX_CORRECTION` | `float` | `30.0` |
| `REGIME_VIX_CONFIRMED` | `float` | `20.0` |

All 8 keys mirrored in `.env.example` under `# Phase 3 — macro + RS snapshot paths and regime thresholds (D-12)`.

### Persistence Schema Additions (src/screener/persistence.py)

5 new `pa.DataFrameModel` schemas, all `strict=True, coerce=False`:

- **`MacroOhlcvSchema`** — single-index (date) macro OHLCV for SPY/QQQ (lowercase columns, volume as `Series[int]`)
- **`VixSchema`** — close-only (`^VIX` has Volume=0 always per RESEARCH Pitfall 4)
- **`YieldsSchema`** — DGS2/DGS10/T10Y2Y all `nullable=True` (FRED weekend gaps per Pitfall 5)
- **`NyadMacroSchema`** — advances/declines (ge=0), ad_line (cumulative, can be negative)
- **`RsSnapshotSchema`** — ticker with regex `^[A-Z][A-Z0-9\-]{0,9}$`, rs_rating as `Series[pd.Int64Dtype]` with custom `@pa.check` enforcing exact dtype (Pitfall 9)

2 new resolver helpers:
- `_macro_dir()` — `getattr(s, "MACRO_CACHE_DIR", "data/macro")` pattern
- `_rs_snapshot_dir()` — same pattern for `RS_SNAPSHOT_DIR`

4 public writers:
- `write_rs_snapshot_atomic(df, snapshot_date)` → routes through `_write_parquet_atomic`
- `_MACRO_SCHEMAS` dispatch dict + `write_macro_atomic(df, series_name)` → validates schema by name, routes through `_write_parquet_atomic`

7 public readers (1 RS + 5 macro + the existing `read_universe`):
- `read_rs_snapshot(snapshot_date)` — lazy validation
- `read_macro_spy()`, `read_macro_qqq()`, `read_macro_vix()`, `read_macro_yields()`, `read_macro_nyad()` — all return **empty schema-shaped DataFrames** when the cache file does not exist (D-06 incremental-refresh pattern)

### Test Coverage (tests/test_rs_snapshot.py, tests/test_persistence.py)

9 new tests:

| Test | What It Verifies |
|------|-----------------|
| `test_rs_snapshot_atomic_write` | Mid-write crash leaves no partial Parquet and no .tmp residue |
| `test_rs_snapshot_round_trip` | Write + read recovers exact frame with `rs_rating.dtype == Int64` |
| `test_rs_snapshot_schema_rejects_bad_rating` | `int64` (not `Int64`) rejected at write boundary (Pitfall 9 custom check) |
| `test_rs_snapshot_schema_rejects_lowercase_ticker` | Lowercase ticker rejects via regex |
| `test_write_macro_atomic_unknown_series_raises` | Typo guard — `ValueError` with "unknown macro series" |
| `test_read_macro_spy_validates` | Missing `volume` column fails lazy validation (SchemaErrors) |
| `test_macro_dir_resolves_from_settings` | `_macro_dir()` returns `Path("data/macro")` |
| `test_rs_snapshot_dir_resolves_from_settings` | `_rs_snapshot_dir()` returns `Path("data/rs_snapshots")` |
| `test_write_parquet_atomic_auto_creates_new_dirs` | `mkdir(parents=True)` handles deep nested dirs (Pitfall 10) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RsSnapshotSchema did not enforce Int64 vs int64 dtype distinction**
- **Found during:** Task 3 (when test_rs_snapshot_schema_rejects_bad_rating failed)
- **Issue:** `pandera 0.31.1` with `coerce=False` does not distinguish `int64` from `pd.Int64Dtype` at the type-annotation level — a DataFrame with `rs_rating: int64` passed `validate_at_write(RsSnapshotSchema, df)` without raising
- **Fix:** Added `@pa.check("rs_rating", name="rs_rating_must_be_nullable_int64")` custom classmethod to `RsSnapshotSchema` that explicitly checks `series.dtype == pd.Int64Dtype()`
- **Files modified:** `src/screener/persistence.py`
- **Commit:** 87aaa3e (test commit), 754d68f (mypy cleanup)

**2. [Rule 1 - Bug] test_read_macro_spy_validates used wrong exception class**
- **Found during:** Task 3 (test failure)
- **Issue:** `validate_at_read` uses `lazy=True` which raises `pandera.errors.SchemaErrors` (plural, different class from `SchemaError`). The plan's test template used `pytest.raises(pandera.errors.SchemaError)` (singular)
- **Fix:** Changed to `pytest.raises((pandera.errors.SchemaError, pandera.errors.SchemaErrors))` to catch both variants
- **Files modified:** `tests/test_rs_snapshot.py`
- **Commit:** 87aaa3e

## Known Stubs

None — all reader/writer functions are fully implemented with real schema validation. No placeholder values, no hardcoded mock data flowing to downstream consumers.

## Threat Flags

No new security-relevant surface introduced beyond what the plan's `<threat_model>` covers:
- T-3-01 (Tampering at read boundary): mitigated via `validate_at_read` on all `read_macro_*` and `read_rs_snapshot` functions
- T-3-04 (Tampering at write boundary): mitigated via `_write_parquet_atomic` in `write_rs_snapshot_atomic` and `write_macro_atomic`

## Self-Check: PASSED

All committed files verified:

| Item | Status |
|------|--------|
| `src/screener/config.py` | FOUND |
| `src/screener/persistence.py` | FOUND |
| `.env.example` | FOUND |
| `tests/test_rs_snapshot.py` | FOUND |
| `tests/test_persistence.py` | FOUND |
| `tests/conftest.py` | FOUND |
| `d9716c9` (Task 1 commit) | FOUND |
| `675afdd` (Task 2 commit) | FOUND |
| `87aaa3e` (Task 3 commit) | FOUND |
| `754d68f` (mypy fix commit) | FOUND |
