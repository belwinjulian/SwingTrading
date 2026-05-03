# Phase 2: Data Foundation - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 ships the data layer that every downstream stage will read from disk: a Russell 1000 universe builder backed by the iShares IWB CSV with weekly snapshots written to `data/universe/YYYY-MM-DD.parquet`; a yfinance-primary OHLCV cache (per-ticker Parquet, 20-year backfill from 2005-01-01, incremental nightly append) with a Stooq circuit-breaker fallback when yfinance is down; per-ticker `splits.parquet` with the full corporate-action ledger; HTTP hygiene via `requests-cache` + `tenacity`; a 95% universe-coverage health check that fails the run loud and refuses to commit partial results; and pandera `DataFrameModel` schemas at the `data/ → indicators/` boundary for OHLCV, universe, and splits.

The phase delivers nothing in `indicators/`, `signals/`, or `regime` — Phase 3 builds those on top of the panel that Phase 2 produces. Survivorship-bias mitigation starts on day one of Phase 2 (every weekly universe snapshot accumulates point-in-time membership for future backtests). Corporate-action integrity is preserved by storing the splits ledger separately so Phase 6 pattern detection can re-derive unadjusted pivots without caching dollar levels.

Requirements covered: **DAT-01** (universe refresh), **DAT-02** (weekly snapshot), **DAT-03** (yfinance + Stooq OHLCV cache), **DAT-06** (requests-cache + tenacity), **DAT-07** (95% coverage health check), **DAT-08** (splits.parquet), **DAT-09** (pandera schemas).

</domain>

<decisions>
## Implementation Decisions

### Universe source policy

- **D-01: iShares IWB CSV is the single canonical source.** The Wikipedia leg referenced in `REQUIREMENTS.md` DAT-01 is dropped — the Russell 1000 Wikipedia page is community-maintained and lags rebalances, while the iShares IWB holdings CSV is BlackRock's daily authoritative file for IWB ≈ R1000. Document the deviation from REQUIREMENTS.md so the tracker matches reality. No diff/cross-check pipeline is built.
- **D-02: On iShares fetch failure, fail loud BUT expose the most recent valid snapshot for downstream.** `make universe` exits non-zero when the CSV fetch fails sanity checks (HTTP ≠ 200, < 800 rows, missing required columns). Universe Parquet is NOT overwritten. `data/ → ohlcv` reads the most recent good snapshot from `data/universe/` so `make ohlcv` can still proceed against last week's universe. The report banner notes "universe stale: <YYYY-MM-DD>" so the user sees the degraded mode. Tenacity wraps the fetch (5 attempts, exponential backoff) inside the single run — no 24-hour spans.
- **D-03: Symbol normalization stores both raw and canonical forms.** Universe Parquet has columns `ticker_raw` (iShares feed form, e.g., `BRKB`, `BFB`, `BFA`) and `ticker` (canonical dash notation for yfinance, e.g., `BRK-B`, `BF-B`, `BF-A`). Single `normalize_ticker()` function in `data/universe.py` consults a hand-curated allowlist `ALLOWLIST = {"BRKB": "BRK-B", "BFB": "BF-B", "BFA": "BF-A"}`; tickers outside the allowlist pass through unchanged. A sanity assertion inside `parse_ishares_iwb_csv()` flags any new ticker matching `^[A-Z]{4,5}[A-Z]$` and not in the allowlist as a candidate for quarterly review (logged as a warning, does not fail the run). Round-trip auditable; lossless against iShares. Downstream layers consume `ticker` only. **Amended 2026-05-02 (post-research):** the originally-recorded regex `\.([A-Z])$` → `-\1` was a no-op against the live iShares feed (verified — feed contains no dots; share-class tickers are concatenated). Allowlist replaces the regex; rationale captured in 02-DISCUSSION-LOG.md "Amendment 2026-05-02".
- **D-04: Sector capture happens at universe time from the iShares CSV.** The IWB CSV ships a `Sector` column; persist it on the universe snapshot. No per-ticker `yfinance.Ticker.info` calls in Phase 2 — that's a 1000-call rate-limit pressure for marginal granularity gain. Phase 6 (CANSLIM L) and any industry-RS work consume `sector` from the universe Parquet directly. If `industry` granularity becomes necessary, Phase 6 makes its own decision then.

