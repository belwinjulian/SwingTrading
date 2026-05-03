---
plan: 02-03
phase: 02-data-foundation
status: complete
wave: 2
completed: 2026-05-03
tags: [universe, ishares, iwb, requests-cache, tenacity, parquet, weekly-snapshot]
subsystem: data/universe
dependency_graph:
  requires: [02-01, 02-02]
  provides: [fetch_ishares_iwb_csv, parse_ishares_iwb_csv, normalize_ticker, sanity_check, iso_week_monday, refresh_universe, build_universe_dataframe, get_cached_session, ALLOWLIST]
  affects: [02-04, 02-05, all-phases-read_universe]
tech_stack:
  added: [requests-cache CachedSession, tenacity retry decorator, ALLOWLIST dict, ISO-week-Monday keying]
  patterns: [HTTP-cache-then-parse, idempotent-weekly-snapshot, allowlist-normalization]
key_files:
  created: [src/screener/data/universe.py, tests/test_data_universe.py]
  modified: [src/screener/data/__init__.py]
decisions:
  - "ALLOWLIST dict replaces the D-03 regex (which was a no-op on live IWB feed — no dots in tickers). Three entries: BRKB->BRK-B, BFB->BF-B, BFA->BF-A. Amendment locked 2026-05-02."
  - "ISO-week-Monday keying: holiday-agnostic; the Monday of the ISO week containing today() is the snapshot key. Open Question 4 resolution."
  - "Row sanity thresholds: [800, 1100] hard fail (ValueError), [950, 1010] soft warning (structured log event). Open Question 5 resolution."
  - "HTTP cache path: ~/.cache/screener/http.sqlite (XDG-style, survives git clean). Open Question 6 resolution."
  - "test_requests_cache_hit patches requests.Session.get — CachedSession inherits from Session so the mock covers both paths (fix applied in commit 94fd6be)."
metrics:
  duration: ~15 minutes (2 commits)
  completed: "2026-05-03"
  tasks_completed: 2
  files_modified: 3
---

# Phase 02 Plan 03: Universe IWB Pipeline Summary

## One-liner

iShares IWB CSV fetcher + ALLOWLIST normalizer + sanity gate + ISO-week-Monday snapshot writer, with 8 green unit tests and a requests-cache CachedSession shared with future Finnhub/FRED fetchers.

## Delivered

### Public API (src/screener/data/universe.py)

- `ISHARES_IWB_URL` — verified-live iShares AJAX CSV URL (2026-05-02)
- `ISHARES_HEADERS` — Mozilla User-Agent header dict (T-02-13 defense)
- `ISHARES_SKIPROWS = 9` — skips 9 metadata lines before the CSV header
- `ISHARES_ENCODING = "utf-8-sig"` — strips the UTF-8 BOM from the iShares feed
- `ALLOWLIST = {"BRKB": "BRK-B", "BFB": "BF-B", "BFA": "BF-A"}` — D-03 amended (replaces regex)
- `CACHE_PATH = ~/.cache/screener/http.sqlite` — Open Question 6 resolution
- `ROW_HARD_MIN/MAX = 800/1100` — ValueError on out-of-range count
- `ROW_WARN_MIN/MAX = 950/1010` — structured `universe_row_count_warning` event in soft zone
- `normalize_ticker(raw)` — ALLOWLIST lookup, pass-through for everything else
- `get_cached_session()` — shared requests-cache CachedSession; TLS assert (T-02-22)
- `fetch_ishares_iwb_csv(session=None)` — tenacity-wrapped: 5 attempts, exp backoff min=2 max=60, reraise=True
- `parse_ishares_iwb_csv(content)` — skiprows=9, utf-8-sig, filter to Equity, drop trailer
- `sanity_check(df)` — hard gate + soft warning + GICS sector validation
- `iso_week_monday(today)` — Monday of the ISO week (holiday-agnostic)
- `build_universe_dataframe(parsed)` — maps iShares columns → UniverseSchema columns
- `refresh_universe(force, today)` — idempotent weekly snapshot; returns Path or None

### Barrel re-exports (src/screener/data/__init__.py)

`fetch_ishares_iwb_csv`, `iso_week_monday`, `normalize_ticker`, `parse_ishares_iwb_csv`, `refresh_universe`, `sanity_check` added to `__all__`.

### Tests (tests/test_data_universe.py — 8 tests, all green)

`test_parse_ishares_csv_happy_path`, `test_normalize_ticker_allowlist`,
`test_parse_ishares_csv_undersized_fails`, `test_parse_ishares_csv_unknown_sector_fails`,
`test_snapshot_iso_monday_keying`, `test_snapshot_idempotent_same_week`,
`test_snapshot_force_overwrites`, `test_requests_cache_hit`

## Deviations from Plan

**[Fix] test_requests_cache_hit patch target corrected**
- `requests_cache.CachedSession.get` doesn't exist as a direct patch target; the fix patches `requests.Session.get` (CachedSession inherits it), which correctly intercepts the call and keeps the test offline.
- Commit: 94fd6be

## Self-Check: PASSED

Files exist:
- src/screener/data/universe.py: FOUND (274 lines)
- tests/test_data_universe.py: FOUND (8 tests)
- src/screener/data/__init__.py: FOUND (updated)

Commits:
- d7266a4 feat(02-03): implement data/universe.py IWB fetcher + parser + snapshot writer
- 94fd6be fix(02-03): patch CachedSession.get not requests.Session.get in cache test

Test results: 8 passed (test_data_universe.py), architecture DAG green
