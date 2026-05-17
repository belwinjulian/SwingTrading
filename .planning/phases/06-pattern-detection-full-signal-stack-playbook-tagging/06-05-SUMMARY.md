---
phase: 06-pattern-detection-full-signal-stack-playbook-tagging
plan: "05"
subsystem: pipeline-wiring
tags: [phase-6, cli, pipeline, snapshot, report, wiring, leader-hold-section, edgar, fundamentals, d19]
dependency_graph:
  requires: [06-04]
  provides: [refresh-fundamentals-body, pipeline-phase6-dag, d19-report-format, currently-held-leaders-section, write-pattern-audit-atomic]
  affects: [cli, publishers-pipeline, publishers-report, publishers-snapshot, persistence]
tech_stack:
  added: []
  patterns:
    - "Pitfall 9 two-pass top-N selection: qullamaggie+minervini -> top-N table; leader_hold -> separate section; none -> excluded"
    - "Inline JSON decode in report.py (_decode_diag) -- architecture constraint: publishers/ may not import indicators/"
    - "CAT-04 startup hook: _ensure_edgar_identity() raises SystemExit(msg) at top of refresh-fundamentals"
    - "W-Plan05-1 snapshot projection: today_panel projected to RankingSnapshotSchema cols BEFORE write_snapshot"
    - "T-3-02 carry-forward: log only error_type=type(e).__name__ in exception handlers"
key_files:
  created: []
  modified:
    - src/screener/cli.py
    - src/screener/publishers/pipeline.py
    - src/screener/publishers/report.py
    - src/screener/persistence.py
    - tests/test_cli_smoke.py
    - tests/test_publishers_pipeline.py
    - tests/test_publishers_report.py
    - tests/test_publishers_snapshot.py
    - docs/strategy_v1_preregistration.md
decisions:
  - "Architecture constraint enforced: publishers/report.py uses inline _decode_diag() rather than importing indicators.patterns.decode_pattern_diagnostics"
  - "mix_stderr=False removed from CliRunner() calls -- not supported by typer 0.25.x CliRunner (Rule 1 bug fix)"
  - "test count discrepancy resolved: plan said 11 CLI tests pre-edit but Plan 06-01 already added 2 stubs making it 14; replaced stub bodies in-place keeping count at 14"
metrics:
  duration: "~2h"
  completed_date: "2026-05-17"
  tasks_completed: 3
  files_modified: 9
---

# Phase 6 Plan 05: Wave 3 Wiring (Pipeline + CLI + Report) Summary

End-to-end wiring of Phase 6 parts: `refresh-fundamentals` CLI body with 3-step orchestrator and EDGAR identity guard; `publishers/pipeline.run_pipeline` DAG extended with Phase 6 steps; `publishers/report.py` updated to D-19 per-pick format with "Currently Held / Leaders" section; `persistence.write_pattern_audit_atomic` added; D-18 preregistration amendment landed.

## Tasks Completed

### Task 1: persistence.write_pattern_audit_atomic + Pipeline DAG Extension + W-Plan05-1 Projection

**Commit:** e490f5d

**persistence.py** — Added `write_pattern_audit_atomic(df, snapshot_date)` that validates against `PatternAuditSchema` and writes `data/pattern_audit/<date>.parquet` atomically via `_write_parquet_atomic`. Reuses `_assert_safe_snapshot_date` (T-06-25 path traversal defense).

**publishers/pipeline.py** — Extended `run_pipeline` with:
- Step 2a: `passes_qullamaggie_setup_a(panel)`
- Step 2b: `persistence.read_fundamentals(snap_ts)` — D-13b lag applied at read
- Step 2c: `canslim_c_overlay(panel, fundamentals, snap_ts)`
- Step 2d: `_add_catalyst_columns(panel, fundamentals, snap_ts)` — new helper
- Step 3a: `tag_playbook(panel)` — after score()
- Step 7a: W-Plan05-1 projection — `today_panel[[c for c in schema_cols if c in today_panel.columns]]` before `write_snapshot`; report receives full panel
- Step 10: `write_pattern_audit_atomic` for VCP/flag picks