### OHLCV cache: backfill, layout, append, invariants

- **D-05: First-run backfill is `start=2005-01-01` (~20 years).** Covers 2008-Q4, 2020-Q1, 2022-H1 regime golden-file tests (Phase 3 REG-04) without special-casing. Provides 4–5 walk-forward windows for Phase 5 (BCK-01) instead of 1. Estimated cache size: ~5 GB local at 1000 tickers; first-run wall time: 30–60 min one-shot. `OHLCV_BACKFILL_START` is exposed as a Settings field with default `"2005-01-01"` so spike runs can use a smaller window.
- **D-06: Per-ticker directory layout: `data/ohlcv/<TICKER>/{prices,splits}.parquet`.** One directory per ticker; `prices.parquet` holds the full OHLCV time series; `splits.parquet` holds the corporate-action ledger. Co-located so atomic replace + lookup are simple. No Hive partitioning, no flat dual-tree layout. Downstream `persistence.read_ohlcv(ticker)` and `persistence.read_splits(ticker)` are the only readers.
- **D-07: Incremental append rule: fetch from `last_cached_date+1`, sentinel-check the previous bar.** Each nightly run reads `prices.parquet`, takes `max(date)`, calls `yf.download(start=max+1)`. Before appending, refetch the cached `last_cached_date` bar from yfinance and assert it matches (within float tolerance). If the sentinel bar mismatches, treat it as a corporate-action drift and trigger a full ticker re-fetch (overwrite `prices.parquet`). Catches silent split-related drift without paying for nightly full re-fetch.
- **D-08: Strict post-fetch invariants gate the 95% health check.** A per-ticker fetch counts as "successful" only if all four hold: (a) DataFrame is non-empty, (b) `df.index.max().date() >= today - 4 business days`, (c) date index is monotonically increasing, (d) `close` column has zero nulls. Failures don't count toward the 95% gate (DAT-07). The 4-business-day recency check is the canonical defense against yfinance's "returns empty on failure" silent-bug from `research/SUMMARY.md`. Halt-flag metadata (Option C) is deferred to Phase 6 catalysts.
- **D-09: Drop-out / delisted policy: keep cache forever, freeze on drop.** When a ticker leaves the current R1000, its existing `prices.parquet` and `splits.parquet` stay on disk untouched. Nightly fetch is filtered to current-universe tickers only. Future backtests join `data/universe/<snapshot_date>.parquet` to recover point-in-time membership; the frozen OHLCV is what an honest backtest needs. Maximally preserves DAT-02's survivorship-mitigation value. Spinoff/re-listing edge cases (ticker leaves, comes back later) are handled naturally — append resumes at re-entry.
- **D-10: Rate-limit pacing is sequential with 0.5–1.5 s sleep + tenacity.** Per-ticker fetch in a single Python loop; `time.sleep(random.uniform(0.5, 1.5))` between tickers; `@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(5))` on the fetch call. ~17 min nightly incremental on 1000 tickers; ~30–60 min initial 20y backfill. No `yf.download(tickers=[...])` batch mode (STACK.md explicitly warns against it). No threading/concurrency in v1 — `OHLCV_FETCH_WORKERS` is NOT exposed as a knob.
- **D-11: Atomic per-ticker writes via tempfile + `os.replace`.** Write to `data/ohlcv/<TICKER>/.prices.parquet.tmp.<pid>`, then `os.replace()` into `prices.parquet`. POSIX-atomic on the same filesystem; a Ctrl-C / crash mid-run never leaves a half-written file visible. Same pattern for `splits.parquet`. The universe Parquet uses the same write-tempfile-then-replace contract.

### Stooq fallback

