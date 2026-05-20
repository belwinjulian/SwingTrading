---
phase: 07-sizing-finalization-paper-trade-journal
verified: 2026-05-18T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run `screener report` or `screener score` on a date with cached OHLCV data, then query `data/journal.sqlite` to confirm rows are present with correct playbook_tag, shares, stop_price, entry_price, atr_zone, and features_json structure"
    expected: "One or more rows in the `picks` table with composite_score >= 50, valid playbook_tag (qullamaggie_continuation / minervini_vcp / leader_hold), non-zero shares, and a parseable features_json blob containing 'features_json_version': 'v1.0'"
    why_human: "End-to-end pipeline execution requires real OHLCV cache and live data dependencies (build_panel, regime computation) that cannot be exercised by the automated verifier without the full data layer"
  - test: "Run `screener journal` when no snapshot exists, then verify exit code 0 and that no stub log line appears"
    expected: "Structured JSON event with event='journal_catchup_snapshot_missing' OR 'journal_catchup_empty'; process exits 0; no '[stub] journal not yet implemented' in stdout"
    why_human: "Requires invoking the real CLI against a live filesystem state; the verifier confirmed the body is wired but the two-stage happy/missing-snapshot path is best confirmed by a human spot-check (already partly documented in 07-05-SUMMARY Task 3)"
---

# Phase 7: Sizing Finalization & Paper-Trade Journal Verification Report

**Phase Goal:** Complete sizing finalization and paper-trade journal — every actionable pick produced by the evening screener now has a concrete entry price, stop loss, position size, and trail rule. The journal persists these picks to SQLite so that tomorrow's outcome tracking closes the paper-trade loop.

