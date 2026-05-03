# Phase 2: Data Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 2-Data Foundation
**Areas discussed:** Universe source policy, OHLCV backfill depth, Stooq fallback strategy, Adjusted vs unadjusted OHLCV

---

## Universe source policy

### Q1: Canonical source for the Russell 1000 list

| Option | Description | Selected |
|--------|-------------|----------|
| iShares IWB canonical, Wikipedia ignored | iShares CSV is BlackRock's daily holdings file — authoritative for IWB ≈ R1000. Wikipedia's R1000 page is community-maintained and can lag. Drop the Wikipedia leg entirely; document the deviation from REQUIREMENTS.md. | ✓ |
| iShares canonical, Wikipedia as cross-check | Use iShares IWB as the universe; pull Wikipedia in parallel; if symmetric diff > 30 tickers (~3%), log a structured warning but still trust iShares. Matches REQUIREMENTS.md literal wording. | |
| Wikipedia primary, iShares fallback | Wikipedia first (it's a stable URL/format); iShares only when Wikipedia scrape fails. Simpler than diff-checking but accepts Wikipedia's freshness lag. | |

**User's choice:** iShares IWB canonical, Wikipedia ignored
**Notes:** REQUIREMENTS.md DAT-01 should be updated at next milestone summary to match reality (the "Wikipedia + iShares" wording is now stale).

### Q2: iShares CSV fetch failure behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Fail loud, exit non-zero, no snapshot written | Mirrors DAT-07's fail-loud philosophy. The cron run fails; downstream stages reuse the most recent valid snapshot. No silent degradation. | |
| Fail loud + serve last good snapshot for downstream | Exit non-zero on the universe step but expose `last_valid_snapshot_path` so make ohlcv proceeds against last week's universe. Report banner notes "universe stale: YYYY-MM-DD." | ✓ |
| Retry with tenacity for 24h, then fail | Wrap the fetch in tenacity (5 retries with exp backoff over a few minutes during the run; do not span 24h in a single run). If still failing, exit non-zero. | |

**User's choice:** Fail loud + serve last good snapshot for downstream
**Notes:** Tenacity still wraps the fetch within the run (5 attempts, exponential backoff) — that's mechanical and orthogonal to the "what does downstream see" question this option resolves.

### Q3: Symbol normalization for iShares dot vs yfinance dash notation

| Option | Description | Selected |
|--------|-------------|----------|
| Store both raw + canonical; canonicalize to yfinance dash form | Universe Parquet stores `ticker_raw` (iShares form) and `ticker` (canonical, dash notation, used downstream). Single small normalization function with explicit mappings + regex. Round-trip auditable. | ✓ |
| Canonical-only; lossy normalization in-place | Drop the raw column; only store the dash-form ticker. Simpler schema but loses the bridge back to iShares CSV. | |
| Manual mapping table, no regex | Maintain a hand-curated `data/ticker_map.csv` with iShares→yfinance pairs for known divergences. No regex; explicit only. | |

**User's choice:** Store both raw + canonical; canonicalize to yfinance dash form
**Notes:** —

### Q4: Sector/industry capture source

| Option | Description | Selected |
|--------|-------------|----------|
| Capture from iShares CSV at universe time | iShares IWB CSV includes Sector and Asset Class columns. Persist to the universe snapshot. One fetch, one source of truth, no extra rate-limit pressure on yfinance Ticker.info. | ✓ |
| Refetch from yfinance Ticker.info per ticker | Yahoo's classification (sector + industry) is more granular than iShares (sector-only). 1000 extra Ticker.info calls per universe refresh — weekly, so manageable. | |
| Defer sector/industry capture to Phase 6 | Phase 2 stores tickers only; sector/industry lookup lands when CANSLIM/industry-RS actually consumes it. | |

**User's choice:** Capture from iShares CSV at universe time
**Notes:** Industry-level granularity decision is deferred to Phase 6.

---

## OHLCV backfill depth

### Q1: First-run backfill window

| Option | Description | Selected |
|--------|-------------|----------|
| ~20 years (2005-01-01 → today) | Covers 2008-Q4, 2020-Q1, 2022-H1 regime golden-file tests. Gives 4–5 walk-forward windows for Phase 5. ~5 GB local cache. First run ~30–60 min. | ✓ |
| 10 years (2016-01-01) | 2 walk-forward windows; insufficient for 2008/2020 regime golden files. ~2.5 GB cache. First run ~20 min. | |
| 5 years (2021-01-01) | BCK-01 IS minimum. One walk-forward window. 2008/2020 regime tests fail. Smallest disk + fastest first run. | |
| Configurable via Settings, default ~20y | OHLCV_BACKFILL_START in Settings (default "2005-01-01"). | |

**User's choice:** ~20 years (2005-01-01 → today)
**Notes:** The Settings knob is still added (Claude's Discretion / D-20) for spike runs, but the documented default is 20y.

### Q2: Per-ticker Parquet layout

| Option | Description | Selected |
|--------|-------------|----------|
| Per-ticker directory: data/ohlcv/<TICKER>/{prices,splits}.parquet | One directory per ticker; prices.parquet + splits.parquet co-located. Easy atomic-replace via tempfile + os.replace. | ✓ |
| Two flat dirs: data/ohlcv/<TICKER>.parquet + data/splits/<TICKER>.parquet | Flatter. More LRU pressure on the FS. | |
| Hive-partitioned dataset via pyarrow.dataset | Predicate pushdown for date-range queries. Overkill; defer to v2. | |

**User's choice:** Per-ticker directory: data/ohlcv/<TICKER>/{prices,splits}.parquet
**Notes:** —

### Q3: Incremental append rule

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch from last_cached_date+1 to today; verify last bar matches Yahoo | Read cached parquet, take max(date), call yf with start=max+1. Refetch the last cached bar and assert match — if not, full refresh for that ticker (catches silent corp-action drift). | ✓ |
| Fetch fixed trailing window (last 7 trading days), upsert by date | Always pull last 7 trading days; merge by date. Wasteful on cache hits but resilient to Yahoo backfill. | |
| Smart — use yf.Ticker.actions to detect splits since last fetch, full re-fetch only on split | Detects corp actions explicitly. More API calls (extra .actions() call per ticker per night). | |

**User's choice:** Fetch from last_cached_date+1 to today; verify last bar matches Yahoo
**Notes:** —

### Q4: Post-fetch invariants for the 95% health check

| Option | Description | Selected |
|--------|-------------|----------|
| Strict: non-empty + last bar within 4 business days + monotonic dates + no nulls in close | All four conditions must pass. Catches yfinance's "returns empty on failure" bug. | ✓ |
| Permissive: non-empty + monotonic dates | Skip recency check. Risk: stuck-feed ticker quietly persists. | |
| Strict + flag stale-but-valid in metadata | Same as strict but tickers with last_bar_age > 4bd are written to a separate halted_YYYY-MM-DD.parquet file. | |

**User's choice:** Strict: non-empty + last bar within 4 business days + monotonic dates + no nulls in close
**Notes:** Halt-flag metadata is deferred to Phase 6.

### Q5: Drop-out / delisted ticker policy

| Option | Description | Selected |
|--------|-------------|----------|
| Keep cache forever; only stop appending when not in current universe | Cache stays. Each night refresh OHLCV ONLY for current-universe tickers. Future backtests join data/universe/<snapshot_date>.parquet for point-in-time membership. | ✓ |
| Keep cache + continue appending for all known tickers | Useful for spinoff edges; eventually thousands of dead-ticker 404s. | |
| Purge cache when ticker leaves R1000 | Defeats DAT-02 / survivorship mitigation. | |

**User's choice:** Keep cache forever; only stop appending when not in current universe
**Notes:** —

### Q6: Rate-limit pacing

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential, sleep random.uniform(0.5, 1.5)s, tenacity backoff on 429 | ~17 min nightly. ~30–60 min initial backfill. Matches CLAUDE.md and STACK.md verbatim. | ✓ |
| Configurable concurrency (default 1) via Settings | OHLCV_FETCH_WORKERS knob. Adds ThreadPoolExecutor. | |
| Use yf.download(tickers=[...], group_by='ticker') in batches of 50 | STACK.md explicitly warns against batch mode. | |

**User's choice:** Sequential, sleep random.uniform(0.5, 1.5)s, tenacity backoff on 429
**Notes:** —

### Q7: Atomic write semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Tempfile + os.replace per ticker | POSIX-atomic on same filesystem; survives crashes; no half-written file is ever visible. | ✓ |
| Write-to-staging directory, mv at end | Stronger 'all or nothing' but blocks downstream from reading the cache during the fetch run. | |
| Plain pyarrow write; rely on health check to invalidate | Faster, but a corrupt half-written file silently breaks the next read. | |

**User's choice:** Tempfile + os.replace per ticker
**Notes:** —

---

## Stooq fallback strategy

### Q1: When does Stooq get used

| Option | Description | Selected |
|--------|-------------|----------|
| Whole-run circuit breaker only | Stooq is invoked only when yfinance fails the run-level health gate. Aborts yfinance loop, surfaces banner, tries Stooq for unfetched tickers. | ✓ |
| Per-ticker silent fallback | Each yfinance failure (after tenacity exhausts) immediately tries Stooq. Highest coverage, but Stooq's gaps + 1-day-stale data silently mix into the panel. | |
| Indices only — never per-ticker R1000 Stooq | Stooq reserved for SPY/^IXIC/^VIX/A-D macro inputs (Phase 3). Cleanest contract; weakest resilience. | |

**User's choice:** Whole-run circuit breaker only
**Notes:** —

### Q2: Circuit-breaker trip signal

| Option | Description | Selected |
|--------|-------------|----------|
| First-N probe: < 80% success in first 50 tickers | Catches a Yahoo outage in <2 min instead of after 17 min. 80% threshold is well above 50% (definitely broken) and well below 95% (nominal). | ✓ |
| Rolling-window: 5 consecutive 429/empty in a row | Faster on a sudden outage but more sensitive to a single bad ticker run. | |
| No mid-run breaker; full pass first, then evaluate | Simpler but wastes ~15 min on a known-down day. | |

**User's choice:** First-N probe: < 80% success in first 50 tickers
**Notes:** —

### Q3: Health-gate behavior post-fallback

| Option | Description | Selected |
|--------|-------------|----------|
| 95% gate still applies; Stooq coverage counts toward it | Combined `(yfinance_success + stooq_success) / universe_size >= 0.95` is the gate. If Stooq R1000 coverage is too thin, run fails loud per DAT-07. Banner discloses data-source mix. | ✓ |
| Lower the gate to 90% on Stooq-only path | Acknowledge Stooq's patchy coverage. Risk: silently weakens the survivorship/coverage discipline. | |
| Stooq-fallback runs are 'best effort, advisory only' | If yfinance is down, write a banner-only report saying "no fresh picks today, last good data from <date>". | |

**User's choice:** 95% gate still applies; Stooq coverage counts toward it
**Notes:** —

### Q4: Stooq client choice

| Option | Description | Selected |
|--------|-------------|----------|
| Add pandas-datareader to dependencies | STACK.md-blessed path. Trivial install, no C deps. ~20-line adapter. | ✓ |
| Direct CSV scrape via requests + pandas.read_csv | Zero deps; ~50 lines of normalization. Higher maintenance if Stooq's format drifts. | |
| yfinance's built-in Stooq fallback | Non-starter — yfinance has no built-in Stooq fallback. | |

**User's choice:** Add pandas-datareader to dependencies
**Notes:** —

---

## Adjusted vs unadjusted OHLCV

### Q1: Storage policy for adjusted vs unadjusted prices

| Option | Description | Selected |
|--------|-------------|----------|
| Adjusted-only + splits.parquet; pattern code re-derives unadjusted on demand | Smaller cache (~5 GB at 20y × 1000), single source of truth. PAT-05 explicitly requires re-derivation each run. | ✓ |
| Store both adjusted and unadjusted side-by-side (~2× disk) | Two parquets per ticker. Fastest at Phase 6 — no re-derivation. Doubles cache + validation surface. | |
| Unadjusted-only + splits.parquet; indicators re-derive adjusted on read | Most-correct semantically but pushes adjustment logic into 5+ indicator modules. | |

**User's choice:** Adjusted-only + splits.parquet; pattern code re-derives unadjusted on demand
**Notes:** —

### Q2: splits.parquet source and refresh

| Option | Description | Selected |
|--------|-------------|----------|
| yfinance Ticker.actions, full refresh each night, columns [date, ratio, dividend] | Tiny file (~few rows over 20y per ticker); cheap full refresh. Captures both splits and dividends. | ✓ |
| yfinance Ticker.splits only (drop dividends) | Smaller file. Loses dividend history. Not worth saving 1 column. | |
| EDGAR 8-K parsing for splits, yfinance for backfill | Most authoritative; overkill for v1. Defer to v2. | |

**User's choice:** yfinance Ticker.actions, full refresh each night, columns [date, ratio, dividend]
**Notes:** —

### Q3: Pandera schema scope for Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2 ships: ohlcv_panel, universe, splits schemas as DataFrameModel classes | All three are Phase 2 outputs; lock the cross-layer contract now. Eager validation at write boundary; lazy at read boundary. | ✓ |
| Just ohlcv_panel; defer universe + splits to Phase 3 | Minimal Phase 2 work; more schema churn later. | |
| Function-based DataFrameSchema | Older API; less mypy-friendly. | |

**User's choice:** Phase 2 ships: ohlcv_panel, universe, splits schemas as DataFrameModel classes
**Notes:** —

### Q4: data/ commit policy (carry-forward from Phase 1)

| Option | Description | Selected |
|--------|-------------|----------|
| Commit data/universe/*.parquet only | Universe snapshots are tiny, append-only, accumulate survivorship value. data/ohlcv/ stays gitignored (~5 GB). | |
| Keep all of data/ gitignored; rely on local-only cache | Loses universe snapshot history across machines. | |
| Commit universe/ + splits/ (still tiny, Phase 6 PAT-05 audit-relevant) | Splits per-ticker is tiny over 20y. Keeps pivot re-derivation reproducible across clones. | ✓ |

**User's choice:** Commit universe/ + splits/ (still tiny, Phase 6 PAT-05 audit-relevant)
**Notes:** Reports/ + journal.sqlite + runs.jsonl commit policies belong to Phase 7 / Phase 8.

---

## Claude's Discretion

The user did not call these out explicitly; the planner finalizes standard answers consistent with the locked decisions:

- Weekly-snapshot trigger semantics (idempotent on Monday-of-current-ISO-week, `--force` override)
- requests-cache configuration (SQLite backend, 1h/24h expiries, not used for yfinance)
- CLI subcommand wiring (`--force` on refresh-universe, `--ticker <T>` on refresh-ohlcv)
- Structured logging events emitted (`fetch_start/success/fail`, `breaker_tripped`, `health_check_*`, `snapshot_written`)
- `.env.example` updates mirroring D-20 Settings additions
- Test fixtures (synthetic empty yfinance, split-mismatch sentinel, malformed iShares CSV)
- Empty splits.parquet handling (zero-row file with schema preserved)
- README "Data layer" section additions

## Deferred Ideas

- EDGAR `set_identity()` call → Phase 6 (CAT-04)
- `make macro` (FRED + Stooq macro indices) → Phase 3 (DAT-04); reuses Phase 2's Stooq adapter
- `make fundamentals` (Finnhub + 45-day lag) → Phase 6 (DAT-05)
- Insider Form 4 + 13F EDGAR fetches → Phase 6
- `runs.jsonl` writer → Phase 8 (OPS-05)
- Reports/journal commit policies → Phases 7 + 8
- Halt-flag metadata → Phase 6 catalysts
- Threading / `OHLCV_FETCH_WORKERS` knob → out of v1 entirely
- Industry-level granularity → Phase 6 decides
- Wikipedia universe leg → dropped (D-01); REQUIREMENTS.md DAT-01 to be edited at next milestone summary
- Initial-backfill resumability → not needed; atomic per-ticker writes preserve progress, incremental append picks up where it left off
