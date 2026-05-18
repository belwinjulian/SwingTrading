---
phase: 07-sizing-finalization-paper-trade-journal
plan: "04"
subsystem: publishers
tags: [phase-7, pipeline-wiring, report-rendering, sizing-injection, journal-append, skipped-picks-footer, integration-tests]
dependency_graph:
  requires: [07-02, 07-03]
  provides: [run_pipeline-with-journal, sizing-per-pick-report, skipped-picks-section, pipeline-journal-integration-tests]
  affects: [pipeline-daily-flow, report-rendering, snapshot-parquet, journal-sqlite]
tech_stack:
  added: []
  patterns:
    - "FULL-frame sizing: compute_sizing runs on all ~1000 rows; actionable-view derived AFTER snapshot write"
    - "composite_score_raw captured before apply_regime_gate (Warning #6 single-source-of-truth)"
    - "atr_zone sentinel 'not_applicable' for non-actionable rows (Blocker #2 followup)"
    - "ticker-from-column fix: _build_journal_rows_df uses row['ticker'] after _add_publisher_columns reset_index"
key_files:
  created: []
  modified:
    - src/screener/publishers/pipeline.py
    - src/screener/publishers/report.py
    - tests/test_pipeline_journal.py
    - tests/test_publishers_report.py
decisions:
  - "FULL-frame sizing contract: compute_sizing on ~1000 rows; actionable-view is a DERIVED VIEW never assigned back (Blocker #1 fix)"
  - "composite_score_raw column persisted to snapshot so cli.journal catch-up uses identical threshold semantics as live pipeline (Warning #6)"
  - "_build_journal_rows_df uses row['ticker'] column (not iter key) because _add_publisher_columns resets index to integer — Rule 1 bug fix"
  - "Monkeypatches target source modules for inline-imported Phase 6 symbols (passes_qullamaggie_setup_a, canslim_c_overlay, tag_playbook, compute_sizing) since they are not module-level attributes in pipeline.py"
metrics:
  duration_minutes: ~90
  completed_date: "2026-05-18"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
---

# Phase 7 Plan 04: Pipeline-Report Wiring Summary

Wave 2 integration that wires sizing.compute_sizing and persistence.append_picks_rows into the daily pipeline — FULL-frame sizing on ~1000 rows, actionable-view derivation AFTER snapshot write, journal append at step 8.5, sizing per-pick block and ## Skipped Picks in the report.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | Extend pipeline.py — sizing injection + actionable view + journal append + helpers | c51d5f5 |
| 2 | Extend report.py — sizing per-pick block + Skipped Picks section + new test | 689ce66 |
| 3 | Land 4 test_pipeline_journal.py bodies + fix ticker-from-column bug | c0d25d3 |

## What Was Built

### Task 1 — publishers/pipeline.py