**Verified:** 2026-05-18
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Position sizer computes shares = (equity × risk_pct × regime_score) / (entry - stop), capped at 25% equity; auto-rejects picks where risk_per_share > 1×ADR_dollars | ✓ VERIFIED | `compute_sizing()` in `sizing.py` lines 314-320 implements exact formula; 11 unit tests pass including `test_shares_formula` and `test_adr_reject_boundary` (output: 25 passed) |
| 2 | Per-playbook stop dispatch: Qullamaggie → entry-day low; Minervini VCP → pivot_price × (1 - final_contraction_depth); leader-hold → 1.5-2×ATR swing-low | ✓ VERIFIED | `STOP_HELPERS` dict at `sizing.py:170-174` maps all three; `_stop_qullamaggie`, `_stop_minervini_vcp`, `_stop_leader_hold` all implemented; `test_stop_dispatch_per_playbook` passes identity assertion |
| 3 | ATR zone 3-bucket annotation (in-zone ≤0.66, extended ≤1.0, chase skip >1.0) surfaces in report per pick | ✓ VERIFIED | `classify_atr_zone()` in `sizing.py:60-70` implements all 3 buckets; `render_report` adds `**Zone:**` line at `report.py:346`; `test_atr_zone_boundaries` + `test_render_report_includes_sizing_fields_and_skipped_section` both pass |
| 4 | Every actionable pick appended to data/journal.sqlite at publish time; decision columns immutable via SQLite trigger | ✓ VERIFIED | `_PICKS_DDL` at `persistence.py:1024` contains `CREATE TRIGGER IF NOT EXISTS picks_immutable_decision_cols`; `append_picks_rows` uses INSERT OR IGNORE; pipeline step 8.5 fires after `write_snapshot`; `test_immutability_trigger` and all 4 `test_pipeline_journal.py` tests pass |
| 5 | features_json blob stores full score-component snapshot at signal time | ✓ VERIFIED | `_build_journal_rows_df()` in `pipeline.py:591-663` builds 13+ component fields + 9 indicators + sizing inputs + inline `pattern_diagnostics` dict + `features_json_version='v1.0'`; `test_golden_pipeline_journal` asserts exact key presence |
| 6 | Journal schema: 6 nullable outcome columns (entry_filled, exit_price, exit_date, hold_days, mfe, mae) — updatable, not locked by trigger | ✓ VERIFIED | `_PICKS_DDL` at `persistence.py:1033-1042` defines all 6 as nullable; trigger `BEFORE UPDATE OF` col-list explicitly excludes them; `test_outcome_column_updatable` and `test_outcome_col_not_in_trigger` pass |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `src/screener/sizing.py` | compute_sizing() + STOP_HELPERS + 3 _stop_* + classify_atr_zone + _trail_rule_label | ✓ VERIFIED | 360 lines; all 8 required functions present; no I/O, no print(), imports screener.indicators.patterns |
| `src/screener/config.py` | RISK_PCT=0.01, JOURNAL_THRESHOLD=50.0, JOURNAL_DB_PATH | ✓ VERIFIED | All 3 fields present (confirmed by runtime: RISK_PCT=0.01, JOURNAL_THRESHOLD=50.0, JOURNAL_DB_PATH=data/journal.sqlite) |
| `src/screener/persistence.py` | _PICKS_DDL + _journal_db_path + _ensure_picks_schema + append_picks_rows + read_picks_for_date + PicksSchema + RankingSnapshotSchema +10 cols | ✓ VERIFIED | All 6 new symbols found at lines 379/1024/1068/1074/1089/1133; RankingSnapshotSchema = 38 columns (28 base + 10 Phase 7) |
| `src/screener/publishers/pipeline.py` | run_pipeline(write_journal=True) + sizing step 5.5 + journal step 8.5 + _build_journal_rows_df + _build_journal_rows_df_from_snapshot | ✓ VERIFIED | Both helpers present; write_journal parameter confirmed; compute_sizing called on full cross-section before write_snapshot |
| `src/screener/publishers/report.py` | render_report/write_report with skipped_picks kwarg + Entry/Stop/Trail/Shares/Zone per-pick block + ## Skipped Picks section | ✓ VERIFIED | Both signatures updated; per-pick block at lines 343-346; ## Skipped Picks at line 482 |
| `src/screener/cli.py` | journal command with real body (no _stub call) | ✓ VERIFIED | `_stub("journal")` removed; body calls `_build_journal_rows_df_from_snapshot` + `validate_at_write` + `append_picks_rows` |
| `tests/test_sizing.py` | 11 tests, 0 skips | ✓ VERIFIED | 11 test functions; 0 pytest.skip calls; all 11 pass |
| `tests/test_journal.py` | 10 tests, 0 skips | ✓ VERIFIED | 10 test functions; 0 pytest.skip calls; all 10 pass |
| `tests/test_pipeline_journal.py` | 4 tests, 0 skips | ✓ VERIFIED | 4 test functions; 0 pytest.skip calls; all 4 pass |
| `.gitignore` | !/data/journal.sqlite allowlist | ✓ VERIFIED | `grep -c "!/data/journal\.sqlite" .gitignore` = 1 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sizing.py` | `indicators/patterns.py` | `from screener.indicators.patterns import find_pivots, decode_pattern_diagnostics` | ✓ WIRED | Import present at `sizing.py:30-34`; architecture test ALLOWED dict updated to permit `sizing → indicators` at `test_architecture.py:35` |
| `pipeline.py` | `sizing.compute_sizing` | `from screener.sizing import compute_sizing` (step 5.5) | ✓ WIRED | Import + call at `pipeline.py:395-403`; FULL cross-section passed (Blocker #1 satisfied) |
| `pipeline.py` | `persistence.append_picks_rows` | step 8.5 after write_snapshot | ✓ WIRED | `append_picks_rows(validated.to_dict(...))` at `pipeline.py:495`; fires after `write_snapshot` at line 463 |
| `cli.journal()` | `pipeline._build_journal_rows_df_from_snapshot` | call at `cli.py:252` | ✓ WIRED | Import at `cli.py:249`; called with `date.today().isoformat()` |
| `persistence._ensure_picks_schema` | SQLite file via `conn.executescript(_PICKS_DDL)` | `executescript` call | ✓ WIRED | `persistence.py:1085` |
| `report.render_report` | `## Skipped Picks` section | `skipped_picks` kwarg | ✓ WIRED | Signature at `report.py:356`; section rendered at `report.py:481-521` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `compute_sizing()` | stop_price, shares, atr_zone | STOP_HELPERS dispatch + shares formula | Yes — formula-driven from row values | ✓ FLOWING |
| `_build_journal_rows_df()` | features_json | score components from actionable_view | Yes — iterrows over real panel data | ✓ FLOWING |
| `run_pipeline` step 8.5 | journal rows | actionable_view derived from today_panel | Yes — derived view from FULL sized frame | ✓ FLOWING |
| `_build_journal_rows_df_from_snapshot` | journal rows | pd.read_parquet(snapshot) | Yes — real parquet read; adr_rejected + composite_score_raw from file | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 25 Phase 7 tests pass | `.venv/bin/python -m pytest tests/test_sizing.py tests/test_journal.py tests/test_pipeline_journal.py --no-cov -q` | 25 passed, 4 warnings | ✓ PASS |
| Architecture test passes (sizing → indicators) | `.venv/bin/python -m pytest tests/test_architecture.py --no-cov -q` | 4 passed | ✓ PASS |
| CLI smoke test passes (D-24 surface lock + journal no-longer-stub) | `.venv/bin/python -m pytest tests/test_cli_smoke.py --no-cov -q` | 13 passed, 2 skipped | ✓ PASS |
| Report tests pass (sizing per-pick + skipped section) | `.venv/bin/python -m pytest tests/test_publishers_report.py --no-cov -q` | 8 passed | ✓ PASS |
| FND-04 no-lookahead gate | `.venv/bin/python -m pytest tests/test_backtest_no_lookahead.py --no-cov -q` | 2 passed | ✓ PASS |
| PHASE_1_STUBS is empty | Python import check | `PHASE_1_STUBS == []` confirmed from test_cli_smoke.py source read | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SIZ-01 | 07-01, 07-02 | shares = (equity × risk_pct × regime_score) / (entry - stop), capped at 25% equity | ✓ SATISFIED | `compute_sizing` lines 314-320; `test_shares_formula` passes |
| SIZ-02 | 07-01, 07-02 | Auto-reject when risk_per_share > 1×ADR_dollars; reason surfaced in report | ✓ SATISFIED | `adr_exceeded` path at `sizing.py:307-308`; `## Skipped Picks` section in report; `test_adr_reject_boundary` passes |
| SIZ-03 | 07-01, 07-02 | Per-playbook stop: Qullamaggie=low-of-entry-day, VCP=final-contraction-low, leader=swing-low | ✓ SATISFIED | STOP_HELPERS registry; 3 `_stop_*` helpers; `test_stop_dispatch_per_playbook` + `test_vcp_stop_from_diagnostics` + `test_leader_swing_fallback` pass |
| SIZ-04 | 07-01, 07-02 | Per-playbook trail: Qullamaggie 10/20/50d SMA by speed, VCP 21d EMA/50d SMA, leader 50d SMA close | ✓ SATISFIED | `_trail_rule_label()` at `sizing.py:75-95`; `test_trail_label_dispatch` + `test_qull_trail_speed_tiers` pass |
| SIZ-05 | 07-01, 07-02 | ATR zone annotation (in-zone / extended / chase, skip) | ✓ SATISFIED | `classify_atr_zone()` at `sizing.py:60-70`; PicksSchema allows all 3; `test_atr_zone_boundaries` passes |
| OUT-04 | 07-01, 07-03, 07-04, 07-05 | Actionable picks appended to journal at publish time; idempotent | ✓ SATISFIED | `_build_journal_rows_df` + `append_picks_rows` in pipeline step 8.5; INSERT OR IGNORE on UNIQUE(ticker, snapshot_date); `test_pipeline_writes_journal` + `test_journal_cli_idempotent` pass |
| OUT-05 | 07-01, 07-03 | Append-only, decision columns immutable; features_json blob with full signal snapshot | ✓ SATISFIED | SQLite trigger at `_PICKS_DDL`; `test_immutability_trigger` + `test_features_json_roundtrip` + `test_features_json_includes_diagnostics` pass |
| OUT-06 | 07-01, 07-03 | 6 nullable outcome columns (entry_filled, exit_price, exit_date, hold_days, mfe, mae) | ✓ SATISFIED | All 6 in DDL as nullable INTEGER/REAL/TEXT; trigger explicitly excludes them; `test_outcome_column_updatable` + `test_outcome_col_not_in_trigger` pass |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `tests/test_cli_smoke.py` lines 339-356 | Two `pytest.skip` calls — `test_refresh_fundamentals_subcommand_no_longer_stub` and `test_edgar_identity_required` | ℹ️ Info | Pre-existing Phase 6 deferrals (Plan 06-05 Wave 4), NOT Phase 7 items. PHASE_1_STUBS is now empty. No Phase 7 impact. |
| None | No TODO/FIXME/placeholder patterns in Phase 7 files | — | All sizing, persistence, pipeline, report, and CLI files clean |

