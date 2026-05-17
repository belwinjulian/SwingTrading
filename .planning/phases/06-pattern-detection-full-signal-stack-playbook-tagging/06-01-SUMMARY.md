---
phase: 06-pattern-detection-full-signal-stack-playbook-tagging
plan: 01
subsystem: testing
tags: [phase-6, foundation, test-skeletons, pandera-schemas, settings, fixtures, gitignore, makefile]

# Dependency graph
requires:
  - phase: 02-data-foundation
    provides: persistence.py atomic-write primitive, validate_at_write/at_read helpers, _write_parquet_atomic, _assert_safe_ticker/_assert_safe_snapshot_date
  - phase: 04-trend-template-composite-skeleton-first-report
    provides: RankingSnapshotSchema, signals/composite.py DEFAULT_WEIGHTS + PHASE_4_ZEROED, publishers/snapshot.py + publishers/report.py
  - phase: 05-backtest-harness-no-lookahead-gate
    provides: FND-04 no-look-ahead gate; backtest/report.py per-playbook attribution stub
provides:
  - 3 new pandera schemas (FundamentalsSchema, InsiderSchema, PatternAuditSchema) at IO boundaries (D-05, D-12, D-13b, D-19)
  - RankingSnapshotSchema 11-column extension (playbook_tag, qullamaggie_score, minervini_score, leader_hold_score, pattern_diagnostics, breakout_strength, days_to_next_earnings, crossed_52w_high_within_60d, insider_cluster_buy, earnings_in_3d_warn, eps_knowable_from)
  - read_universe_latest() persistence helper (consumed by Plan 06-03 refresh_fundamentals)
  - 3 Phase 6 Settings path fields (FUNDAMENTALS_CACHE_DIR, INSIDER_CACHE_PATH, PATTERN_AUDIT_DIR)
  - 2 already-existing Settings keys (FINNHUB_API_KEY, EDGAR_IDENTITY) promoted to REQUIRED for Phase 6+ in .env.example
  - `make fundamentals` target -> refresh-fundamentals (no 10th subcommand)
  - 12 test skeletons (37 named pytest.skip stubs) locking the per-Plan verify map
  - 7 committed fixtures (~74KB) + scripts/generate_phase6_fixtures.py
  - test_signals_indicators_cannot_import_data (D-23 structural defense)
  - test_subcommand_surface_locked (D-24 hard byte-level lock)
  - publishers/report._add_publisher_columns emits safe defaults for the 11 new RankingSnapshotSchema columns (auto-fix for strict-schema upstream)
affects: [phase-6 Plan 06-02 patterns, Plan 06-03 data adapters, Plan 06-04 composite + playbook tagger, Plan 06-05 CLI wire-up]

# Tech tracking
tech-stack:
  added: []  # No new third-party deps — pandera/pyarrow/yfinance already in pyproject
  patterns:
    - "Pattern B (existing): pandera strict=True/coerce=False at every IO boundary"
    - "Pattern: getattr() Settings cross-wave fallback in _X_dir() helpers"
    - "Pattern: body-level pytest.skip with Wave/Plan citation (decoder-level discoverability)"
    - "Pattern: fixture loaders in conftest.py for committed Parquet/SQLite artifacts"

key-files:
  created:
    - tests/test_patterns_golden.py
    - tests/test_patterns_split.py
    - tests/test_breakout_strength.py
    - tests/test_qullamaggie.py
    - tests/test_canslim.py
    - tests/test_canslim_lag.py
    - tests/test_fundamentals_io.py
    - tests/test_insider_io.py
    - tests/test_insider_cluster_buy.py
    - tests/test_composite_full.py
    - tests/test_playbook_tagger.py
    - scripts/generate_phase6_fixtures.py
    - tests/fixtures/patterns/nvda_2023_vcp.parquet
    - tests/fixtures/patterns/aapl_2020_vcp.parquet
    - tests/fixtures/patterns/nvda_2024_split.parquet
    - tests/fixtures/patterns/nvda_2023_flag.parquet
    - tests/fixtures/fundamentals/sample_quarterly.parquet
    - tests/fixtures/form4_cluster.sqlite
    - tests/fixtures/form4_no_cluster.sqlite
    - data/fundamentals/.gitkeep
    - data/insider/.gitkeep
    - data/pattern_audit/.gitkeep
  modified:
    - src/screener/config.py
    - src/screener/persistence.py
    - src/screener/publishers/report.py
    - tests/conftest.py
    - tests/test_architecture.py
    - tests/test_cli_smoke.py
    - tests/test_persistence.py
    - tests/test_publishers_snapshot.py
    - tests/test_rs_snapshot.py
    - .env.example
    - .gitignore
    - Makefile

