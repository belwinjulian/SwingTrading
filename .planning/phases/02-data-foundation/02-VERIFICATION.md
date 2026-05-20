---
phase: 02-data-foundation
verified: 2026-05-03T12:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 6/7
  gaps_closed:
    - "Corporate-action splits stored alongside OHLCV (splits.parquet) for ALL fetch paths including Stooq fallback — fixed in commit afe55fb"
  gaps_remaining: []
  regressions: []
---

# Phase 2: Data Foundation Verification Report

**Phase Goal:** All downstream stages can rely on a fresh, schema-validated, survivorship-aware OHLCV panel — yfinance failures fail loud, weekly universe snapshots accumulate from day one, and corporate-action splits are stored alongside prices for honest pattern detection in Phase 6.
**Verified:** 2026-05-03
**Status:** passed
**Re-verification:** Yes — after gap closure (DAT-08 Stooq fallback missing `write_splits_atomic`)

---

## Re-verification Summary

The original verification (2026-05-03, initial) found one BLOCKER gap: the Stooq circuit-breaker fallback path in `run_with_breaker` called `write_ohlcv_atomic` but omitted `fetch_splits` and `write_splits_atomic`. Commit `afe55fb` fixed this by adding both calls to the Stooq else-branch (ohlcv.py lines 280-281). This re-verification confirms the fix is present and all 7 must-have truths are now VERIFIED.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Pandera schemas (OhlcvPanelSchema, UniverseSchema, SplitsSchema) enforce strict types, multiindex order, GICS sector allowlist at write/read boundaries | VERIFIED | persistence.py lines 76-135: all three DataFrameModel classes with strict=True, coerce=False, multiindex_strict=True; 9 tests pass in test_persistence.py |
| 2 | Atomic writes via tempfile.NamedTemporaryFile(dir=target.parent) + os.replace — crash mid-write leaves no partial Parquet at target path | VERIFIED | persistence.py lines 154-176: NamedTemporaryFile with delete=False, os.replace, unlink on failure; test_atomic_write_crash_no_partial passes |
| 3 | Weekly universe snapshot written to data/universe/<iso-monday>.parquet, idempotent, with --force override | VERIFIED | universe.py lines 244-275: iso_week_monday() keying, idempotent skip when file exists, refresh_universe() with force parameter; test_snapshot_idempotent_same_week and test_snapshot_force_overwrites pass |
| 4 | yfinance failures fail loud via tenacity (stop_after_attempt(5), wait_exponential(multiplier=1, min=2, max=60), reraise=True) on all four D-08 invariants (empty, stale, non-monotonic, null close) | VERIFIED | ohlcv.py lines 54-104: @retry decorator with verbatim parameters; all 4 invariants present; test_fetch_empty_raises_after_retries (5 retries confirmed), test_fetch_stale_fails, test_fetch_non_monotonic_fails, test_fetch_null_close_fails all pass |
| 5 | Stooq circuit-breaker fires when yfinance success rate < 0.80 in first 50 probes and routes remaining tickers through Stooq | VERIFIED | ohlcv.py lines 220-286: STOOQ_BREAKER_PROBE_N=50, STOOQ_BREAKER_THRESHOLD=0.80; test_circuit_breaker_trip passes (49/50 fail -> breaker trips) |
| 6 | 95% health gate enforced at CLI: (yf_ok + stooq_ok) / n_universe >= UNIVERSE_HEALTH_THRESHOLD (0.95); exits non-zero with health_check_failed below threshold | VERIFIED | cli.py lines 133-155: gate computation, typer.Exit(code=1) on fail; test_health_gate_below_95_fails_run and test_health_gate_above_95_passes_run both pass |
| 7 | Corporate-action splits stored alongside OHLCV (splits.parquet) for ALL fetch paths including Stooq fallback | VERIFIED | ohlcv.py lines 277-281 (Stooq else-branch): stooq_module.fetch_ohlcv + write_ohlcv_atomic + fetch_splits(ticker) + write_splits_atomic(ticker, splits_df) all present. Confirmed by direct code read. Both yf path (lines ~249-250) and Stooq fallback path now call fetch_splits + write_splits_atomic. |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/screener/persistence.py` | Pandera schemas + atomic-write + readers/writers | VERIFIED | 332 lines; OhlcvPanelSchema, UniverseSchema, SplitsSchema, StaleOrEmptyError, _write_parquet_atomic, all writer/reader functions present |
| `src/screener/config.py` | Settings with 8 D-20 fields | VERIFIED | All 8 fields present with correct defaults: OHLCV_CACHE_DIR=Path("data/ohlcv"), UNIVERSE_HEALTH_THRESHOLD=0.95, STOOQ_BREAKER_PROBE_N=50, STOOQ_BREAKER_THRESHOLD=0.80 |
| `src/screener/data/universe.py` | iShares IWB fetcher + ALLOWLIST + weekly snapshot | VERIFIED | ALLOWLIST={"BRKB":"BRK-B","BFB":"BF-B","BFA":"BF-A"} literal present; ISHARES_SKIPROWS=9, ISHARES_ENCODING="utf-8-sig"; tenacity wrapped fetch; refresh_universe() with idempotent weekly key |
| `src/screener/data/ohlcv.py` | yfinance fetch + tenacity + 4-invariant gate + sentinel + breaker + splits on all paths | VERIFIED | Core fetch, sentinel, breaker correct; Stooq branch now includes fetch_splits + write_splits_atomic (fix in commit afe55fb lines 280-281) |
| `src/screener/data/stooq.py` | pandas-datareader Stooq adapter + ascending sort + lowercase + D-08 gate | VERIFIED | pdr.DataReader, sort_index(ascending=True), rename(columns=str.lower), all 4 invariants present |
| `src/screener/cli.py` | refresh-universe + refresh-ohlcv real bodies + 95% gate | VERIFIED | refresh_universe_impl call, run_with_breaker, health gate logic, typer.Exit(code=1) on fail; 9 subcommands intact |
| `tests/test_persistence.py` | 9 named tests | VERIFIED | All 9 tests present and passing |
| `tests/test_data_universe.py` | 8 named tests | VERIFIED | All 8 tests present and passing |
| `tests/test_data_ohlcv.py` | 12 tests (10 active + 2 skipped) | VERIFIED | 12 test functions present; 10 pass, 2 skipped with @pytest.mark.skip and clear rationale |
| `tests/test_data_stooq.py` | 3 named tests | VERIFIED | All 3 tests present and passing |
| `tests/test_cli_smoke.py` | 6 tests (expanded from 2) | VERIFIED | 6 test functions; all 6 pass; D14_SUBCOMMANDS unchanged at 9 |
| `tests/conftest.py` | 10 synthetic fixtures | VERIFIED | All 10 fixtures confirmed: synthetic_ohlcv_valid_df, _empty_df, _stale_df, _null_close_df, _non_monotonic_df, _ishares_csv_bytes, _undersized_bytes, _bad_sector_bytes, split_mismatch_pair, stooq_descending_df |
| `README.md` | Data layer section | VERIFIED | ## Data layer at line 37; per-ticker layout, backfill docs, Stooq fallback, survivorship disclosure, atomic-write note |
| `.gitignore` | D-19 carve-out | VERIFIED | /data/* with carve-outs; prices.parquet ignored; splits.parquet and universe/*.parquet committed (git check-ignore confirmed) |
| `data/universe/.gitkeep` | Zero-byte anchor | VERIFIED | File exists |
| `data/ohlcv/.gitkeep` | Zero-byte anchor | VERIFIED | File exists |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/screener/data/ohlcv.py` | `src/screener/data/stooq.py` | `from screener.data import stooq as stooq_module` | WIRED | ohlcv.py line 35; stooq_module.fetch_ohlcv called in breaker else-branch |
| `src/screener/data/ohlcv.py` | `src/screener/persistence.py` | `write_ohlcv_atomic, write_splits_atomic, StaleOrEmptyError, make_empty_splits` | WIRED | Both yf branch and Stooq branch now call write_ohlcv_atomic + fetch_splits + write_splits_atomic (fix confirmed at ohlcv.py lines 279-281) |
| `src/screener/data/universe.py` | `src/screener/persistence.py` | `from screener.persistence import write_universe_atomic, GICS_SECTORS, UniverseSchema` | WIRED | universe.py lines 34-38 |
| `src/screener/cli.py` | `src/screener/data/universe.py` | `from screener.data.universe import refresh_universe as refresh_universe_impl` | WIRED | cli.py line 30; called in refresh_universe() command body |
| `src/screener/cli.py` | `src/screener/data/ohlcv.py` | `from screener.data.ohlcv import run_with_breaker` | WIRED | cli.py line 26; called in refresh_ohlcv() body with tickers + today |
| `src/screener/cli.py` | `src/screener/persistence.py` | `from screener.persistence import read_universe` | WIRED | cli.py line 33; read_universe called to obtain ticker list |