- **D-12: Stooq is a whole-run circuit-breaker, not a per-ticker silent fallback.** Within the first 50 tickers of a nightly run, if `successful_fetches / 50 < 0.80`, the breaker trips: the yfinance loop aborts, a structured warning logs, and the remaining unfetched tickers are routed through the Stooq adapter. Catches a Yahoo outage in <2 min instead of after the full ~17-min loop. Per-ticker silent fallback would silently mix Stooq's coverage gaps + 1-day-stale data into the panel — explicitly rejected.
- **D-13: 95% coverage gate (DAT-07) still applies post-fallback; Stooq successes count toward it.** Combined `(yfinance_success + stooq_success) / universe_size >= 0.95` is the run gate. If Stooq's R1000 coverage is too thin to make up the yfinance shortfall, the run fails loud per DAT-07 and refuses to commit. The report banner documents the data-source mix: `data source: yfinance (n=X) + stooq (n=Y), date_t-1 stale`. No "degraded mode 90% gate" — the discipline is uniform.
- **D-14: Stooq client is `pandas-datareader`.** Add `pandas-datareader>=0.10` to `[project.dependencies]` in `pyproject.toml`. Wrapper in `data/stooq.py` calls `pdr.DataReader(ticker, 'stooq')`, normalizes column names + index to match the canonical OHLCV schema (D-15), and applies the same post-fetch invariants (D-08). Stooq output also flows through atomic-write per D-11.

### Pandera schemas (DAT-09)

- **D-15: Phase 2 ships three `DataFrameModel` class-based schemas in `src/screener/persistence.py`:**
  1. `OhlcvPanelSchema` — `ticker: str`, `date: pd.Timestamp` (or DatetimeIndex), `open/high/low/close: float >= 0`, `volume: int >= 0`, `close` non-null. Multi-ticker panel shape (long format) with composite index `(ticker, date)`.
  2. `UniverseSchema` — `ticker: str` (canonical dash form), `ticker_raw: str` (iShares form), `name: str`, `sector: str`, `weight_pct: float`. One row per ticker.
  3. `SplitsSchema` — `ticker: str`, `date: pd.Timestamp`, `ratio: float >= 0`, `dividend: float >= 0`. Sparse (rows only on event dates).
- **D-16: Validation policy: eager at the `data/` write boundary; lazy at the `indicators/` read boundary.** `data/ohlcv.py` validates with `lazy=False` so a single bad row aborts the write loud. `indicators/` (Phase 3) reads via `persistence.read_panel(...)` which validates with `lazy=True` to collect all schema errors at once for clearer downstream debugging. The schema modules live in `persistence.py` (the Phase 1 D-13 reserved seam) — single import surface for the contract.

### Splits ledger storage (DAT-08, supporting PAT-05)

- **D-17: Store adjusted-only OHLCV; splits.parquet is the corp-action ledger that lets Phase 6 re-derive unadjusted pivots on demand.** yfinance fetches use `auto_adjust=True` (the default); cache holds split-and-dividend-adjusted prices. PAT-05 explicitly requires "pivots are re-derived from adjusted closes on every run, never cached as fixed dollar levels," which is consistent with this storage choice. Downstream pattern code that needs the raw price ladder applies `splits.parquet` ratios in-memory at read time. Saves ~5 GB vs storing both.
- **D-18: splits.parquet is sourced from `yfinance.Ticker.actions`, refreshed in full each nightly run, schema `[date, ratio, dividend]`.** Full refresh-overwrite (not append) on every run because the file is tiny (~few rows over 20y per ticker). Schema captures both splits and dividends so Phase 6 can reconstruct the full corporate-action timeline if needed. Refresh path goes through the same atomic-write pattern (D-11).

### data/ commit policy (Phase 1 carry-forward todo)

- **D-19: Commit `data/universe/*.parquet` AND `data/splits/*.parquet`; keep `data/ohlcv/` gitignored.** `.gitignore` carves out two exceptions for the small, append-only artifacts that have audit/repro value. Universe snapshots accumulate the point-in-time membership dataset across machines and CI runs. Splits ledger lets pivot re-derivation in Phase 6 stay reproducible across a fresh clone. OHLCV cache (~5 GB) stays local-only; Phase 8 cron re-fetches incrementally. Phase 7 (`journal.sqlite`) and Phase 8 (`reports/`, `runs.jsonl`) commit policies are decided in those phases — out of scope here.