- `run_pipeline` signature gains `write_journal: bool = True` parameter (CONTEXT D-01)
- `composite_score_raw` captured BEFORE `apply_regime_gate` — preserves pre-gate semantics for journal threshold (Pitfall 3 / Warning #6 single-source-of-truth)
- `compute_sizing` injected at step 5.5 on the FULL cross-section (~1000 rows); `today_panel` NEVER filtered before `write_snapshot` (Blocker #1)
- `atr_zone` sentinel patch: non-actionable rows receive `"not_applicable"` (Blocker #2 followup)
- `validate_run` + `pass_rate` run on FULL post-sizing frame (Blocker #3)
- `actionable_view` + `skipped_view` derived AFTER `write_snapshot` as DERIVED views (never assigned back to `today_panel`)
- Journal append at step 8.5: `_build_journal_rows_df` + `validate_at_write(PicksSchema, ...)` + `append_picks_rows`
- `write_report_md` gains `skipped_picks=skipped_view` kwarg pass-through
- New private helpers: `_build_journal_rows_df`, `_build_journal_rows_df_from_snapshot`, `_safe_int`, `_safe_float`, `_safe_decode_json`
- `features_json` contains: `features_json_version='v1.0'`, 13 score-component keys, 9 indicator values, 8 sizing-input keys, full `pattern_diagnostics` dict, `pivot_distance_atr_breakout` (Warning #5 rename)

### Task 2 — publishers/report.py

- `render_report` and `write_report` gain `skipped_picks: pd.DataFrame | None = None` kwarg (backwards-compatible, default None)
- `_render_per_pick_block` gains Phase 7 sizing block: `**Entry:** $...`, `**Stop:** $... (label)   **Trail:** ...`, `**Shares:** ...`, `**Zone:** ... (xATR above pivot)` — guarded on `pd.notna(row.get("stop_price"))`
- D-07 stop-source labels per playbook: `low-of-entry-day`, `final-contraction-low`, `max(1.5xATR, recent swing low)`
- `## Skipped Picks` section rendered after per-pick blocks and before `## Data Quality` when `skipped_picks` is non-empty (CONTEXT D-06 / SIZ-02 1xADR rejection surface)
- Fixed em dash regression: `# Daily Picks — {snapshot_date}` (was regular dash)
- Fixed RUF046: removed redundant `int()` around `round()` in `_format_breakdown`
- New test: `test_render_report_includes_sizing_fields_and_skipped_section` (all 8 report tests pass)

### Task 3 — tests/test_pipeline_journal.py

- All 4 pytest.skip skeletons replaced with real integration test bodies
- `_make_synthetic_multiindex_panel`: 4-ticker MultiIndex panel with all required schema columns including `rs_component` and `trend_component`
- `_install_pipeline_mocks`: NO try/except (Blocker #4); write_snapshot NOT mocked (Blocker #4); source-module patches for inline-imported Phase 6 symbols
- `_stub_sizing`: deterministic sizing stub that rejects only REJC (adr_pct=0.3)
- `test_pipeline_writes_journal`: asserts AAPL+NVDA in journal, REJC absent
- `test_journal_disabled`: asserts zero journal rows when `write_journal=False`
- `test_rejected_picks_not_in_journal`: asserts REJC absent from journal AND present in snapshot (Blocker #1 regression check)
- `test_golden_pipeline_journal`: snapshot row-count == 4 (Warning #10 regression lock), features_json key validation, `pivot_distance_atr_breakout` present (Warning #5)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ticker-from-column after _add_publisher_columns reset_index**
- **Found during:** Task 3 — test_pipeline_writes_journal pandera SchemaError `str_matches failure cases: 0, 1, 2`
- **Issue:** `_add_publisher_columns(today_panel, regime_row)` calls `reset_index()` at line 133 of report.py, converting the ticker-indexed DataFrame to an integer-indexed DataFrame with `ticker` as a column. When `_build_journal_rows_df` subsequently does `for ticker, row in actionable_view.iterrows()`, the iterator key is now an integer (0, 1, 2...) rather than a ticker string. `str(ticker)` produces `"0"`, `"1"`, `"2"` which fail PicksSchema's `str_matches('^[A-Z]...')` regex.
- **Fix:** `_build_journal_rows_df` now uses `row["ticker"]` when the "ticker" column exists in the row, falling back to `str(ticker)` for callers that pass a ticker-indexed view (e.g. `_build_journal_rows_df_from_snapshot`)
- **Files modified:** `src/screener/publishers/pipeline.py`
- **Commit:** c0d25d3

**2. [Rule 1 - Bug] Monkeypatch targets for inline-imported Phase 6 symbols**
- **Found during:** Task 3 — `AttributeError: module 'screener.publishers.pipeline' has no attribute 'passes_qullamaggie_setup_a'`
- **Issue:** Phase 6 functions (`passes_qullamaggie_setup_a`, `canslim_c_overlay`, `tag_playbook`) are imported inside `run_pipeline` via local `from X import Y` statements, not at module level. Monkeypatching `screener.publishers.pipeline.passes_qullamaggie_setup_a` therefore fails because there is no module-level attribute.
- **Fix:** Monkeypatches target the source modules (`screener.signals.qullamaggie`, `screener.signals.canslim`, `screener.signals.composite`, `screener.sizing`) so the local imports inside `run_pipeline` pick up the stubs.
- **Files modified:** `tests/test_pipeline_journal.py`
- **Commit:** c0d25d3

**3. [Rule 2 - Missing critical functionality] rs_component + trend_component in synthetic panel**
- **Found during:** Task 3 — pandera SchemaError `column 'rs_component' not in dataframe`
- **Issue:** `RankingSnapshotSchema` requires `rs_component` and `trend_component` columns. Since `score()` is mocked as an identity function, these columns must be provided in the synthetic panel.
- **Fix:** Added `rs_component` and `trend_component` to `_make_synthetic_multiindex_panel()`
- **Files modified:** `tests/test_pipeline_journal.py`
- **Commit:** c0d25d3

**4. [Rule 1 - Bug] write_pattern_audit_atomic does not exist in persistence.py**
- **Found during:** Task 3 — `AttributeError: module 'screener.persistence' has no attribute 'write_pattern_audit_atomic'`
- **Issue:** `pipeline.py` step 10 calls `persistence.write_pattern_audit_atomic(...)` inside a `try/except Exception` block. The function is referenced in a comment as a Plan 06-02 placeholder but was never implemented. The try/except swallows the AttributeError silently in production. The test's monkeypatch of this non-existent symbol failed loudly.
- **Fix:** In `_install_pipeline_mocks`, use `hasattr()` guard: only patch if the symbol exists, otherwise let the pipeline's existing `try/except` handle it silently.
- **Files modified:** `tests/test_pipeline_journal.py`
- **Commit:** c0d25d3

## Known Stubs

None — all plan goals achieved. The `write_pattern_audit_atomic` placeholder in persistence.py is pre-existing (Plan 06-02 responsibility) and is documented above as a deviation. It does not affect this plan's deliverables.

## Threat Surface Scan

No new threat surface introduced beyond what was already in the plan's threat model. The ticker-from-column bug fix (Rule 1 deviation above) is directly relevant to T-07-20 (spoofing via malformed ticker symbols) — the fix ensures `PicksSchema.str_matches` validation actually runs on real ticker strings rather than integer positions.

## Verification Results

All plan verification checks passed:

```
uv run pytest tests/test_pipeline_journal.py --no-cov -q        # 4 passed
uv run pytest tests/test_sizing.py --no-cov -q                  # green (Plan 07-02)
uv run pytest tests/test_journal.py --no-cov -q                 # green (Plan 07-03)
uv run pytest tests/test_publishers_pipeline.py --no-cov -q     # green
uv run pytest tests/test_publishers_report.py --no-cov -q       # 8 passed (7 existing + 1 new)
uv run pytest tests/test_backtest_no_lookahead.py --no-cov -q   # green (FND-04)
uv run pytest tests/test_architecture.py --no-cov -q            # green (D-23)
uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q  # green (D-24)

Total: 47 passed, 1 skipped, 0 failures

uv run ruff check src/screener/publishers/pipeline.py src/screener/publishers/report.py
# All checks passed!
```

## Self-Check: PASSED

All files found and all commits verified:
- src/screener/publishers/pipeline.py: FOUND
- src/screener/publishers/report.py: FOUND
- tests/test_pipeline_journal.py: FOUND
- tests/test_publishers_report.py: FOUND
- .planning/phases/07-sizing-finalization-paper-trade-journal/07-04-SUMMARY.md: FOUND
- c51d5f5 (Task 1): FOUND
- 689ce66 (Task 2): FOUND
- c0d25d3 (Task 3): FOUND