### Human Verification Required

### 1. End-to-End Pipeline Smoke Test

**Test:** With real OHLCV cache available, run `screener score` or `screener report` for a recent trading date. Then query the journal: `sqlite3 data/journal.sqlite "SELECT ticker, composite_score, playbook_tag, shares FROM picks ORDER BY composite_score DESC LIMIT 5;"`

**Expected:** Rows with composite_score >= 50, playbook_tag in the locked enum set, shares > 0 for non-rejected picks. The report file (if using `screener report`) should contain `**Entry:**`, `**Stop:**`, `**Trail:**`, `**Shares:**`, and `**Zone:**` fields per pick.

**Why human:** Full pipeline execution requires real OHLCV Parquet cache (build_panel), regime computation (compute_for_date), and canslim/qullamaggie/pattern layers. The verifier confirmed all wiring exists and integration tests pass with synthetic data, but real data execution requires the developer to confirm sizing values are sensible.

### 2. Journal CLI Idempotency on Live Snapshot

**Test:** After running `screener score` (which writes a real snapshot), run `screener journal` twice and inspect structlog output.

**Expected:** First invocation emits `journal_catchup_complete` with `n_inserted > 0`. Second invocation emits `journal_catchup_complete` with `n_inserted=0` and `n_idempotent_skip == n_attempted`. Both exit code 0. No `[stub]` log line.

**Why human:** The automated `test_journal_cli_idempotent` covers this with a synthetic snapshot, but the developer should confirm the real-world path works with the actual data stack once OHLCV data is present.

### Gaps Summary

No gaps found. All 6 must-have truths are verified with code evidence and passing test suites. All 8 phase requirement IDs (SIZ-01 through SIZ-05, OUT-04 through OUT-06) are satisfied by the implementation. The two human verification items require real data execution that cannot be performed programmatically without the full OHLCV cache.

---

_Verified: 2026-05-18_
_Verifier: Claude (gsd-verifier)_