key-decisions:
  - "Auto-fix: extended publishers/report._add_publisher_columns to emit safe defaults for the 11 new RankingSnapshotSchema columns (Rule 3) — Plans 06-02/06-04 overwrite the placeholders upstream, but the strict schema would otherwise reject every existing snapshot until those plans land."
  - "Updated 3 test helpers (_make_ranking_snapshot_df in test_persistence.py, test_publishers_snapshot.py, test_rs_snapshot.py) with Phase 6 placeholder columns — necessary because strict=True snapshot schema cannot validate a frame missing required columns."
  - "Generator script falls back to deterministic synthetic OHLCV when yfinance is unavailable; Pitfall 5 mitigation. Real OHLCV was successfully fetched during this run."
  - "Added explicit test_subcommand_surface_locked (D-24) test even though help-listing test already covers the surface — explicit-named test is unmissable in PR review."
  - "Plan said remove `refresh-fundamentals` from PHASE_1_STUBS. Done — but the current refresh-fundamentals body is still a stub. The new `test_refresh_fundamentals_subcommand_no_longer_stub` test is itself a Wave 4 skip until Plan 06-05 fills the body."

patterns-established:
  - "Pattern: every Phase 6 plan owns one of the 12 test files; replacing pytest.skip(...) with the real assertion is the canonical Wave verification path."
  - "Pattern: Wave/Plan citation in every skip reason — `pytest -v` output documents the deferred work without needing a separate tracker."
  - "Pattern: fixture generator scripts live in scripts/, run ONCE, output committed; CI never re-fetches."
  - "Pattern: _add_publisher_columns adds Phase 6 placeholder columns only when absent (`if 'col' not in out.columns`) so downstream plans populate real values upstream without colliding."

requirements-completed:
  - DAT-05  # 45-day lag persistence read-time gate seam (read_fundamentals lands in Plan 06-03; structural lock + test skel here)
  - PAT-06  # golden-file pattern test fixtures + skeletons (real assertions land in Plan 06-02)
  - SIG-02  # Qullamaggie Setup A test skel (Plan 06-04 fills body)
  - SIG-03  # CANSLIM C+L+M overlay test skel (Plan 06-04 fills body)
  - CMP-01  # composite full activation test skel (Plan 06-04 fills body)
  - CMP-02  # playbook tagger test skel (Plan 06-04 fills body)
  - CMP-03  # tie-breaker test skel (Plan 06-04 fills body)
  - CMP-04  # co-located tagger seam (architecture lock in this plan)
  - CMP-05  # per-pick component breakdown — schema columns shipped (eps_knowable_from etc.)
  - CAT-01  # earnings calendar test skel (Plan 06-03 fills body)
  - CAT-04  # EDGAR identity required test skel (Plan 06-05 fills body)

# Metrics
duration: 51min
completed: 2026-05-17
---

# Phase 6 Plan 01: Pattern Detection Foundation Summary

**3 new pandera schemas + RankingSnapshotSchema 11-column extension + 12 named test skeletons + 7 committed fixtures + D-23/D-24 structural locks — every subsequent Wave 1-4 plan has an automated verify target with zero bootstrap drag.**

## Performance

- **Duration:** 51 min
- **Started:** 2026-05-17T08:13:00Z (approx)
- **Completed:** 2026-05-17T09:04:00Z (approx)
- **Tasks:** 3
- **Files modified:** 12 source/config/test files + 12 new test artifacts (incl. 7 fixtures, 3 .gitkeep, generator script)

## Accomplishments