### Settings additions (D-15 from Phase 1; mechanical extension)

- **D-20: Phase 2 extends `screener.config.Settings` additively with:**
  - `OHLCV_CACHE_DIR: Path = Path("data/ohlcv")`
  - `UNIVERSE_CACHE_DIR: Path = Path("data/universe")`
  - `OHLCV_BACKFILL_START: str = "2005-01-01"` (ISO date string)
  - `UNIVERSE_HEALTH_THRESHOLD: float = 0.95` (matches DAT-07)
  - `STOOQ_BREAKER_PROBE_N: int = 50` (matches D-12)
  - `STOOQ_BREAKER_THRESHOLD: float = 0.80` (matches D-12)
  - `OHLCV_FETCH_SLEEP_MIN_S: float = 0.5`, `OHLCV_FETCH_SLEEP_MAX_S: float = 1.5` (matches D-10)
  - `EDGAR_IDENTITY` already exists from Phase 1 — used here only to prepare the seam; no EDGAR calls in Phase 2.

### Claude's Discretion

The user did not call these out explicitly; the planner finalizes standard answers consistent with the locked decisions above:

- **Weekly-snapshot trigger semantics for `data/universe/`.** Standard pattern: `make universe` is idempotent — checks whether `data/universe/<this_monday>.parquet` exists and skips if so unless `--force`; writes `data/universe/<today>.parquet` otherwise. Cron runs daily but only writes a new snapshot at most once per ISO week. Holidays/weekends: snapshot is keyed off the Monday of the current ISO week, computed from `today.isoweekday()`.
- **`requests-cache` configuration.** SQLite backend at `~/.cache/screener/http.sqlite`; 1-hour expiry for "fresh-data" endpoints (universe CSV, OHLCV calls bypass cache entirely since per-ticker Parquet is the cache); 24-hour expiry for static-ish endpoints (Finnhub fundamentals when Phase 6 lands). Not used for yfinance (yfinance manages its own session) — only HTTP-based fetchers (Stooq via pandas-datareader, iShares CSV download).
- **CLI subcommand wiring.** `screener refresh-universe` and `screener refresh-ohlcv` subcommands (already stubbed in Phase 1's `cli.py` per Phase 1 D-14) get real bodies. Makefile `make data` already chains them. Add `--force` flag on `refresh-universe` for the snapshot override above; `--ticker <T>` flag on `refresh-ohlcv` for single-ticker debugging.
- **Structured logging events.** Every fetch loop emits structured events via `structlog` (already configured Phase 1): `fetch_start`, `fetch_success` / `fetch_fail` per ticker, `breaker_tripped`, `health_check_passed` / `health_check_failed`, `snapshot_written`. Phase 8 (OPS-05) consumes these for `runs.jsonl`; Phase 2 just emits them.
- **`.env.example` updates.** Mirror the new Settings fields (D-20) with placeholder values + comments. `EDGAR_IDENTITY` already there from Phase 1.
- **Test fixtures.** Synthetic OHLCV fixtures live in `tests/conftest.py` (already there from Phase 1's `01-03-tests-scaffolding-PLAN.md`). Phase 2 adds: a fixture that simulates yfinance returning empty (post-fetch invariants test); a fixture that simulates a split-mismatch sentinel (D-07 test); a fixture that simulates an iShares CSV with < 800 rows (D-02 test).
- **`splits.parquet` empty case.** When a ticker has no corporate actions in the cached window, write a zero-row Parquet with the schema preserved (don't skip the file — pandera schema check would otherwise fail on read).
- **`.gitignore` carve-out reconciles D-06 and D-19.** D-06 locks per-ticker co-location at `data/ohlcv/<TICKER>/{prices,splits}.parquet`; D-19 says commit splits but not prices. Reconciliation: keep D-06's layout and write a selective .gitignore — `data/ohlcv/**/prices.parquet` is ignored, `!data/ohlcv/**/splits.parquet` is committed. There is no separate `data/splits/` top-level directory. **Amended 2026-05-02 (post-research):** rationale captured in 02-DISCUSSION-LOG.md "Amendment 2026-05-02".
- **README updates.** Add a "Data layer" section pointing at the per-ticker directory layout, the 20y backfill expectation, the Stooq fallback semantics, and the disclosed survivorship caveat (per `CLAUDE.md` §5.3).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project intent and scope
- `.planning/PROJECT.md` — $0 budget, EOD-only, free-data-only constraints; survivorship-bias-accepted-and-disclosed posture
- `.planning/REQUIREMENTS.md` §"Data" — DAT-01..03, DAT-06..09 (the seven Phase 2 requirements) plus traceability table
- `.planning/STATE.md` — accumulated decisions, open calibration questions including "Stooq full-Russell-1000 per-ticker coverage unverified"

### Phase 2 specifics
- `.planning/ROADMAP.md` §"Phase 2: Data Foundation" — phase goal, success criteria 1–5, dependencies (Phase 1)
- `.planning/ROADMAP.md` §"Pitfall-Prevention Mapping" — pitfalls #1 (survivorship), #3 (corp-action integrity), #7 (yfinance silent partial), #9 (free-tier quota), #10 (universe leakage) all map to Phase 2 invariants

### Stack and architecture (research-time decisions)
- `.planning/research/STACK.md` §"Core Technologies" — yfinance >=1.3.0 lower bound, pandas-datareader for Stooq, pandera 0.31.1, requests-cache + tenacity, pyarrow 17.x
- `.planning/research/STACK.md` §"What NOT to Use" — Alpha Vantage as primary OHLCV (25/day quota), `yfinance.download(tickers=[...])` parallel mode, IEX Cloud (discontinued)
- `.planning/research/STACK.md` §"Known Sharp Edges" — Stooq R1000 per-ticker coverage unverified; yfinance batch-mode 429 risk
- `.planning/research/ARCHITECTURE.md` §"Component Responsibilities" — `data/universe`, `data/ohlcv`, `persistence` boundaries; one-way DAG with `data/` as the only network-I/O layer
- `.planning/research/PITFALLS.md` — pitfalls #1, #3, #7, #9, #10 detailed; Phase 2 invariants `assert successful_fetches >= 0.97 * universe_size` and `assert df.index[-1].date() >= today - 4bd`
- `.planning/research/SUMMARY.md` §"Phase 1: Data Foundation" — paraphrased deliverables (note: SUMMARY.md uses an older phase-numbering where Phase 2 was called "Phase 1"; current ROADMAP.md is authoritative)

### Methodology (project-wide context)
- `CLAUDE.md` §5 (Data Sourcing Architecture) — full free-tier matrix; rate limits per source
- `CLAUDE.md` §5.2 (Stock universe) — iShares IWB / IWV CSV endorsement for Russell universes
- `CLAUDE.md` §5.3 (Survivorship bias) — the disclosure-and-mitigate posture, weekly snapshot rationale
- `CLAUDE.md` §5.5 (Corporate Actions) — `auto_adjust=True` semantics, splits-storage rationale (informs D-17/D-18)
- `CLAUDE.md` §5.6 (Caching) — per-ticker Parquet pattern, sequential + sleep + tenacity (informs D-06, D-10)
- `CLAUDE.md` §10 (Repository layout) — `src/screener/data/` and `persistence.py` boundaries

### Phase 1 prior decisions (carry-forward)
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` D-13 — `persistence.py` reserved as the schema seam
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` D-14 — `cli.py` already exposes `refresh-universe` / `refresh-ohlcv` stubs that Phase 2 fills in
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` D-15 — `Settings` extends additively (informs D-20)
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` D-16 — architecture test enforces `data/` is the only layer importing from network deps; new Stooq adapter must respect this contract

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

The Phase 1 scaffold reserves the seams Phase 2 fills:

- `src/screener/data/__init__.py` — module docstring already declares "the ONLY layer permitted to make network I/O ... yfinance, Finnhub, FRED, EDGAR, Stooq, Wikipedia/iShares fetches; writes Parquet/SQLite via `persistence`." Phase 2 adds `universe.py`, `ohlcv.py`, `stooq.py` modules under this directory.
- `src/screener/persistence.py` — module docstring already says "Pandera schemas land in Phase 2 (DAT-09); this Phase 1 placeholder reserves the seam." This file becomes the home of `OhlcvPanelSchema`, `UniverseSchema`, `SplitsSchema`, `read_panel()`, `read_splits()`, `write_ohlcv_atomic()`, `write_universe_atomic()`.
- `src/screener/config.py` — `Settings` class is already wired with `lru_cache` `get_settings()` (Phase 1 WR-01 fix). Phase 2 additively extends with the D-20 fields. `.env.example` mirrors the additions.
- `src/screener/cli.py` — `refresh-universe` and `refresh-ohlcv` subcommands are already stubbed (Phase 1 D-14); Phase 2 replaces the `[stub] ... not yet implemented` log lines with real implementations that delegate to `data/universe.py` and `data/ohlcv.py`.
- `src/screener/obs.py` — structlog JSON-logging baseline already configured. Phase 2 emits structured `fetch_start` / `fetch_success` / `fetch_fail` / `breaker_tripped` / `health_check_*` / `snapshot_written` events through the configured logger.
- `Makefile` — `make data` target is already wired to chain `screener refresh-universe && screener refresh-ohlcv && ...` (Phase 1 D-14). Phase 2 doesn't touch the Makefile.

### Established Patterns

- **Layered DAG (Phase 1 D-16):** `data/` imports nothing from `src/screener/` except `persistence` and `config`. The new `data/universe.py`, `data/ohlcv.py`, `data/stooq.py` modules MUST respect this — no imports from `indicators/`, `signals/`, `regime`, etc. The architecture test (`tests/test_architecture.py`) will catch violations.
- **Pure-function math modules (Phase 1 D-13):** `indicators/` and `signals/` are pure functions; Phase 2 doesn't alter that contract. All disk I/O lives in `data/` (write side) and `persistence.py` (read side).
- **Typed config (Phase 1 D-15):** every parameter the planner introduces is exposed via `Settings`, never hardcoded in business logic. Cached via `get_settings()` (Phase 1 WR-01).
- **Atomic write contract (D-11 here):** new convention; planner extends to any future disk artifact in this layer.

### Integration Points

- **Phase 3 (Indicator Panel) reads via `persistence.read_panel(universe_snapshot_date)`.** That function joins `data/universe/<date>.parquet` with `data/ohlcv/<TICKER>/prices.parquet` for every member ticker, returning a multi-ticker long-format DataFrame validated against `OhlcvPanelSchema`. `research/SUMMARY.md` flags this as the "panel-first from Phase 2 onward" structural decision — RS percentile is cross-sectional and forces the panel API. Phase 2 ships the `read_panel()` function so Phase 3 has the contract to consume.
- **Phase 5 (Backtest Harness) reads the same `data/ohlcv/` and `data/universe/` artifacts.** The backtest layer per Phase 1 D-16 imports only `persistence` + stdlib — no network. Phase 2's atomic-write + schema-enforced contract is what makes the backtest reproducible from frozen snapshots.
- **Phase 6 (Pattern Detection PAT-05) consumes `data/ohlcv/<TICKER>/splits.parquet` to re-derive unadjusted pivots on demand.** The D-17 / D-18 splits ledger is the contract; no API change in Phase 6 — just `persistence.read_splits(ticker)`.
- **Phase 8 (Cron) calls the same Makefile targets.** Phase 8 wraps `make data && make rank && ...` in a GitHub Actions workflow; nothing in Phase 2 should be CI-only or local-only — the same code path runs in both contexts.

</code_context>

<specifics>
## Specific Ideas

- **iShares IWB CSV URL** is `https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund` (subject to BlackRock URL drift; pin in `data/universe.py` with a comment noting verification cadence). Sanity check: header row is non-standard — first ~9 lines are metadata; the actual columns start after a blank line. The parser must skip leading metadata, not assume `header=0`.
- **The literal `.gitignore` carve-outs** must be:
  ```
  data/*
  !data/universe/
  !data/universe/.gitkeep
  !data/splits/
  !data/splits/.gitkeep
  ```
  i.e., ignore `data/` by default, then explicitly un-ignore `data/universe/` and `data/splits/` (D-19).
- **Atomic-write idiom** is the standard `tempfile.NamedTemporaryFile(dir=parent, delete=False, suffix=".tmp")` + `os.replace(tmp.name, target)`. Same filesystem only. Document this contract in `persistence.py`'s `write_*_atomic()` docstrings so it doesn't get re-litigated in later phases.
- **Stooq column normalization** — Stooq returns `Open / High / Low / Close / Volume` (PascalCase, sometimes with a leading `Date` index column). Map to lowercase canonical names in `data/stooq.py` before the pandera validation runs; the panel schema (D-15.1) is lowercase.
- **EDGAR identity** — Phase 2 does NOT call EDGAR (Phase 6 does), but `Settings.EDGAR_IDENTITY` exists from Phase 1 D-15. Phase 2 leaves it alone. No `set_identity()` call yet.
- **No `pandas-ta` use in Phase 2.** No indicators in Phase 2 — pandas-ta-classic stays unused until Phase 3. Schema definitions in `persistence.py` import only `pandera` and `pandas`; no indicator imports.

</specifics>

<deferred>
## Deferred Ideas

These came up during analysis but explicitly belong outside Phase 2:

- **EDGAR `set_identity()` call** — Phase 6 (CAT-04). Settings field exists; Phase 2 doesn't invoke EDGAR.
- **Macro data fetch (`make macro`)** — Phase 3 (DAT-04). FRED + Stooq for SPY/^IXIC/^VIX/A-D line. The Stooq adapter built in Phase 2 (D-14) is the foundation Phase 3 reuses for macro indices.
- **Fundamentals fetch (`make fundamentals`)** — Phase 6 (DAT-05). Finnhub earnings + EPS with the 45-day post-quarter-end "knowable from" lag.
- **Insider Form 4 + 13F EDGAR fetches** — Phase 6 (CAT-03 / part of catalysts).
- **`runs.jsonl` structured-log writer** — Phase 8 (OPS-05). Phase 2 just emits structured events; Phase 8 routes them to a persistent file.
- **Reports/journal commit-to-repo policy** — Phase 7 (journal.sqlite) and Phase 8 (reports/, runs.jsonl). Phase 2's D-19 only addresses universe + splits; reports + journal stay gitignored until their owning phases revisit.
- **Halt-flag metadata** — Phase 6 catalysts. D-08 Option C was the strict-with-halt-flag variant; Phase 6 owns the halt classification when catalysts land.
- **Threading / concurrency knob (`OHLCV_FETCH_WORKERS`)** — Out of v1 entirely (D-10 explicitly rejects it). Sequential + sleep is the contract.
- **`industry`-level granularity (vs `sector`-only)** — Phase 6 makes its own decision when CANSLIM L / industry-RS work needs it. Phase 2 only stores `sector` from iShares (D-04).
- **Wikipedia universe leg** — Dropped (D-01); REQUIREMENTS.md DAT-01 to be edited at next milestone summary to match reality.
- **Initial-backfill resumability** — A 30–60 min one-shot Ctrl-C-able fetch is acceptable for v1. If the backfill crashes mid-run, atomic per-ticker writes (D-11) preserve all completed tickers; re-running picks up where it left off via the incremental-append rule (D-07). No explicit "resume" CLI flag is needed.

</deferred>

---

*Phase: 2-Data Foundation*
*Context gathered: 2026-05-02*