---

### Data-Flow Trace (Level 4)

Not applicable — data layer does not render dynamic data to UI. The data flows are write-side (fetch → validate → write Parquet) rather than render-side. The relevant data-flow verification is that written artifacts are schema-validated (confirmed) and that the CLI gates on fetch success rates (confirmed).

---

### Behavioral Spot-Checks

| Behavior | Method | Result | Status |
|----------|--------|--------|--------|
| 39 tests pass (0 failures, 2 skips) | `uv run pytest tests/ -m "not slow and not integration" -q` | 39 passed, 2 skipped in 81.50s | PASS |
| 9 persistence schema tests pass | `uv run pytest tests/test_persistence.py -q` | 9 passed | PASS |
| Stooq 3 tests pass | `uv run pytest tests/test_data_stooq.py -q` | 3 passed | PASS |
| CLI smoke 6 tests pass | `uv run pytest tests/test_cli_smoke.py -q` | 6 passed | PASS |
| 95% health gate exits non-zero below threshold | test_health_gate_below_95_fails_run | exit_code != 0 + health_check_failed event | PASS |
| 95% health gate exits 0 above threshold | test_health_gate_above_95_passes_run | exit_code == 0 + health_check_passed event | PASS |
| Stooq fallback branch writes splits.parquet | Direct code read ohlcv.py lines 280-281 | fetch_splits + write_splits_atomic present in else-branch | PASS |
| .gitignore carve-out correct | `git check-ignore` boundary checks | prices ignored; splits+universe committed | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DAT-01 | 02-03 | User can refresh Russell 1000 universe; iShares IWB CSV fetch | SATISFIED | universe.py: fetch_ishares_iwb_csv + parse + sanity_check + refresh_universe; 8 tests pass |
| DAT-02 | 02-03 | Weekly snapshot written to data/universe/YYYY-MM-DD.parquet for point-in-time membership | SATISFIED | refresh_universe() with iso_week_monday() keying; idempotency tested |
| DAT-03 | 02-01, 02-04 | OHLCV via yfinance >= 1.3.0 with Stooq fallback, cached to per-ticker Parquet, incrementally appended | SATISFIED | ohlcv.py fetch + append_incremental + run_with_breaker; stooq.py adapter; all invariant tests pass |
| DAT-06 | 02-03, 02-04 | requests-cache + tenacity retries; rate-limit failures trigger backoff, not silent zero-row results | SATISFIED | universe.py: CachedSession with 1h iShares expiry; ohlcv.py: @retry(stop_after_attempt(5), wait_exponential); test_tenacity_backoff_on_429 passes |
| DAT-07 | 02-05 | 95% universe-coverage health check; fail loud if successful_fetches < 95% universe_size | SATISFIED | cli.py health gate; test_health_gate_below_95_fails_run + test_health_gate_above_95_passes_run pass |
| DAT-08 | 02-01, 02-04 | Corporate-action splits stored alongside OHLCV (splits.parquet) | SATISFIED | persistence.py: write_splits_atomic + SplitsSchema + make_empty_splits correct. ohlcv.py yf path writes splits (lines ~249-250). Stooq fallback path now also writes splits (lines 280-281, commit afe55fb). Both fetch paths complete. |
| DAT-09 | 02-01 | Pandera schemas enforced at data/indicators and composite/publishers boundaries | SATISFIED | persistence.py: OhlcvPanelSchema, UniverseSchema, SplitsSchema; validate_at_write (eager) + validate_at_read (lazy); all 9 schema tests pass |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/screener/data/universe.py` | 133 | `assert session.verify is True` — will be silently skipped under Python -O (optimized) | WARNING | Running `python -O screener/cli.py` disables this safety check. The production entry point via typer is invoked as a normal script and is unlikely to be run with -O, reducing blast radius. Replace with an explicit `if not session.verify: raise RuntimeError(...)` for defense-in-depth. Not a blocker for Phase 2 goal. |

The DAT-08 BLOCKER (Stooq branch missing `write_splits_atomic`) has been resolved. No remaining blockers.

---

### Human Verification Required

None — all automated checks pass and no items require human observation.

---

### Gaps Summary

No gaps. All 7 must-have truths verified. The one previously identified BLOCKER (DAT-08: Stooq fallback path did not write splits.parquet) was resolved in commit `afe55fb`. The Stooq else-branch in `run_with_breaker` (ohlcv.py lines 277-286) now calls `stooq_module.fetch_ohlcv`, `write_ohlcv_atomic`, `fetch_splits(ticker)`, and `write_splits_atomic(ticker, splits_df)` — matching the pattern of the yf-success branch.

The remaining WARNING (assert vs raise in universe.py) is informational and does not block the Phase 2 goal.

---

_Verified: 2026-05-03_
_Verifier: Claude (gsd-verifier)_
