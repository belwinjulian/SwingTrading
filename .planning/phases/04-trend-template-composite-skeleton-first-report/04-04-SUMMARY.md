---
phase: "04"
plan: "04"
subsystem: publishers
tags: [publishers, pipeline, snapshot, report, D-03, D-07, D-08, OUT-01, OUT-02, OUT-03, tdd, wave-3]
dependency_graph:
  requires: [04-01, 04-02, 04-03]
  provides: [run_pipeline orchestrator, apply_regime_gate, validate_run, write_snapshot, render_report, write_report, _classify_pivot_zone, _add_publisher_columns]
  affects: [04-05-cli-wiring]
tech_stack:
  added: []
  patterns: [D-16 re-export via signals/__init__.py for build_panel access, tempfile+os.replace Markdown analog of _write_parquet_atomic, Literal 3-state pivot zone, PHASE_4_ZEROED iteration for placeholder rendering]
key_files:
  created:
    - src/screener/publishers/pipeline.py
    - src/screener/publishers/snapshot.py
    - src/screener/publishers/report.py
    - tests/test_publishers_pipeline.py
    - tests/test_publishers_snapshot.py
    - tests/test_publishers_report.py
  modified:
    - src/screener/signals/__init__.py
    - tests/test_rs_snapshot.py
decisions:
  - "build_panel re-exported via signals/__init__.py (not direct indicators import) to satisfy D-16 publishers ALLOWED = {signals, sizing, regime, persistence, config, obs}"
  - "em dash in report header '# Daily Picks — YYYY-MM-DD' per plan spec; test written to match"
  - "Ruff B905: added strict=False to zip() in _add_publisher_columns for compliant same-length Series zipping"
  - "PIVOT_COLUMN_HEADER line split to satisfy 100-char E501 constraint in render_report table header"
metrics:
  duration: "~9 minutes"
  completed_date: "2026-05-10"
  tasks_completed: 3
  files_changed: 8
---

# Phase 04 Plan 04: Publishers Layer (pipeline + snapshot + report) Summary

**One-liner:** Three publishers modules — D-03 soft regime gate via apply_regime_gate, D-07/D-08 dual-channel pass-rate guard via validate_run, atomic Parquet snapshot (thin wrapper), and Markdown report with 5-section layout + per-pick PHASE_4_ZEROED placeholders — 15 tests all green.

## What Was Built

### Task 1: src/screener/publishers/pipeline.py (180 lines)

Three public functions:

**apply_regime_gate(scored_panel, regime_score)** (line 40):
- D-03 soft gate: `composite_score *= regime_score` on the cross-section frame
- Pitfall 6 defensive: `assert 0.0 <= regime_score <= 1.0` (raises AssertionError before mutating)
- Returns a copy — original frame untouched

**validate_run(pass_rate, regime_state, warn_threshold, fail_threshold_with_correction)** (line 63):
- D-07: `pass_rate > warn_threshold` emits structlog event `"trend_template_pass_rate_high"` — no exit
- D-08: adds `"Correction"` AND `pass_rate > fail_threshold` → emits `"data_quality_gate_failed"` + raises `typer.Exit(code=1)` (line 102)
- Mirrors cli.py refresh_ohlcv health-gate pattern (lines 130-144)

**run_pipeline(snapshot_date, write_report=True)** (line 108):
- Orchestrates: `build_panel → passes_trend_template → composite.score → apply_regime_gate → validate_run → write_snapshot + optional write_report`
- `write_report=False` path skips Markdown (used by `screener score` subcommand per RESEARCH §10)
- Imports: `from screener.signals import build_panel` (re-export from signals/ — see deviation below)

**Deviation [Rule 1 - Bug] — Architecture violation in plan template:**
- Plan template included `from screener.indicators import build_panel` at top level of pipeline.py
- D-16 ALLOWED["publishers"] = {signals, sizing, regime, persistence, config, obs} — `indicators` is FORBIDDEN
- Fix: added `from screener.indicators import build_panel` to `signals/__init__.py` as a re-export; `signals/` is allowed to import from `indicators/` per D-16 ALLOWED["signals"] = {indicators, regime, persistence, config, obs}
- pipeline.py uses `from screener.signals import build_panel` — passes architecture test

### Task 2: src/screener/publishers/snapshot.py (38 lines)

**write_snapshot(scored_panel, snapshot_date)** (line 23):
- Thin wrapper: delegates entirely to `persistence.write_snapshot_atomic`
- Returns the Path written; emits `"publisher_snapshot_complete"` structlog event
- D-11 atomic-write contract preserved (crash-test in test_rs_snapshot.py confirms)
- T-4-01 path-traversal defense: `_assert_safe_snapshot_date` in persistence rejects non-YYYY-MM-DD

### Task 3: src/screener/publishers/report.py (291 lines)

Public functions and constants:

**PIVOT_COLUMN_HEADER** (line 35): `"ATR from 52w high (Phase 4 proxy)"` — D-05 verbatim

