---
phase: 02-data-foundation
plan: "04"
subsystem: data
tags: [ohlcv, yfinance, stooq, circuit-breaker, tenacity, sentinel-refetch, splits]
dependency_graph:
  requires: ["02-01", "02-02", "02-03"]
  provides: [ohlcv_fetch, stooq_fallback, splits_ledger, circuit_breaker]
  affects: ["02-05"]
tech_stack:
  added: [yfinance>=1.3.0, pandas-datareader>=0.10, tenacity, structlog]
  patterns: [tenacity-retry-decorator, sentinel-bar-refetch, circuit-breaker-probe]
key_files:
  created:
    - src/screener/data/stooq.py
    - src/screener/data/ohlcv.py
    - tests/test_data_stooq.py
    - tests/test_data_ohlcv.py
  modified:
    - src/screener/data/__init__.py
    - src/screener/data/universe.py
decisions:
  - "Mock append_incremental (not yf.download) in circuit-breaker test to bypass tenacity backoff; otherwise 49 failures * 4 retries * 8s = ~1570s wall time"
  - "before_sleep_log requires stdlib logging.Logger, not structlog bound-logger; use logging.getLogger(__name__) + logging.WARNING in both ohlcv.py and universe.py"
  - "Sentinel-bar test builds a stale cache (last bar 5 BD before REF_DATE) so append_incremental does not hit the early-return gate (last_cached_date >= today - 1d)"
metrics:
  duration: 15min
  completed: "2026-05-03"
  tasks: 4
  files: 6
---

# Phase 2 Plan 04: OHLCV Cache + Stooq Circuit-Breaker Summary

**One-liner:** yfinance fetch wrapped in tenacity-5-retry with four D-08 invariants, sentinel-bar refetch (rtol=0.005), circuit-breaker probe (N=50, threshold=0.80) routing to Stooq fallback, and splits ledger via Ticker.actions.

## Public Symbols Exposed

### src/screener/data/stooq.py

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `fetch_ohlcv` | `(ticker, start, today) -> pd.DataFrame` | pandas-datareader Stooq adapter. Sorts ascending, lowercases columns, applies D-08 four-invariant gate. Raises `StaleOrEmptyError` on any violation. No tenacity (hard-fail on trip). |

### src/screener/data/ohlcv.py

| Symbol | Signature | Description |
|--------|-----------|-------------|
| `fetch_ohlcv` | `(ticker, start, today) -> pd.DataFrame` | yfinance fetch with tenacity + D-08 invariants. Returns lowercase columns + DatetimeIndex named 'date'. |
| `fetch_ohlcv_with_pacing` | `(ticker, start, today) -> pd.DataFrame` | Wraps `fetch_ohlcv` with inter-ticker random sleep. |
| `append_incremental` | `(ticker, today) -> (df, bool)` | Cache read + incremental fetch + sentinel check + atomic write. Returns `(df, full_refetched)`. |
| `fetch_splits` | `(ticker) -> pd.DataFrame` | `yf.Ticker.actions` -> SplitsSchema shape. Returns `make_empty_splits()` on empty. |
| `run_with_breaker` | `(tickers, today) -> (yf_ok, stooq_ok, failed)` | Circuit-breaker orchestration. CLI uses counters to compute the 95% health gate. |

### src/screener/data/__init__.py

Re-exports all of the above plus existing universe symbols (`fetch_ishares_iwb_csv`, `refresh_universe`, `normalize_ticker`, etc.).

## Tenacity Parameters (D-10 verbatim)

```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
```

Per-ticker retry budget: max 2+4+8+16+32 = 62 seconds (five attempts with exponential backoff capped at 60s). `reraise=True` ensures callers receive `StaleOrEmptyError`, not tenacity's `RetryError`.

## D-08 Four-Invariant Gate

Applied inside `fetch_ohlcv` (yfinance path) and `stooq.fetch_ohlcv` (Stooq path) after normalization to lowercase columns:

| # | Invariant | Error message pattern |
|---|-----------|----------------------|
| 1 | DataFrame not None and non-empty | `"yf returned empty for {ticker}"` |
| 2 | `df.index[-1].date() >= today - 4 BD` | `"stale: last bar {last}, today {today}"` |
| 3 | `df.index.is_monotonic_increasing` | `"non-monotonic index"` |
| 4 | `df["close"].isna().any() == False` | `"has null close"` |

## Sentinel-Bar Refetch (D-07)

`append_incremental` re-fetches from `last_cached_date` (not `last_cached_date + 1`) so the response includes the sentinel bar. Compares sentinel close against cached close with `rtol=0.005` (0.5% tolerance). Catches ~50% split adjustments while tolerating dividend-drift.

On mismatch: emits `sentinel_mismatch` structured warning and triggers full backfill from `OHLCV_BACKFILL_START` (default: `"2005-01-01"`).

## Circuit-Breaker (D-12)