New private helpers:
- `_add_catalyst_columns`: adds `days_to_next_earnings`, `earnings_in_3d_warn`, `crossed_52w_high_within_60d`, `insider_cluster_buy`, `eps_knowable_from`
- `_build_pattern_audit_df`: constructs per-leg audit DataFrame from `pattern_diagnostics` JSON (inline decode to avoid importing `indicators.patterns`)

**tests/test_publishers_pipeline.py** — 4 new tests appended (8 Phase 4 tests preserved):
- `test_run_pipeline_includes_phase_6_steps` — call-order assertions via monkeypatch
- `test_run_pipeline_writes_pattern_audit` — VCP panel -> pattern_audit written with real leg dates
- `test_run_pipeline_lag_d13b_applied` — read_fundamentals called with snap_ts
- `test_snapshot_strict_accepts_full_pipeline_panel` — W-Plan05-1 regression (pipeline-only cols don't leak to snapshot)

**Test count:** 12 (8 preserved + 4 added)

### Task 2: CLI refresh-fundamentals Body + EDGAR Identity Hook + CAT-04 Tests

**Commit:** 9af2f07

**src/screener/cli.py**:
- `_ensure_edgar_identity()` added: raises `SystemExit("EDGAR_IDENTITY env var is unset. SEC requires 'Name <email>' for User-Agent. See .env.example.")` when `EDGAR_IDENTITY` is empty (CAT-04 / T-06-23)
- `refresh-fundamentals` stub replaced with 3-step orchestrator:
  1. Finnhub/yfinance EPS via `screener.data.fundamentals.refresh_fundamentals(today=today, force=force)`
  2. EDGAR Form 4 via `screener.data.insider.refresh_insider(today=today)`
  3. Flags: `--force`, `--skip-insider`, `--insider-only` (D-09)
- T-3-02: `error_type=type(e).__name__` only; never `str(e)` in exception handlers
- `SystemExit` from `_ensure_edgar_identity` propagates (not caught by broad `Exception`)

**tests/test_cli_smoke.py**:
- `test_refresh_fundamentals_subcommand_no_longer_stub`: real mock-patched test replacing `pytest.skip`
- `test_edgar_identity_required`: EDGAR_IDENTITY='' -> exit!=0 + "EDGAR_IDENTITY" + ".env.example" in output

**Rule 1 deviation:** `CliRunner(mix_stderr=False)` -> `CliRunner()` — typer 0.25.x CliRunner does not support the `mix_stderr` keyword argument. Removed from both new test functions.

**Test count:** 14 (the plan said 11+2=13 but Plan 06-01 already added 2 stub tests making the pre-edit count 14; replaced stubs in-place keeping count at 14)

### Task 3: publishers/report D-19 Format + Currently Held/Leaders + Preregistration Amendment

**Commit:** 6b2bb2b

**src/screener/publishers/report.py**:
- `_decode_diag(raw)`: inline JSON decoder (architecture constraint: publishers/ cannot import indicators/)
- `_format_breakdown`: extended for D-19 full format:
  - `Pattern=0.67 (VCP, 4 contractions, brk_vol=2.1x)` or `flag, N bars` or `no pattern`
  - `Earnings=1 (EPS YoY >=25%)` or `Earnings=0 (EPS pending[, knowable YYYY-MM-DD])`
  - `Catalyst=0.33 (1/3 flags)`
- `_render_per_pick_block(i, row, lines)`: extracted helper for per-pick blocks (D-04/D-19), shared between top-N and leaders section; includes playbook line `(Q=N, M=N, LH=N)` and `WARNING: Earnings in Nd` when `earnings_in_3d_warn=True`
- `render_report`: Pitfall 9 two-pass selection when `playbook_tag` column present:
  - Pass 1: `{qullamaggie_continuation, minervini_vcp}` -> top-N table
  - Pass 2: `leader_hold` -> "Currently Held / Leaders" section (no cap, all picks)
  - `none` picks excluded entirely
  - Legacy fallback: when `playbook_tag` absent, use full scored_cross (backward compat with Phase 4 tests)

**tests/test_publishers_report.py** — 4 new tests appended:
- `test_d19_breakdown_format`: regex asserts on D-19 format
- `test_currently_held_section_separate`: leader_hold not in top-N table; "## Currently Held / Leaders" header present
- `test_none_tag_excluded`: none-tag picks absent from report
- `test_earnings_in_3d_warn_renders`: "WARNING: Earnings in" present for flagged picks

**tests/test_publishers_snapshot.py** — 1 new test appended:
- `test_52w_high_60d_flag`: schema accepts `crossed_52w_high_within_60d=True`

**docs/strategy_v1_preregistration.md** — D-18 amendment appended below References:
- "Amendment 2026-05-17 -- CANSLIM L/M de-duplication (D-18)"
- Weights table unchanged; preregistration CI still passes

**Test counts:** test_publishers_report.py = 11 (7+4), test_publishers_snapshot.py = 3 (2+1)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `CliRunner(mix_stderr=False)` unsupported by typer 0.25.x**
- **Found during:** Task 2
- **Issue:** `TypeError: CliRunner.__init__() got an unexpected keyword argument 'mix_stderr'` — the installed typer version's CliRunner does not accept this argument
- **Fix:** Removed `mix_stderr=False` from both `test_refresh_fundamentals_subcommand_no_longer_stub` and `test_edgar_identity_required`; typer's CliRunner merges stderr into output by default so `SystemExit` message still appears in `result.output`
- **Files modified:** `tests/test_cli_smoke.py`
- **Commit:** 9af2f07

**2. [Rule 2 - Architecture] publishers/report.py cannot import indicators.patterns**
- **Found during:** Task 3
- **Issue:** Plan code example used `from screener.indicators.patterns import decode_pattern_diagnostics` inside `_format_breakdown` — violates architecture constraint "publishers/ may import {signals, sizing, regime, persistence, config, obs}; NOT indicators"
- **Fix:** Inlined `_decode_diag(raw)` function in report.py using stdlib `json` — same approach used in `_build_pattern_audit_df` in pipeline.py (Task 1)
- **Files modified:** `src/screener/publishers/report.py`
- **Commit:** 6b2bb2b

### Deferred Items

- `hypothesis` module not installed: `tests/test_regime_score.py` and `tests/test_signals_composite.py` fail at collection with `ModuleNotFoundError: No module named 'hypothesis'`. This is a pre-existing issue unrelated to Plan 06-05 changes. Logged for future resolution (install `hypothesis` dev dependency).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced beyond what the plan's threat model already covers (T-06-23 through T-06-29 all mitigated as planned).

## Known Stubs

None — all Phase 6 placeholders in `_format_breakdown` are now wired. The report footer line "Composite score is capped at ~55/100 in Phase 4" is a historical note, not a functional stub.

## Phase 6 Success Criteria Status

1. **Golden-file pattern classification** (Plans 02+05): pipeline writes `pattern_diagnostics` JSON with real VCP/flag classifications; `test_run_pipeline_writes_pattern_audit` asserts B2 real leg dates.
2. **Pivot re-derived from adjusted closes; NVDA 2024 split test** (Plan 02): golden-file tests pass in test_patterns_golden.py (from Plan 02).
3. **Each pick declares playbook tag with breakdown** (Plans 04+05): `tag_playbook` runs in pipeline; D-19 format in `_format_breakdown`; `test_d19_breakdown_format` asserts format.
4. **Qullamaggie Setup A scan** (Plans 02+04): `passes_qullamaggie_setup_a` in pipeline DAG at step 2a.
5. **days_to_next_earnings + crossed_52w_high_within_60d + insider_cluster_buy + EDGAR identity** (this plan): `_add_catalyst_columns` helper adds all four; `_ensure_edgar_identity` startup hook; `test_edgar_identity_required` GREEN.
6. **CANSLIM C+L+M additive scoring with 45-day lag** (Plans 03+04+05): `canslim_c_overlay` at step 2c; D-13b lag via `read_fundamentals(snap_ts)`; D-18 amendment documents L/M de-duplication.

## Self-Check: PASSED

- src/screener/cli.py: FOUND, contains `_ensure_edgar_identity`
- src/screener/publishers/report.py: FOUND, contains `Currently Held / Leaders`
- src/screener/publishers/pipeline.py: contains `tag_playbook`
- src/screener/persistence.py: contains `write_pattern_audit_atomic`
- docs/strategy_v1_preregistration.md: contains `CANSLIM L` amendment
- Commits: e490f5d (Task 1), 9af2f07 (Task 2), 6b2bb2b (Task 3) all verified via git log
- Full test suite (excluding pre-existing hypothesis import errors): 191 passed, 2 skipped