- 3 new pandera schemas (FundamentalsSchema, InsiderSchema, PatternAuditSchema) follow the existing Phase 2 strict=True/coerce=False contract; importable as `from screener.persistence import ...`.
- RankingSnapshotSchema gained exactly 11 new columns per D-12/D-15/D-19 — including the W11 ergonomics field `eps_knowable_from` (ISO YYYY-MM-DD string) so the report can render an honest "pending until DATE" line.
- `persistence.read_universe_latest()` ships as a list[str] helper backed by `_universe_dir()` lexicographic-glob; Plan 06-03 `refresh_fundamentals(today)` consumes it when its `tickers` arg is `None`.
- 12 test skeletons land with 37 named pytest.skip stubs; each citation names the Wave + Plan + decision ID it validates, so `pytest -v` output documents the entire deferred test plan.
- 7 fixtures committed (~74 KB total): NVDA 2023 base / 2024 split / 2023 flag, AAPL 2020 VCP (real yfinance OHLCV), synthetic Form 4 SQLite cluster/no-cluster pair, FundamentalsSchema-compliant 4-row sample.
- D-23 + D-24 structural locks made explicit via `test_signals_indicators_cannot_import_data` and `test_subcommand_surface_locked` — both pass on the current codebase and stay green through Phase 6.
- `make fundamentals` resolves to `refresh-fundamentals` (no 10th subcommand added, D-24 lock preserved).
- `.env.example` documents `FINNHUB_API_KEY` and `EDGAR_IDENTITY` as REQUIRED for Phase 6+.
- `.gitignore` excludes the 3 new data subdirs with `.gitkeep` carve-outs (mirrors Phase 2 snapshots pattern).

## Task Commits

Each task was committed atomically:

1. **Task 1: Settings + .env.example + .gitignore + Makefile fundamentals target** — `f1d872f` (feat)
2. **Task 2: Pandera schemas (3 new + RankingSnapshotSchema 11-column extension) + read_universe_latest helper + Phase 6 _dir helpers** — `0719beb` (feat)
3. **Task 3: 12 test skeletons + 7 fixtures + architecture/CLI-smoke extensions** — `32e2ee8` (test)

## Files Created/Modified

### Source / config

- `src/screener/config.py` — added 3 Phase 6 path fields (FUNDAMENTALS_CACHE_DIR, INSIDER_CACHE_PATH, PATTERN_AUDIT_DIR)
- `src/screener/persistence.py` — 3 new schemas (FundamentalsSchema, InsiderSchema, PatternAuditSchema) + 11-column RankingSnapshotSchema extension + 3 dir helpers (`_fundamentals_dir`, `_insider_db_path`, `_pattern_audit_dir`) + `read_universe_latest()`
- `src/screener/publishers/report.py` — `_add_publisher_columns` emits Phase 6 placeholder columns when missing (Rule 3 auto-fix for strict-schema)

### Tests

- `tests/test_patterns_golden.py` — 6 D-02 golden tests (Wave 1 / Plan 06-02)
- `tests/test_patterns_split.py` — split-pivot continuity (Wave 1 / 06-02)
- `tests/test_breakout_strength.py` — D-06 + Pitfall 10 (Wave 1 / 06-02)
- `tests/test_canslim_lag.py` — D-13b 30d-then-16d (Wave 1 / 06-03)
- `tests/test_fundamentals_io.py` — Finnhub + yfinance mocks (Wave 1 / 06-03)
- `tests/test_insider_io.py` — edgartools + sqlite (Wave 1 / 06-03)
- `tests/test_insider_cluster_buy.py` — Pitfall 7 fallback (Wave 1 / 06-03)
- `tests/test_qullamaggie.py` — SIG-02 Setup A (Wave 2 / 06-04)
- `tests/test_canslim.py` — SIG-03 + D-18 dedup (Wave 2 / 06-04)
- `tests/test_composite_full.py` — PHASE_4_ZEROED + loop sanctity (06-04)
- `tests/test_playbook_tagger.py` — D-14 tie-breaker + D-15 (06-04)
- `tests/conftest.py` — 7 fixture loaders for the committed Parquet/SQLite artifacts
- `tests/test_architecture.py` — `test_signals_indicators_cannot_import_data` (D-23)
- `tests/test_cli_smoke.py` — `test_subcommand_surface_locked` (D-24) + 2 Wave 4 stubs + `refresh-fundamentals` removed from PHASE_1_STUBS
- `tests/test_persistence.py` — extended `_make_ranking_snapshot_df` helper with Phase 6 columns
- `tests/test_publishers_snapshot.py` — extended `_make_ranking_snapshot_df` helper with Phase 6 columns
- `tests/test_rs_snapshot.py` — extended inline snapshot frame with Phase 6 columns