**_classify_pivot_zone(close, high_52w, atr)** (line 46):
- 3-state Literal["in-zone", "chase, skip", "unknown"]
- Pitfall 5 NaN-safe: returns "unknown" if high_52w is NaN, atr is NaN, or atr == 0
- "in-zone" when `(close - high_52w) / atr <= 1.0`; "chase, skip" otherwise

**_add_publisher_columns(cross, regime_row)** (line 60):
- Adds `pivot_distance_atr`, `pivot_zone`, `regime_state`, `regime_score`, `rank` to a cross-section frame
- Required to satisfy RankingSnapshotSchema before snapshot write

**_format_breakdown(row)** (line 91):
- D-04: iterates `DEFAULT_WEIGHTS` keys; renders `PHASE_4_ZEROED` entries as `"--(Phase 6)"` placeholders
- File: `src/screener/publishers/report.py`, line 91-115

**_write_text_atomic(content, target)** (line 118):
- Markdown analog of `persistence._write_parquet_atomic`
- `tempfile.NamedTemporaryFile(dir=target.parent)` + `os.replace()` = POSIX-atomic same-filesystem rename
- On exception: `.tmp` unlinked (missing_ok=True), no partial file

**render_report(scored_cross, regime_row, snapshot_date, top_n, pass_rate)** (line 147):
- 5-section Markdown output: `# Daily Picks`, `## Regime`, `## Top {N} Picks`, `## Per-Pick Detail`, `## Data Quality`
- D-07 WARNING banner (plain ASCII, no emoji) when `pass_rate > settings.TREND_TEMPLATE_PASS_RATE_WARN`
- T-4-13: `ticker.replace("|", "")` in table rows to prevent Markdown injection

**write_report(...)** (line 273): renders + atomically writes to `reports/<date>.md`

## D-04 Placeholder Rendering

**File:line:** `src/screener/publishers/report.py:91-115` (`_format_breakdown`)

```python
for key in DEFAULT_WEIGHTS:
    label = key.capitalize()
    if key in PHASE_4_ZEROED:
        parts.append(f"{label}=--(Phase 6)")
    elif key == "rs":  ...
    elif key == "trend":  ...
    elif key == "volume":  ...
```

Iterates `DEFAULT_WEIGHTS` keys; checks membership in `PHASE_4_ZEROED = {"pattern", "earnings", "catalyst"}` to emit the placeholder label. Phase 6 removes keys from `PHASE_4_ZEROED` and the placeholders disappear automatically.

## D-05 Pivot Column Header

**File:line:** `src/screener/publishers/report.py:35`

```python
PIVOT_COLUMN_HEADER = "ATR from 52w high (Phase 4 proxy)"  # D-05 verbatim
```

Used in the top-N picks table header. Verified by `test_pivot_column_header_d05`.

## D-07 WARNING Banner

**File:line:** `src/screener/publishers/report.py:250-254`

```python
if pass_rate > warn_thresh:
    # Pitfall 12: plain ASCII 'WARNING:', no emoji.
    lines.append(
        f"**WARNING: Pass rate {pass_rate * 100:.1f}% "
        f"(expected 5-15% -- verify data quality)**"
    )
```

No emoji anywhere in the output. `grep -cE "⚠|🚨|❌|✅" src/screener/publishers/report.py` outputs `0`.

## D-08 typer.Exit Propagation

**File:line:** `src/screener/publishers/pipeline.py:102`

```python
raise typer.Exit(code=1)
```

Test that proves it: `test_data_quality_gate_failed_in_correction_d08` in `tests/test_publishers_pipeline.py`.

## D-16 Architecture Test Status

`pytest tests/test_architecture.py -v` — 3 passed.

- `test_layer_import_contract`: PASS (publishers/ imports only signals/regime/persistence/config/obs)
- `test_backtest_does_not_import_data_layer`: PASS
- `test_indicators_signals_pure_no_io_imports`: PASS

## Test Count: 15 (6 pipeline + 2 snapshot + 7 report)

| File | Tests | What they verify |
|------|-------|-----------------|
| test_publishers_pipeline.py | 6 | D-03 soft gate multiplication, Pitfall 6 range assertion, D-07 warn-only, D-08 exit=1, silent-below-threshold, Correction+low-rate ok |
| test_publishers_snapshot.py | 2 | OUT-03 write path, T-4-01 path-traversal rejection |
| test_publishers_report.py | 7 | OUT-01 file written, all 5 sections present, D-04 per-pick breakdown, Pitfall 5 pivot zone labels, D-07 WARNING banner, D-05 column header, atomic-write crash |

Additional tests in test_rs_snapshot.py: `test_snapshot_atomic_write_crash_no_residue` (1 new test — crash confirms D-11 contract for write_snapshot_atomic).

