---
phase: 02-data-foundation
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - README.md
  - pyproject.toml
  - src/screener/cli.py
  - src/screener/data/__init__.py
  - src/screener/data/ohlcv.py
  - src/screener/data/stooq.py
  - src/screener/data/universe.py
  - src/screener/persistence.py
  - tests/conftest.py
  - tests/test_cli_smoke.py
  - tests/test_data_ohlcv.py
  - tests/test_data_stooq.py
  - tests/test_data_universe.py
  - tests/test_persistence.py
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-03
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 2 delivers a solid data foundation: atomic Parquet writes, tenacity retry wrappers, pandera schema validation, and a circuit-breaker for the yfinance → Stooq fallback path. The layered-DAG architecture is clean and the happy-path logic is sound.

Two BLOCKER-class defects were found: (1) the Stooq fallback path silently omits `splits.parquet` writes for every ticker it recovers, contradicting both the function docstring and the downstream `read_splits` contract; (2) `assert session.verify is True` in production code is the sole TLS-verification guard — it silently vanishes under `python -O`, leaving the iShares fetch exposed to MitM with no runtime error. Six warnings cover a double rename that violates the module's own postcondition, an off-by-one in the universe.py CSV comment, a test that does not validate cache-hit behavior, a production `assert` as a data-invariant guard, a 4-calendar-day stale window that produces false positives over long-weekend holidays, and missed pre-breaker Stooq retry. Four info items cover code quality and documentation issues.

---

## Critical Issues

### CR-01: Stooq fallback path does not write `splits.parquet`

**File:** `src/screener/data/ohlcv.py:277-284`
**Issue:** The `else` branch in `run_with_breaker` (the Stooq path executed after the circuit-breaker trips) calls `write_ohlcv_atomic` but never calls `fetch_splits` or `write_splits_atomic`. Every ticker recovered via Stooq gets a `prices.parquet` written but no `splits.parquet`. The function docstring explicitly states it "writes per-ticker prices.parquet + splits.parquet via persistence.write_ohlcv_atomic and persistence.write_splits_atomic." Downstream callers that invoke `read_splits(ticker)` for any Stooq-recovered ticker will raise `FileNotFoundError`, crashing Phase 3 indicator computation silently for the affected tickers.

**Fix:**
```python
# In run_with_breaker, else branch (Stooq path):
        else:
            try:
                df = stooq_module.fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
                write_ohlcv_atomic(ticker, df)
                # Write an empty splits ledger; Stooq has no splits endpoint.
                write_splits_atomic(ticker, make_empty_splits())
                stooq_ok += 1
                log.info("fetch_success", ticker=ticker, source="stooq", n_bars=len(df))
            except Exception as e:
                failed.append(ticker)
                log.warning("fetch_fail", ticker=ticker, source="stooq", error=str(e), attempt=1)
```
Also update the import at the top of `ohlcv.py`: `make_empty_splits` is already imported from `screener.persistence`.

---

### CR-02: `assert session.verify is True` is the only TLS-verification guard and is disabled by `python -O`

**File:** `src/screener/data/universe.py:133`
**Issue:** The TLS verification check `assert session.verify is True` inside `get_cached_session()` is the sole defence against a misconfigured `requests` session fetching the iShares holdings CSV over an unverified TLS connection. Python's `assert` statements are compiled out when the interpreter runs with the `-O` or `-OO` optimisation flag (common in Docker containers and some CI runners). If `session.verify` were ever `False` (e.g., a future `requests-cache` version that changes the default, or a malicious environment variable injection), the assert would silently pass under `-O` and the fetch would proceed without certificate verification, enabling MitM substitution of the universe CSV.

**Fix:**
```python
def get_cached_session() -> requests_cache.CachedSession:
    ...
    session = requests_cache.CachedSession(...)
    if not session.verify:
        raise RuntimeError(
            "requests-cache session has TLS verification disabled; "
            "refusing to fetch financial data over unverified connection"
        )
    return session
```
Replace `assert` with an unconditional `if not session.verify: raise RuntimeError(...)`. The explicit `raise` survives `-O` and produces a clear, actionable error.

---

## Warnings

### WR-01: CLI `--ticker` path redundantly re-normalises columns already guaranteed lowercase by `fetch_ohlcv`