### Fixtures

- `tests/fixtures/patterns/nvda_2023_vcp.parquet` (71 rows / 8 KB)
- `tests/fixtures/patterns/aapl_2020_vcp.parquet` (146 rows / 12 KB)
- `tests/fixtures/patterns/nvda_2024_split.parquet` (107 rows / 10 KB)
- `tests/fixtures/patterns/nvda_2023_flag.parquet` (24 rows / 6 KB)
- `tests/fixtures/fundamentals/sample_quarterly.parquet` (4 rows / 7 KB)
- `tests/fixtures/form4_cluster.sqlite` (4 rows / 16 KB)
- `tests/fixtures/form4_no_cluster.sqlite` (1 row / 16 KB)

### Generator / config / repo

- `scripts/generate_phase6_fixtures.py` — one-shot fixture generator (yfinance pull + synthetic Form 4)
- `.env.example` — promoted FINNHUB_API_KEY + EDGAR_IDENTITY to REQUIRED for Phase 6+ + optional path overrides
- `.gitignore` — added 3 Phase 6 data subdirs with `.gitkeep` carve-outs
- `Makefile` — added `fundamentals` target (D-09) + .PHONY entry
- `data/fundamentals/.gitkeep`, `data/insider/.gitkeep`, `data/pattern_audit/.gitkeep` — directory anchors

## Decisions Made

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | `_add_publisher_columns` emits Phase 6 placeholder columns when missing | Auto-fix Rule 3: strict-schema RankingSnapshotSchema rejects existing frames missing the 11 new columns. Placeholders are overridden upstream by Plans 06-02 (real diagnostics) and 06-04 (real playbook_tag); the `if 'col' not in out.columns` guard means no collision. |
| 2 | Updated 3 test helpers with Phase 6 placeholder columns | Same root cause as #1 — schema-test fixtures bypass `_add_publisher_columns` and build the DataFrame directly. |
| 3 | Generator script has synthetic fallback when yfinance is unavailable | Pitfall 5 mitigation; real OHLCV fetched successfully on this run, but downstream contributors can re-run offline without network. |
| 4 | Added explicit `test_subcommand_surface_locked` (D-24) even though help-listing test exists | Explicit-named test is unmissable in PR review and matches Plan 01 verification. |
| 5 | Removed `refresh-fundamentals` from PHASE_1_STUBS now (Wave 0) even though the body isn't filled until Plan 06-05 | Plan instructed this; the deferred test `test_refresh_fundamentals_subcommand_no_longer_stub` is a Wave 4 skip that Plan 06-05 will flip to active. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RankingSnapshotSchema strict=True rejects existing snapshot frames**

- **Found during:** Task 2 (Pandera schema extension)
- **Issue:** Adding 11 new non-nullable columns to a strict=True schema immediately broke 2 existing tests (`test_ranking_snapshot_schema_accepts_valid_frame`, `test_snapshot_written_atomic`) because their snapshot-helper frames lacked the new columns.
- **Fix:** Extended (a) `src/screener/publishers/report.py::_add_publisher_columns` with `if 'col' not in out.columns` guards so the production write path supplies safe defaults (Plan 06-04 will overwrite real values upstream); (b) the 3 test helpers (`_make_ranking_snapshot_df` in `test_persistence.py`, `test_publishers_snapshot.py`, and the inline frame in `test_rs_snapshot.py`) with Phase 6 placeholder columns.
- **Files modified:** `src/screener/publishers/report.py`, `tests/test_persistence.py`, `tests/test_publishers_snapshot.py`, `tests/test_rs_snapshot.py`
- **Verification:** Full suite passes (151 passed, 41 skipped). The two originally-broken tests pass with the placeholder frames. The `if col not in out.columns` guards mean Plan 06-02/06-04 can write real values upstream without collision.
- **Committed in:** `0719beb` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The placeholder-default extension preserves backwards compatibility with all Phase 4-5 tests while letting the new strict schema reject malformed Phase 6 frames at write time. No scope creep — the `if col not in out.columns` guard cleanly hands off to the real Phase 6 plans.

## Issues Encountered