`run_with_breaker` probes the first `STOOQ_BREAKER_PROBE_N` (default: 50) tickers via yfinance. If `yf_ok / 50 < STOOQ_BREAKER_THRESHOLD` (default: 0.80), sets `breaker_tripped = True`, emits `breaker_tripped` structured event, and routes all remaining tickers through `screener.data.stooq.fetch_ohlcv`.

Returns `(yf_ok, stooq_ok, failed)`. The CLI (Plan 02-05) computes `(yf_ok + stooq_ok) / n_universe >= 0.95` and decides exit code.

## Structured Log Events (Open Question 7 Resolution)

| Event | Fields | Emitter |
|-------|--------|---------|
| `fetch_start` | `command, n_universe` | `run_with_breaker` once at start |
| `fetch_start` | `ticker, source` | `stooq.fetch_ohlcv` per ticker |
| `fetch_success` | `ticker, source, n_bars` | `run_with_breaker` on success |
| `fetch_fail` | `ticker, source, error, attempt` | `run_with_breaker` on exception |
| `breaker_tripped` | `probe_n, success_rate, threshold` | `run_with_breaker` once on trip |

These event names are frozen — Phase 8 (OPS-05) will route them to `runs.jsonl`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] before_sleep_log incompatible with structlog bound-logger**
- **Found during:** Task 4 (test_fetch_empty_raises_after_retries failure)
- **Issue:** `before_sleep_log(log, "warning")` passes a string level to structlog's `make_filtering_bound_logger.log(level, event)`, which expects an int. `TypeError: '<' not supported between instances of 'str' and 'int'`.
- **Fix:** Use `logging.getLogger(__name__)` (stdlib logger) + `logging.WARNING` (int constant) for `before_sleep_log`. The structlog `log` is still used for all other structured events. Applied to `data/ohlcv.py` and the existing `data/universe.py`.
- **Files modified:** `src/screener/data/ohlcv.py`, `src/screener/data/universe.py`
- **Commit:** 2c61a95

**2. [Rule 1 - Bug] test_fetch_empty_raises_after_retries timed out in circuit_breaker test**
- **Found during:** Task 4 first test run
- **Issue:** `test_circuit_breaker_trip` mocked `yf.download` returning empty; tenacity's 5-retry backoff (2+4+8+16 per failure) * 49 failures = ~1570s wall time.
- **Fix:** Mock `append_incremental` directly instead of `yf.download`. The circuit-breaker logic is in `run_with_breaker` at the `append_incremental` call boundary, so this exercises the correct code path without paying tenacity's backoff cost. Applied the same pattern to `test_combined_gate_passes` and `test_structured_log_on_fail`.
- **Files modified:** `tests/test_data_ohlcv.py`
- **Commit:** 2c61a95

**3. [Rule 2 - Missing functionality] Sentinel test needed stale cache, not REF_DATE cache**
- **Found during:** Task 4 (test_sentinel_mismatch_full_refetch failure)
- **Issue:** The plan showed seeding cache with `synthetic_split_mismatch_pair` whose last bar is `REF_DATE`. `append_incremental` returns early with `(cached, False)` when `last_cached_date >= today - 1 day`.
- **Fix:** Build a fresh stale cache (last bar 5 BD before REF_DATE, Close=200) in the test body. Then mock `yf.download` to return a sentinel window (Close=100) on first call and a full backfill on second call.
- **Files modified:** `tests/test_data_ohlcv.py`
- **Commit:** 2c61a95

## Golden-File Test Deferral

`test_nvda_split_2024_recorded` and `test_aapl_split_2020_recorded` are shipped as `@pytest.mark.skip` stubs. To activate:

1. Run `uv run python -c "from screener.data.ohlcv import fetch_splits; import pandas as pd; df = fetch_splits('NVDA'); df.to_parquet('tests/fixtures/golden/NVDA/splits.parquet')"`
2. Write an assertion checking `df.loc['2024-06-10', 'ratio'] == 10.0` (NVDA 10:1 split).
3. Same for AAPL: `df.loc['2020-08-31', 'ratio'] == 4.0`.
4. Remove the `@pytest.mark.skip` decorator.

## Known Stubs

None — all public symbols are fully implemented. The golden-file stubs are intentional deferrals documented above, not data stubs that block the plan's goal.

## Threat Flags

No new network endpoints or auth paths introduced beyond what the threat model covers (T-02-16 through T-02-22 in the plan's threat register). All four D-08 invariants are implemented and tested.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/screener/data/stooq.py | FOUND |
| src/screener/data/ohlcv.py | FOUND |
| tests/test_data_stooq.py | FOUND |
| tests/test_data_ohlcv.py | FOUND |
| commit 7ec1436 (stooq.py) | FOUND |
| commit cb942ec (ohlcv.py + __init__.py) | FOUND |
| commit dd4a5b5 (test_data_stooq.py) | FOUND |
| commit 2c61a95 (test_data_ohlcv.py + before_sleep_log fix) | FOUND |
| Full quick suite (35 passed, 2 skipped) | PASSED |
