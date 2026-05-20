---
plan: 02-01
phase: 02-data-foundation
status: complete
wave: 1
completed: 2026-05-03
tags: [persistence, pandera, schemas, atomic-write, parquet, tests]
subsystem: persistence
dependency_graph:
  requires: [01-05]
  provides: [OhlcvPanelSchema, UniverseSchema, SplitsSchema, write_ohlcv_atomic, write_universe_atomic, write_splits_atomic, read_panel, read_splits, read_universe, StaleOrEmptyError, make_empty_splits]
  affects: [02-03, 02-04, 02-05, all-phases-read_panel]
tech_stack:
  added: [pandera.pandas DataFrameModel, tempfile+os.replace atomic pattern]
  patterns: [eager-validate-at-write, lazy-validate-at-read, same-filesystem-rename]
key_files:
  created: [tests/test_persistence.py]
  modified: [src/screener/persistence.py, tests/conftest.py, pyproject.toml]
decisions:
  - "pytest pythonpath=['src'] added to pyproject.toml — pre-existing issue where uv editable .pth file was not being processed by pytest; added pythonpath config (pytest 7+ supports this) to fix test discovery (Rule 3 auto-fix)"
  - "NamedTemporaryFile used as context manager (with block) to satisfy ruff SIM115; tmp_path captured before exiting context (Rule 1 auto-fix)"
metrics:
  duration: 6 minutes
  completed: "2026-05-03"
  tasks_completed: 3
  files_modified: 4
---

# Phase 02 Plan 01: Persistence Layer Summary

## One-liner

Three pandera DataFrameModel schemas + atomic tempfile-rename writer + GICS-sector allowlist, all tested with 9 green unit tests and 10 synthetic fixtures.

## Delivered

### Public API (src/screener/persistence.py)

- `StaleOrEmptyError` — shared exception for data/ohlcv.py and data/stooq.py
- `GICS_SECTORS` — frozenset of 11 verified GICS sector strings (iShares feed 2026-05-02)
- `OhlcvPanelSchema` — MultiIndex (ticker, date) OHLCV panel; strict=True, coerce=False
- `UniverseSchema` — one row per ticker with GICS sector isin validation
- `SplitsSchema` — sparse corporate-action ledger with DatetimeIndex 'date'
- `validate_at_write(schema_cls, df)` — eager (lazy=False), fail on first error
- `validate_at_read(schema_cls, df)` — lazy (lazy=True), collect all errors
- `_write_parquet_atomic(df, target)` — tempfile + os.replace D-11 contract
- `write_universe_atomic(df, snapshot_date)` — validates + writes universe Parquet
- `write_ohlcv_atomic(ticker, df)` — validates + writes per-ticker prices Parquet
- `write_splits_atomic(ticker, df)` — validates + writes per-ticker splits Parquet
- `make_empty_splits()` — zero-row splits DataFrame with correct float64 dtypes
- `read_universe(snapshot_date)` — reads + lazy-validates universe Parquet
- `read_splits(ticker)` — reads + lazy-validates splits Parquet
- `read_panel(snapshot_date)` — joins universe + OHLCV per-ticker into MultiIndex panel

### Contracts established

- Atomic-write (D-11): tempfile in target.parent + os.replace; crash leaves no partial target
- Validation policy (D-16): eager at write, lazy at read
- Path safety: `_assert_safe_ticker` refuses '/', '\\', '..' in ticker strings
- Architecture DAG: persistence imports only config/stdlib/third-party (no data/)

### Test fixtures added to tests/conftest.py (10 fixtures)

`synthetic_ohlcv_valid_df`, `synthetic_ohlcv_empty_df`, `synthetic_ohlcv_stale_df`,
`synthetic_ohlcv_null_close_df`, `synthetic_ohlcv_non_monotonic_df`,
`synthetic_ishares_csv_bytes`, `synthetic_ishares_csv_undersized_bytes`,
`synthetic_ishares_csv_bad_sector_bytes`, `synthetic_split_mismatch_pair`,
`synthetic_stooq_descending_df`

### Tests created (tests/test_persistence.py — 9 tests all green)

`test_panel_schema_rejects_null_close`, `test_panel_schema_rejects_negative_price`,
`test_panel_schema_rejects_wrong_index_order`, `test_universe_schema_rejects_unknown_sector`,
`test_splits_schema_rejects_negative`, `test_lazy_collects_multiple_errors`,
`test_atomic_write_crash_no_partial`, `test_empty_splits_schema_preserved`,
`test_read_panel_round_trip`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest pythonpath missing from pyproject.toml**
- **Found during:** Task 1 verification (`uv run pytest` returned `ModuleNotFoundError: No module named 'screener'`)
- **Issue:** pytest 7+ src-layout projects require `pythonpath = ["src"]` in `[tool.pytest.ini_options]`. The uv editable install `.pth` file (`_editable_impl_screener.pth`) was not being processed by pytest's import mode, so `screener` was not on sys.path.
- **Fix:** Added `pythonpath = ["src"]` to `[tool.pytest.ini_options]` in `pyproject.toml`
- **Files modified:** `pyproject.toml`
- **Commit:** 089bdb6 (inline with Task 1)

**2. [Rule 1 - Bug] ruff SIM115: NamedTemporaryFile not used as context manager**
- **Found during:** Task 1 ruff check after writing persistence.py
- **Issue:** `tempfile.NamedTemporaryFile(...)` without `with` statement triggers ruff SIM115 ("Use a context manager for opening files")
- **Fix:** Changed to `with tempfile.NamedTemporaryFile(...) as tmp:` and captured `tmp_path = Path(tmp.name)` before exiting the context block (file is closed but not deleted due to `delete=False`)
- **Files modified:** `src/screener/persistence.py`
- **Commit:** 089bdb6 (inline with Task 1)

## Downstream consumers

- Plans 02-03 and 02-04: import `write_*` and `make_empty_splits`
- Plan 02-05 and Phase 3+: import `read_panel`, `read_splits`, `read_universe`
- All data/ adapters: import `StaleOrEmptyError` for shared exception type

## Self-Check: PASSED

Files exist:
- src/screener/persistence.py: FOUND
- tests/test_persistence.py: FOUND
- tests/conftest.py: FOUND (updated)

Commits exist:
- 089bdb6 feat(02-01): implement persistence schemas, atomic-write, readers/writers
- 1afb0d9 feat(02-01): add 10 synthetic Phase 2 fixtures to conftest
- dff8268 feat(02-01): add 9 persistence tests (schemas, atomic-write, round-trip)

Test results: 14 passed (5 pre-existing + 9 new), 0 failures