- `uv run python` did NOT pick up the `screener` package without `PYTHONPATH=src` set — the package is configured under `tool.hatch.build.targets.wheel` but not installed in editable mode in the worktree's `.venv`. Verification commands prepended `PYTHONPATH=src` to satisfy the `screener.config` import. Plan-level verify commands work because pytest reads `tool.pytest.ini_options.pythonpath = ["src"]`. No fix needed; documented here as an operations note for future plans.

## User Setup Required

None - no external service configuration required. Phase 6+ requires `FINNHUB_API_KEY` and `EDGAR_IDENTITY` in `.env` for `make fundamentals` to run, but this is documented in `.env.example` and enforced lazily — only Plan 06-05's `_ensure_edgar_identity` startup hook (CAT-04) will fail loud if missing.

## Next Phase Readiness

- **Plan 06-02 (Wave 1, patterns):** consumes `nvda_2023_vcp_panel`, `aapl_2020_vcp_panel`, `nvda_2024_split_panel`, `nvda_2023_flag_panel` conftest fixtures; targets `test_patterns_golden.py`, `test_patterns_split.py`, `test_breakout_strength.py`. Will create `src/screener/indicators/patterns.py` with VCP/flag detectors + Final-locked thresholds.
- **Plan 06-03 (Wave 1, data adapters):** consumes `sample_quarterly_fundamentals`, `form4_cluster_db_path`, `form4_no_cluster_db_path` fixtures + `read_universe_latest()` helper; targets `test_canslim_lag.py`, `test_fundamentals_io.py`, `test_insider_io.py`, `test_insider_cluster_buy.py`. Will create `src/screener/data/fundamentals.py`, `src/screener/data/insider.py`, and `persistence.{write_fundamentals_atomic,read_fundamentals,write_pattern_audit_atomic,read_insider_cluster_buy}`.
- **Plan 06-04 (Wave 2, signals + composite + tagger):** depends on 06-02 and 06-03; targets `test_qullamaggie.py`, `test_canslim.py`, `test_composite_full.py`, `test_playbook_tagger.py`. Will create `signals/qullamaggie.py`, `signals/canslim.py`, extend `signals/composite.py` (shrink `PHASE_4_ZEROED` to `frozenset()`, add `tag_playbook`).
- **Plan 06-05 (Wave 4, CLI wire-up):** flips `test_refresh_fundamentals_subcommand_no_longer_stub` and `test_edgar_identity_required` from skip to active.

**FND-04 no-look-ahead gate confirmed green** — `tests/test_backtest_no_lookahead.py` runs in 4.09 s with 2/2 passing on the new schema.

## Per-Task Verification Map Update for 06-VALIDATION.md

- `06-01-0-1` (Task 1 — Settings, env, gitignore, Makefile): VERIFIED via `make -n fundamentals | grep refresh-fundamentals` + `Settings()` instantiation + 3 grep checks on `.env.example` / `.gitignore`.
- `06-01-0-2` (Task 2 — schemas + helper): VERIFIED via direct import + `RankingSnapshotSchema.to_schema().columns` enumeration + `validate_at_write(FundamentalsSchema, bad_row)` rejection + `read_universe_latest` callable check.
- `06-01-0-3` (Task 3 — skeletons, fixtures, locks): VERIFIED via `pytest tests/test_patterns_*.py ...` showing 37 skipped + `ls tests/fixtures/...` returning all 7 paths + `pytest tests/test_architecture.py::test_signals_indicators_cannot_import_data tests/test_cli_smoke.py::test_subcommand_surface_locked` returning 2/2 passed.

## Self-Check: PASSED

All claimed artifacts verified on disk + every claimed commit present in `git log`:

- ✓ `src/screener/config.py`, `src/screener/persistence.py`, `src/screener/publishers/report.py` modified
- ✓ `.env.example`, `.gitignore`, `Makefile` modified
- ✓ 12 new test files + 7 fixtures + 3 .gitkeep + generator script created
- ✓ Commits present: `f1d872f` (Task 1), `0719beb` (Task 2), `32e2ee8` (Task 3)
- ✓ Full suite: 151 passed, 41 skipped (was 149 passed / 2 skipped — +2 passing tests, +39 skipped stubs, no regressions)
- ✓ FND-04 no-look-ahead gate green (2/2 passed in 4.09 s)
- ✓ D-23 + D-24 lock tests pass

---
*Phase: 06-pattern-detection-full-signal-stack-playbook-tagging*
*Completed: 2026-05-17*
