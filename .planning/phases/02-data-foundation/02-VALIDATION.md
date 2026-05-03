---
phase: 2
slug: data-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-02
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `02-RESEARCH.md` §"Validation Architecture". Final task IDs land here once `/gsd-plan-phase` finishes.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + hypothesis 6.x (Phase 1 baseline; both already installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 1) |
| **Quick run command** | `uv run pytest -m "not slow and not integration" -x` |
| **Full suite command** | `uv run pytest --cov=src/screener --cov-fail-under=80 --strict-markers` |
| **Estimated runtime** | ~30 s quick / ~90 s full (Wave 0 → Wave 4 budget) |

Mypy gate also runs in CI (Phase 1 baseline) and binds strictly on `src/screener/persistence.py` once Phase 2 lands its DataFrameModel schemas. `src/screener/data/*` stays under the existing mypy ignore-overrides because it depends on un-stubbed third-party libraries (yfinance, pandas-datareader).

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -m "not slow and not integration" -x`
- **After every plan wave:** Run `uv run pytest --cov=src/screener --cov-fail-under=80 --strict-markers`
- **Before `/gsd-verify-work`:** Full suite green; coverage ≥ 80% on `src/screener/persistence.py` and `src/screener/data/`
- **Max feedback latency:** 30 s (quick) / 90 s (full)

---

## Per-Task Verification Map

> Plan IDs (`02-01`, `02-02`, …) and task IDs are stamped in by `/gsd-plan-phase`. This table seeds the contract from REQUIREMENTS → behaviors. The plan-checker confirms every plan task points at a row here.

| Plan (TBD by planner) | Wave | Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|------|------|-------------|----------|-----------|-------------------|-------------|--------|
| TBD universe | 1 | DAT-01 | iShares CSV happy-path parse returns ≥ 800 equity rows | unit | `uv run pytest tests/test_data_universe.py::test_parse_ishares_csv_happy_path -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-01 | `normalize_ticker()` allowlist round-trip (BRKB → BRK-B) | unit | `uv run pytest tests/test_data_universe.py::test_normalize_ticker_allowlist -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-01 | iShares CSV with < 800 rows raises ValueError | unit | `uv run pytest tests/test_data_universe.py::test_parse_ishares_csv_undersized_fails -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-01 | Unknown sector raises ValueError | unit | `uv run pytest tests/test_data_universe.py::test_parse_ishares_csv_unknown_sector_fails -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-02 | Weekly snapshot writes `data/universe/<iso_monday>.parquet` | unit | `uv run pytest tests/test_data_universe.py::test_snapshot_iso_monday_keying -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-02 | Same-week re-run is a no-op | unit | `uv run pytest tests/test_data_universe.py::test_snapshot_idempotent_same_week -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-02 | `--force` overrides idempotency | unit | `uv run pytest tests/test_data_universe.py::test_snapshot_force_overwrites -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-09 | OhlcvPanelSchema rejects null close | unit | `uv run pytest tests/test_persistence.py::test_panel_schema_rejects_null_close -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-09 | OhlcvPanelSchema rejects negative price | unit | `uv run pytest tests/test_persistence.py::test_panel_schema_rejects_negative_price -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-09 | OhlcvPanelSchema rejects wrong index order | unit | `uv run pytest tests/test_persistence.py::test_panel_schema_rejects_wrong_index_order -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-09 | UniverseSchema rejects unknown sector | unit | `uv run pytest tests/test_persistence.py::test_universe_schema_rejects_unknown_sector -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-09 | SplitsSchema rejects negative ratio | unit | `uv run pytest tests/test_persistence.py::test_splits_schema_rejects_negative -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-09 | Lazy-mode validation collects all errors | unit | `uv run pytest tests/test_persistence.py::test_lazy_collects_multiple_errors -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-03 | Atomic write — Ctrl-C mid-write leaves no partial Parquet | unit | `uv run pytest tests/test_persistence.py::test_atomic_write_crash_no_partial -x` | ❌ W0 | ⬜ pending |
| TBD persistence | 1 | DAT-08 | Empty actions → zero-row splits.parquet with schema preserved | unit | `uv run pytest tests/test_persistence.py::test_empty_splits_schema_preserved -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-03 | yfinance fetch with all 4 invariants passing → success | unit | `uv run pytest tests/test_data_ohlcv.py::test_fetch_all_invariants_pass -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-03 | yfinance returns empty → tenacity retries 5× then raises | unit | `uv run pytest tests/test_data_ohlcv.py::test_fetch_empty_raises_after_retries -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-03 | Stale last bar (>4 business days) fails invariant | unit | `uv run pytest tests/test_data_ohlcv.py::test_fetch_stale_fails -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-03 | Non-monotonic index fails invariant | unit | `uv run pytest tests/test_data_ohlcv.py::test_fetch_non_monotonic_fails -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-03 | Null close fails invariant | unit | `uv run pytest tests/test_data_ohlcv.py::test_fetch_null_close_fails -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-03 | Sentinel mismatch on incremental triggers full re-fetch | unit | `uv run pytest tests/test_data_ohlcv.py::test_sentinel_mismatch_full_refetch -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-06 | Tenacity backoff on simulated 429 | unit (mocked) | `uv run pytest tests/test_data_ohlcv.py::test_tenacity_backoff_on_429 -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-06 | structured `fetch_fail` event on tenacity exhaustion | unit | `uv run pytest tests/test_data_ohlcv.py::test_structured_log_on_fail -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-08 | NVDA 2024-06-10 split ratio = 10.0 | golden-file | `uv run pytest tests/test_data_ohlcv.py::test_nvda_split_2024_recorded` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 2 | DAT-08 | AAPL 2020-08-31 split ratio = 4.0 | golden-file | `uv run pytest tests/test_data_ohlcv.py::test_aapl_split_2020_recorded` | ❌ W0 | ⬜ pending |
| TBD stooq | 2 | DAT-03 | Stooq adapter normalizes columns + ascending index | unit | `uv run pytest tests/test_data_stooq.py::test_normalize_columns_and_order -x` | ❌ W0 | ⬜ pending |
| TBD stooq | 2 | DAT-03 | Stooq adapter raises on empty response | unit | `uv run pytest tests/test_data_stooq.py::test_empty_raises -x` | ❌ W0 | ⬜ pending |
| TBD stooq | 2 | DAT-03 | Stooq breaker — < 80% in first 50 routes remainder to Stooq | unit | `uv run pytest tests/test_data_ohlcv.py::test_circuit_breaker_trip -x` | ❌ W0 | ⬜ pending |
| TBD universe | 1 | DAT-06 | requests-cache returns cached response on second call | unit (mocked) | `uv run pytest tests/test_data_universe.py::test_requests_cache_hit -x` | ❌ W0 | ⬜ pending |
| TBD ohlcv | 3 | DAT-07 | (yf+stooq) ≥ 0.95 satisfies combined gate | unit | `uv run pytest tests/test_data_ohlcv.py::test_combined_gate_passes -x` | ❌ W0 | ⬜ pending |
| TBD cli | 3 | DAT-07 | < 95% success → CLI exits non-zero with `health_check_failed` | integration | `uv run pytest tests/test_cli_smoke.py::test_health_gate_below_95_fails_run` | ❌ W0 | ⬜ pending |
| TBD cli | 3 | DAT-07 | ≥ 95% success → CLI exits zero with `health_check_passed` | integration | `uv run pytest tests/test_cli_smoke.py::test_health_gate_above_95_passes_run` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Tests do not exist yet — these are Wave 0 deliverables that must precede any data-layer code:

- [ ] `tests/conftest.py` — extend with these synthetic fixtures (mock yfinance / iShares CSV, no network):
  - `synthetic_ohlcv_valid_df` — 252 days passing all 4 invariants
  - `synthetic_ohlcv_empty_df` — empty DataFrame for the silent-empty test
  - `synthetic_ohlcv_stale_df` — last bar 10 business days old
  - `synthetic_ohlcv_null_close_df` — one NaN in close
  - `synthetic_ohlcv_non_monotonic_df` — last 5 bars in random order
  - `synthetic_ishares_csv_bytes` — 1010-row valid CSV mock matching live structure
  - `synthetic_ishares_csv_undersized_bytes` — 500-row variant for sanity-check fail
  - `synthetic_ishares_csv_bad_sector_bytes` — one row with sector "Bogus Sector"
  - `synthetic_split_mismatch_pair` — `(cached, refetched)` pair where the sentinel close differs by 0.5×
  - `synthetic_stooq_descending_df` — Stooq-shape DataFrame (descending index, PascalCase columns)
- [ ] `tests/test_data_universe.py` — 7 tests (DAT-01, DAT-02, DAT-06)
- [ ] `tests/test_data_ohlcv.py` — 9 tests (DAT-03, DAT-06, DAT-07, DAT-08)
- [ ] `tests/test_data_stooq.py` — 3 tests (DAT-03 fallback)
- [ ] `tests/test_persistence.py` — 9 tests (DAT-09, atomic-write, read_panel)
- [ ] `tests/test_cli_smoke.py` — extend with 2 health-gate integration tests (DAT-07)

**Total target: 30 tests** across 5 test files; ≥ 80% coverage on `src/screener/persistence.py` and `src/screener/data/`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First-run 20-year backfill (~30–60 min wall-clock, ~5 GB cache) | DAT-03 (D-05) | Slow + network-bound; CI cannot afford the runtime, and Yahoo rate-limits make it nondeterministic. Production correctness is covered by per-ticker unit tests. | After plans land, run `uv run python -m screener.cli refresh-ohlcv --ticker NVDA` once locally; expect `data/ohlcv/NVDA/{prices,splits}.parquet` to exist with 5000+ rows and 1+ split entry. |
| Live iShares CSV reachability | DAT-01 (D-01) | Depends on BlackRock CDN reachability and User-Agent acceptance. Live HTTP is excluded from CI to keep runs reproducible. | Run `uv run python -m screener.cli refresh-universe` once; expect `data/universe/<this_iso_monday>.parquet` with 950–1010 rows. |
| Live Stooq fallback latency | DAT-03 (D-12) | Stooq's coverage and response time vary day-to-day; locking into a CI test would be flaky. Coverage gap is documented in 02-RESEARCH.md §"Pitfall 3". | Manually trigger by injecting a yfinance failure for 50% of first-50 tickers; verify breaker emits `breaker_tripped` and Stooq attempts run. |
| NVDA/AAPL split ratio match (golden-file capture) | DAT-08 (ROADMAP success criterion 4) | Live yfinance fetch is required + golden-file Parquet must be hand-captured into `tests/fixtures/` (or `tests/data/golden/`). CI cannot afford the runtime or the non-determinism of a live yfinance call. The `test_nvda_split_2024_recorded` and `test_aapl_split_2020_recorded` stubs in `tests/test_data_ohlcv.py` are `@pytest.mark.skip`-decorated until the golden files land. | After plans land, run `uv run python -m screener.cli refresh-ohlcv --ticker NVDA` and inspect `data/ohlcv/NVDA/splits.parquet` — confirm a row at 2024-06-10 with ratio = 10.0; then `uv run python -m screener.cli refresh-ohlcv --ticker AAPL` and confirm `data/ohlcv/AAPL/splits.parquet` has a row at 2020-08-31 with ratio = 4.0. Capture both as golden-file Parquets under `tests/fixtures/golden/`, then drop the `@pytest.mark.skip` decorator from each of the two stubbed tests so they assert against the captured fixtures. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or are pinned to a Wave 0 fixture
- [ ] Sampling continuity: no 3 consecutive tasks without an automated verify command
- [ ] Wave 0 covers every MISSING reference above (5 test files + conftest fixtures)
- [ ] No watch-mode flags in the per-task commands
- [ ] Feedback latency < 30 s on the quick command
- [ ] `nyquist_compliant: true` set in frontmatter once plans + Wave 0 are stamped

**Approval:** pending
