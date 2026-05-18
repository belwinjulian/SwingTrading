---
phase: 07-sizing-finalization-paper-trade-journal
plan: "01"
subsystem: config-settings, persistence-schemas, test-infrastructure
tags: [phase-7, foundation, settings, schemas, fixtures, gitignore, conftest, wave-0]
dependency_graph:
  requires:
    - 06-05-SUMMARY.md (Phase 6 pipeline projection + RankingSnapshotSchema 28-col base)
  provides:
    - Settings.RISK_PCT (0.01), Settings.JOURNAL_THRESHOLD (50.0), Settings.JOURNAL_DB_PATH
    - RankingSnapshotSchema 38 columns (28 base + 10 Phase 7 sizing cols, all nullable=True)
    - data/journal.sqlite gitignore allowlist (paper-trade commit policy resolved)
    - sized_input_cross() function-scope conftest fixture (5-ticker, 14 columns)
    - tests/test_sizing.py, tests/test_journal.py, tests/test_pipeline_journal.py (25 skip skeletons)
  affects:
    - 07-02-PLAN.md (reads RISK_PCT/ACCOUNT_EQUITY; bodies land in test_sizing.py)
    - 07-03-PLAN.md (bodies land in test_journal.py + test_pipeline_journal.py)
    - 07-04-PLAN.md (uses sized_input_cross fixture; pipeline populates Phase 7 cols)
    - 07-05-PLAN.md (test_journal.py::test_journal_cli_idempotent body)
tech_stack:
  added: []
  patterns:
    - additive-settings-extension (Phase 6 D-09 idiom — RISK_PCT, JOURNAL_THRESHOLD, JOURNAL_DB_PATH)
    - pandera-schema-additive-extension (10 new cols with nullable=True on RankingSnapshotSchema)
    - gitignore-allowlist-carveout (!/data/journal.sqlite mirrors !/data/ohlcv/**/splits.parquet)
    - conftest-function-scope-fixture (sized_input_cross Pitfall 7 mitigation)
    - pytest-skip-skeleton-pattern (Plan 07-02/03/04 wave coordination via named skeletons)
key_files:
  created:
    - tests/test_sizing.py (11 named pytest.skip skeletons for SIZ-01..05)
    - tests/test_journal.py (10 named pytest.skip skeletons for OUT-04..06)
    - tests/test_pipeline_journal.py (4 named pytest.skip skeletons for pipeline integration)
  modified:
    - src/screener/config.py (RISK_PCT, JOURNAL_THRESHOLD, JOURNAL_DB_PATH added)
    - .env.example (Phase 7 section with RISK_PCT=0.01, JOURNAL_THRESHOLD=50.0)
    - src/screener/persistence.py (RankingSnapshotSchema +10 Phase 7 cols)
    - .gitignore (!/data/journal.sqlite allowlist)
    - tests/conftest.py (sized_input_cross() fixture appended)
decisions:
  - "JOURNAL_THRESHOLD=50.0 not 0.5 — composite_score scale is 0-100 (RankingSnapshotSchema ge=0,le=100); CONTEXT.md typo caught by RESEARCH Open Question 1 and PATTERNS.md"
  - "All 10 Phase 7 sizing cols are nullable=True (revision iteration 1 Blocker #2) — plan 07-04 writes FULL universe ~1000 rows; ~95% have playbook_tag='none' per composite.py:261"
  - "atr_zone isin includes 'not_applicable' sentinel rather than nullable=True — preserves enum integrity on actionable rows while accommodating non-actionable rows"
  - "Schema has 38 columns not 36 — Phase 6 base was 28 cols (plan summary said 26; actual count confirmed 28); +10 Phase 7 = 38 total; all verification assertions pass"
  - "data/journal.sqlite git-commit policy: YES commit (RESEARCH A4) — paper-trade history is v1.x performance contract; resolves STATE.md open todo"
metrics:
  duration: 4m
  completed_date: "2026-05-18"
  tasks: 3
  files: 8
---

# Phase 07 Plan 01: Foundation — Settings, Schemas, Fixtures Summary

Wave 0 foundation for Phase 7: typed Settings extensions (RISK_PCT, JOURNAL_THRESHOLD, JOURNAL_DB_PATH), RankingSnapshotSchema extended with 10 nullable Phase 7 sizing columns, data/journal.sqlite gitignore allowlist, sized_input_cross() conftest fixture, and 25 pytest.skip skeleton tests (test_sizing/test_journal/test_pipeline_journal) so Wave 1 plans 07-02 and 07-03 can land bodies inside pre-existing stubs.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Extend Settings with RISK_PCT, JOURNAL_THRESHOLD, JOURNAL_DB_PATH | b676b50 | src/screener/config.py, .env.example |
| 2 | Extend RankingSnapshotSchema + .gitignore carve-out | 3e410d8 | src/screener/persistence.py, .gitignore |
| 3 | sized_input_cross fixture + 3 skeleton test files | 9d66918 | tests/conftest.py, tests/test_sizing.py, tests/test_journal.py, tests/test_pipeline_journal.py |

## Verification Results

All Phase 7 Wave 0 surface checks passed:

- `25 skipped` — test_sizing.py + test_journal.py + test_pipeline_journal.py (zero errors)
- `8 passed` — tests/test_publishers_pipeline.py (Phase 6 W-Plan05-1 projection regression)
- `4 passed` — tests/test_architecture.py (D-23 ALLOWED dict unchanged)
- `1 passed` — tests/test_cli_smoke.py::test_subcommand_surface_locked (D-24 9-subcommand lock)
- `2 passed` — tests/test_backtest_no_lookahead.py (FND-04 mutation gate)
- Settings import: `RISK_PCT=0.01, JOURNAL_THRESHOLD=50.0, JOURNAL_DB_PATH=data/journal.sqlite`
- Schema column count: `38 columns` (28 base + 10 Phase 7)

## Deviations from Plan

### JOURNAL_THRESHOLD scale correction (auto-applied per plan spec)

The plan document itself documents this: "CRITICAL VALUES: JOURNAL_THRESHOLD=50.0 NOT 0.5 — composite_score is bounded ge=0.0, le=100.0 per RankingSnapshotSchema:232; CONTEXT line 30 said 0.5 using the wrong scale (caught by RESEARCH Open Question 1 + PATTERNS.md §config.py 'Threshold value' note)." Implemented the correct value (50.0) as specified in the plan's action block.

### Schema column count 38 vs 36 in success criteria

The plan's success criteria stated "36 columns (was 26; +10)". The actual Phase 6 base count was 28 columns (not 26 as estimated in the plan summary). The 10 Phase 7 cols were added correctly per all structural checks — 28 + 10 = 38. All verification assertions pass (presence + nullability checks, not a raw column-count assertion). Documented as a plan estimation discrepancy, not a code defect.

## Known Stubs

The three test files (test_sizing.py, test_journal.py, test_pipeline_journal.py) consist entirely of `pytest.skip()` skeletons — this is **intentional and by design**. The plan explicitly created them as skeleton stubs for Wave 1 plans (07-02, 07-03, 07-04) to populate. These skeletons do not block the plan's goal (seam wiring). No data-flow stubs exist in config.py or persistence.py — all new fields carry concrete defaults and the schema extension is fully typed.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what the plan's threat model covers. The `data/journal.sqlite` allowlist in .gitignore implements T-07-01 mitigation (paper-trade data only, no PII/keys). The RankingSnapshotSchema extension implements T-07-02 mitigation (strict=True, coerce=False, pandera enum constraints).

## Self-Check: PASSED