**File:** `src/screener/cli.py:107-109`
**Issue:** `fetch_ohlcv` guarantees lowercase columns and a `"date"`-named index as a postcondition (documented in `ohlcv.py` lines 100-103: "do NOT add a defensive rename in callers"). The `refresh_ohlcv` single-ticker path at lines 107-109 applies both transforms again. This is harmless today but directly violates the postcondition contract, will confuse maintainers, and creates a divergence from the universe path (which correctly relies on `fetch_ohlcv`'s contract). If `fetch_ohlcv`'s invariant ever changes, only one of the two code paths will pick up the change.

**Fix:** Delete lines 107-109 from `cli.py`:
```python
# REMOVE these three lines — fetch_ohlcv already guarantees them:
df = df.rename(columns=str.lower)           # line 107
if df.index.name is None or df.index.name.lower() != "date":  # line 108
    df.index.name = "date"                  # line 109
```

---

### WR-02: `append_incremental` uses a production `assert` to enforce the lowercase invariant

**File:** `src/screener/data/ohlcv.py:154-157`
**Issue:** `assert "close" in cached.columns` is a data-invariant check on a cached Parquet that could have been written by an older version of the code or by an external tool. `assert` statements are disabled under `python -O`, so if the cache file happens to have `Close` (PascalCase) columns — e.g., a file written before the lowercase migration — the assert silently passes and the subsequent `cached["close"].iloc[-1]` access raises a `KeyError`, producing a confusing traceback that obscures the root cause. The postcondition contract should raise an explicit exception.

**Fix:**
```python
# Replace assert with an explicit check:
if "close" not in cached.columns:
    raise ValueError(
        f"cached panel for {ticker} violates lowercase invariant; "
        f"got columns {list(cached.columns)!r}"
    )
```

---

### WR-03: Stooq adapter does not set `index.name = "date"`, breaking the canonical shape contract

**File:** `src/screener/data/stooq.py:27-59`
**Issue:** `fetch_ohlcv` in `stooq.py` sorts and lowercases the DataFrame but never sets `df.index.name = "date"`. The canonical shape (enforced by `fetch_ohlcv` in `ohlcv.py` and documented as a module-wide contract) requires the DatetimeIndex to be named `"date"`. When a Stooq-sourced DataFrame is read back via `pd.read_parquet`, the index name will be `None` (or whatever Stooq returns — typically also `None`). The `read_panel` code in `persistence.py` calls `prices.rename(columns=str.lower)` defensively but does not rename the index. The OhlcvPanelSchema validates the MultiIndex level name `"date"` at read time, so the schema may accept the parquet (because `write_ohlcv_atomic` sets it in `panel_view.index.names` before validation, not in `df`) but the on-disk index name will be `None`, causing confusion when files are read directly.

**Fix:** Add one line at the end of the Stooq normalisation block in `stooq.py`:
```python
df = df.rename(columns=str.lower)
if df.index.name is None or df.index.name.lower() != "date":
    df.index.name = "date"
```

---

### WR-04: `universe.py` comment incorrectly describes which row `skiprows=9` uses as the CSV header

**File:** `src/screener/data/universe.py:62-63`
**Issue:** The comment reads: "9 metadata rows, then a blank, then the header at row 9 (0-indexed). `skiprows=9` skips lines 0..8 and treats line 9 as the header." Row 9 (0-indexed) is the **blank line**, not the header. The header is at row 10. The code works only because pandas silently skips the blank "header" row and uses the next non-empty line — this is undocumented, version-dependent pandas behaviour. If pandas ever changes this heuristic, the parse silently produces a one-column DataFrame with an empty string as the column name, failing only at `sanity_check` rather than loudly at the parse step. Both the constant `ISHARES_SKIPROWS = 9` and the comment need to be corrected.

**Fix:** Update constant and comment to reflect reality:
```python
# 9 metadata rows + 1 blank = 10 lines before the header at row 10 (0-indexed).
# skiprows=10 skips lines 0..9 and treats line 10 as the header.
ISHARES_SKIPROWS = 10
```
If the live feed genuinely uses `skiprows=9` (blank at row 9 is a valid header line that pandas handles), document the pandas blank-header heuristic explicitly and add a `assert "Ticker" in df.columns` guard immediately after the `read_csv` call to catch a future regression loudly.

---

### WR-05: `test_requests_cache_hit` does not validate that the second fetch is served from cache

**File:** `tests/test_data_universe.py:132-166`
**Issue:** The test asserts `call_count["n"] >= 1`, which is always true after the first call. A real cache-hit test should assert `call_count["n"] == 1` (one HTTP request for two `fetch_ishares_iwb_csv` calls, proving the second was served from the `CachedSession` cache). The current assertion will pass even if the session makes two separate network requests, meaning a complete cache regression (e.g., expiry config change causing every call to miss) would go undetected by this test.

**Fix:**
```python
# Replace the final assertion:
assert call_count["n"] == 1, (
    f"Expected exactly 1 HTTP request (second call from cache); got {call_count['n']}"
)
```
Also note: `_MockResponse.from_cache = False` is set on all responses; the second response should set `from_cache = True` to simulate a real cache hit if the test is ever extended to check that field.

---

### WR-06: `test_fetch_all_invariants_pass` uses an OR assertion that permits regression to PascalCase columns

**File:** `tests/test_data_ohlcv.py:39`
**Issue:** `assert "close" in df.columns or "Close" in df.columns` accepts both lowercase and PascalCase columns as passing. The postcondition contract of `fetch_ohlcv` is **lowercase only** (documented in `ohlcv.py:100-103`). If the lowercase normalisation were accidentally removed from `fetch_ohlcv`, this test would still pass (because the mock returns PascalCase columns, and `"Close" in df.columns` would be true). This means the test provides no regression coverage for the postcondition it was designed to verify.

**Fix:**
```python
# Replace the OR assertion with a strict lowercase check:
assert "close" in df.columns, (
    f"fetch_ohlcv must return lowercase columns; got {list(df.columns)}"
)
assert df.index.name == "date", (
    f"fetch_ohlcv must return index named 'date'; got {df.index.name!r}"
)
```

---

## Info

### IN-01: `read_universe` and `write_universe_atomic` perform no validation of `snapshot_date` before path construction

**File:** `src/screener/persistence.py:213-219, 276-280`
**Issue:** Both functions build a path via `_universe_dir() / f"{snapshot_date}.parquet"` without validating that `snapshot_date` is a well-formed ISO date string. In the current call graph, all callers pass controlled values (from `isoformat()` or `snapshot.stem`). However, `read_universe` and `write_universe_atomic` are public API functions that Phase 3+ components will call directly. A `snapshot_date` containing `"../secret"` would resolve to a path outside `UNIVERSE_CACHE_DIR`. There is no `_assert_safe_ticker`-equivalent guard for snapshot dates.

**Fix:** Add a simple format guard at the top of both functions:
```python
import re
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _assert_safe_snapshot_date(snapshot_date: str) -> None:
    if not _ISO_DATE_RE.match(snapshot_date):
        raise ValueError(f"Unsafe or malformed snapshot_date: {snapshot_date!r}")
```

---

### IN-02: `4`-calendar-day stale window produces false positives after extended market holidays

**File:** `src/screener/data/ohlcv.py:91`, `src/screener/data/stooq.py:51`
**Issue:** `if last < today - timedelta(days=4)` uses calendar days. On the Tuesday following a 4-day US market holiday (e.g., Good Friday through Easter Monday — Thursday last trading day, 5 calendar days to Tuesday), `today - 4 = Friday`, and `last = Thursday < Friday` triggers a spurious `StaleOrEmptyError`. This will cause the run to fail for every ticker on that Tuesday morning even though the data is perfectly fresh, requiring a manual re-run. The same window in both `ohlcv.py` and `stooq.py` needs to be widened to 5 or 6 calendar days, or replace with business-day logic.

**Fix:** Change both occurrences to `timedelta(days=5)` or `timedelta(days=7)` to accommodate 4-day holiday weekends (US markets never close for more than 4 consecutive calendar days):
```python
if last < today - timedelta(days=5):  # 5 covers 4-day holiday weekends
    raise StaleOrEmptyError(...)
```

---

### IN-03: `README.md` status banner still reads "Phase 1 — repository scaffolding"

**File:** `README.md:5`
**Issue:** "**Status:** Phase 1 — repository scaffolding. No data fetching, indicators, or backtests yet." Phase 2 ships real data fetching. This banner is stale and will confuse hiring managers or collaborators reading the README.

**Fix:** Update to: `**Status:** Phase 2 complete — OHLCV cache, Russell 1000 universe builder, and circuit-breaker fallback shipped. Indicators and backtests in Phase 3+.`

---

### IN-04: `_make_ishares_csv_bytes` fixture comment incorrectly describes the blank line as being skipped by `ISHARES_SKIPROWS=9`

**File:** `tests/conftest.py:127-134`
**Issue:** The fixture docstring and inline comment say it "replicates the verified live structure: 9 metadata lines, blank, header". This matches `ISHARES_SKIPROWS=9` only via pandas' blank-header auto-skip heuristic. If the test fixture is ever ported to a different parsing library or if pandas changes this heuristic, the fixture will silently produce wrong column names. The fixture should either set `n_metadata_lines=10` (blank included) or add a `SKIPROWS=10` constant for clarity.

**Fix:** Document the blank-line / pandas-heuristic dependency inline in `_make_ishares_csv_bytes`, and add an assertion in `test_parse_ishares_csv_happy_path` that `"Ticker"` is a column in the parsed result (it currently only asserts row count and column set membership).

---

_Reviewed: 2026-05-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
