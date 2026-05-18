---
phase: 07-sizing-finalization-paper-trade-journal
plan: "03"
subsystem: persistence, journal-sqlite, pandera-schema
tags: [phase-7, persistence, sqlite, picks-table, immutability-trigger, idempotent-append, pandera-schema, tdd]
dependency_graph:
  requires:
    - 07-01-SUMMARY.md (Settings.JOURNAL_DB_PATH, RankingSnapshotSchema Phase 7 extension, test_journal.py skeletons)
  provides:
    - PicksSchema DataFrameModel (13-field strict validation contract)
    - _PICKS_DDL Final[str] (table + 2 indexes + immutability trigger in one executescript)
    - _journal_db_path() resolver
    - _ensure_picks_schema() idempotent setup
    - append_picks_rows() INSERT OR IGNORE write API
    - read_picks_for_date() SELECT read API
    - tests/test_journal.py 9 real bodies (was 9 skips)
  affects:
    - 07-04-PLAN.md (pipeline wiring calls append_picks_rows via _build_journal_rows_df)
    - 07-05-PLAN.md (cli.journal calls read_picks_for_date + append_picks_rows)
tech_stack:
  added: []
  patterns:
    - sqlite-executescript-single-call (Pitfall 1 mitigation — table+indexes+trigger in one executescript)
    - insert-or-ignore-idempotent-append (UNIQUE(ticker, snapshot_date) as natural key)
    - pandera-strict-schema-at-write-boundary (PicksSchema validates before INSERT)
    - tdd-red-green-commit (failing tests committed before implementation)
key_files:
  created: []
  modified:
    - src/screener/persistence.py (PicksSchema + _PICKS_DDL + _journal_db_path + _ensure_picks_schema + append_picks_rows + read_picks_for_date)
    - tests/test_journal.py (9 real bodies replacing pytest.skip skeletons)
decisions:
  - "pivot_distance_atr_breakout nullable=True in PicksSchema — leader_hold picks have no breakout pivot; aligns with RankingSnapshotSchema nullable=True for this column"
  - "All DDL in single executescript call — ensures table + indexes + trigger are always created atomically; DROP + re-create guarantees trigger survives (Pitfall 1 per RESEARCH)"
  - "PicksSchema.shares typed as Series[int] not Series[pd.Int64Dtype] — SQLite INTEGER maps cleanly to Python int; nullable=False enforced"
  - "read_picks_for_date uses pd.read_sql_query with positional params=(snapshot_date,) — mirrors read_insider_cluster_buy idiom"
metrics:
  duration: 5m
  completed_date: "2026-05-18"
  tasks: 2
  files: 2
---

# Phase 07 Plan 03: Journal Persistence Layer Summary

SQLite journal persistence layer for the paper-trade picks table: PicksSchema pandera contract + _PICKS_DDL (table + 2 indexes + immutability trigger in one executescript) + append_picks_rows INSERT OR IGNORE API + read_picks_for_date SELECT API. 9 of 10 test_journal.py bodies pass; test_journal_cli_idempotent deferred to Plan 07-05.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| RED | Add failing test bodies for journal persistence | ff17059 | tests/test_journal.py |
| 1 | Add PicksSchema + _PICKS_DDL + _journal_db_path + _ensure_picks_schema | 2549ffa | src/screener/persistence.py |
| 2 | Add append_picks_rows + read_picks_for_date | 5456241 | src/screener/persistence.py |

## Verification Results

All acceptance criteria passed:

- `9 passed, 1 skipped` — tests/test_journal.py (test_journal_cli_idempotent deferred)
- `2 passed` — tests/test_backtest_no_lookahead.py (FND-04 mutation gate green)
- `4 passed` — tests/test_architecture.py (D-23 ALLOWED dict unchanged)
- `1 passed` — tests/test_cli_smoke.py::test_subcommand_surface_locked (D-24 9-subcommand lock)
- `2 passed` — tests/test_insider_io.py (Phase 6 InsiderSchema no regression)
- PicksSchema: `13 PicksSchema columns` confirmed
- No `print()` calls in persistence.py
- All DDL grep checks: _PICKS_DDL (1), _journal_db_path (1), _ensure_picks_schema (1), PicksSchema (1), trigger (1), UNIQUE constraint (1), 2 indexes (1 each)

## Deviations from Plan

None — plan executed exactly as written.

The quoted type annotations `"Path | None"` on new functions follow the pre-existing pattern in persistence.py. The ruff UP037 warnings were pre-existing throughout the file and are out of scope for this plan (SCOPE BOUNDARY rule).

## TDD Gate Compliance

- RED gate: `test(07-03)` commit ff17059 — import error confirmed before implementation
- GREEN gate: `feat(07-03)` commits 2549ffa and 5456241 — 9 passing tests confirmed
- REFACTOR: no cleanup needed; implementation matches plan verbatim

## Known Stubs

None — all 9 implemented test bodies exercise real functionality with `tmp_path` SQLite databases. The single remaining skip (`test_journal_cli_idempotent`) is intentionally deferred to Plan 07-05 per plan spec.

## Threat Surface Scan

No new network endpoints or auth paths. New SQLite file access pattern (`data/journal.sqlite`) is covered by the plan's threat model:
- T-07-11 (tampering — decision columns): mitigated by immutability trigger (tested via test_immutability_trigger + test_schema_idempotent_recreates_trigger)
- T-07-12 (Pitfall 1 — DROP + re-create): mitigated by single executescript (tested via test_schema_idempotent_recreates_trigger)
- T-07-13 (double-insert): mitigated by UNIQUE + INSERT OR IGNORE (tested via test_idempotent_append)
- T-07-16 (path traversal): mitigated by PicksSchema regex `^\d{4}-\d{2}-\d{2}$` on snapshot_date

## Self-Check: PASSED