Total tests run in full sampling check: 52 passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Architecture violation in plan template — indicators import**
- **Found during:** Task 1 GREEN phase (test_architecture.py::test_layer_import_contract)
- **Issue:** Plan template included `from screener.indicators import build_panel` as a top-level import in pipeline.py. D-16 ALLOWED["publishers"] does NOT include `indicators`. The AST-based architecture test caught this.
- **Fix:** Added `from screener.indicators import build_panel` to `signals/__init__.py` as a re-export. Updated pipeline.py to use `from screener.signals import build_panel`. signals/ is permitted to import from indicators/ per D-16.
- **Files modified:** `src/screener/signals/__init__.py`, `src/screener/publishers/pipeline.py`
- **Commit:** ff24ada

**2. [Rule 1 - Bug] Ruff lint issues in report.py and test file**
- **Found during:** Task 3 verification
- **Issues:** B905 (zip without strict=), E501 (long lines in docstring/table header), F841 (unused variable in test)
- **Fix:** Added `strict=False` to `zip()` in `_add_publisher_columns`; split docstring/table header lines; removed unused `original_replace` variable in test
- **Files modified:** `src/screener/publishers/report.py`, `tests/test_publishers_report.py`
- **Commit:** 160bce3

## Known Stubs

The following are intentional Phase 4 placeholders per D-01, tracked by `PHASE_4_ZEROED` in `signals/composite.py`:

| Component | Rendered as | Phase resolving |
|-----------|-------------|-----------------|
| `pattern_component` | `Pattern=--(Phase 6)` in per-pick blocks | Phase 6 |
| `earnings_component` | `Earnings=--(Phase 6)` in per-pick blocks | Phase 6 |
| `catalyst_component` | `Catalyst=--(Phase 6)` in per-pick blocks | Phase 6 |
| Playbook tagging | `Playbook: --(Phase 6)` | Phase 6 |
| Catalyst annotation | `Catalysts: --(Phase 6)` | Phase 6 |

These placeholders are intentional per D-04 and D-01. The maximum composite score in Phase 4 is ~55/100 (live weights: RS 25% + Trend 20% + Volume 10% = 55%). Phase 6 adds the remaining components.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes at trust boundaries beyond what is in the plan's threat model.

Threat mitigations applied as planned:
- **T-4-13** (ticker Markdown injection): `ticker.replace("|", "")` in render_report table loop — `src/screener/publishers/report.py:177`
- **T-4-14** (atomic write): `_write_text_atomic` uses tempfile in `target.parent` + `os.replace` — crash test verifies
- **T-4-17** (regime_score > 1.0): `apply_regime_gate` asserts `0.0 <= regime_score <= 1.0` — `pipeline.py:53`

## CI Gate Status

| Gate | Result |
|------|--------|
| D-16: `test_layer_import_contract` | PASS |
| `uv run mypy src/screener/publishers/` | PASS (4 files, 0 issues) |
| `uv run ruff check src/screener/publishers/` | PASS |
| `grep -cE "⚠|🚨|❌|✅" src/screener/publishers/report.py` | 0 (Pitfall 12 clean) |
| 15 publisher tests | PASS |
| 52 total tests in sampling check | PASS |

## Self-Check: PASSED

Verified files exist:

- `src/screener/publishers/pipeline.py` contains `def apply_regime_gate`, `def validate_run`, `def run_pipeline`, `raise typer.Exit(code=1)`, `"trend_template_pass_rate_high"`, `"data_quality_gate_failed"`, `"regime_score out of range"` — all CONFIRMED
- `src/screener/publishers/snapshot.py` contains `def write_snapshot`, `from screener.persistence import write_snapshot_atomic` — CONFIRMED
- `src/screener/publishers/report.py` contains `def render_report`, `def write_report`, `def _classify_pivot_zone`, `def _format_breakdown`, `def _write_text_atomic`, `def _add_publisher_columns`, `PIVOT_COLUMN_HEADER`, `"ATR from 52w high (Phase 4 proxy)"`, `from screener.signals.composite import DEFAULT_WEIGHTS, PHASE_4_ZEROED`, `"WARNING:"` — all CONFIRMED
- `tests/test_publishers_pipeline.py` contains 6 required test functions — CONFIRMED
- `tests/test_publishers_snapshot.py` contains 2 required test functions — CONFIRMED
- `tests/test_publishers_report.py` contains 7 required test functions — CONFIRMED
- `tests/test_rs_snapshot.py` contains `test_snapshot_atomic_write_crash_no_residue` — CONFIRMED

Verified commits exist:
- `532479e` — test(04-04): RED for pipeline tests
- `ff24ada` — feat(04-04): pipeline.py + signals/__init__.py re-export (GREEN)
- `0d67b6d` — test(04-04): RED for snapshot tests + rs_snapshot crash test
- `92a2d7d` — feat(04-04): snapshot.py (GREEN)
- `de44ece` — test(04-04): RED for report tests
- `160bce3` — feat(04-04): report.py (GREEN)
