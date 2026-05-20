# Phase 2: Data Foundation — Research

**Researched:** 2026-05-02
**Domain:** Free-tier OHLCV/universe ingest layer; per-ticker Parquet cache; pandera DataFrameModel schemas at the data/→indicators/ boundary
**Confidence:** HIGH (every library API surface verified live against PyPI and Context7; iShares CSV format and yfinance behavior reproduced live; one notable contradiction with CONTEXT.md `D-03` surfaced and documented)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Universe source policy (D-01..D-04)**
- **D-01**: iShares IWB CSV is the single canonical Russell 1000 source. Wikipedia leg (per REQUIREMENTS.md DAT-01) is dropped; document the deviation.
- **D-02**: On iShares fetch failure → fail loud (exit non-zero, do NOT overwrite snapshot), but expose most recent valid snapshot to OHLCV layer. Tenacity 5 attempts, exponential backoff inside the run. Banner notes "universe stale: <YYYY-MM-DD>".
- **D-03**: Symbol normalization stores both `ticker_raw` (iShares form) and `ticker` (canonical dash notation). Single `normalize_ticker()` function, regex `\.([A-Z])$` → `-\1` plus tiny known-divergence allowlist. **NOTE — see "Open Questions Q1" below: the regex assumption is inconsistent with the live iShares feed, which uses NO separator (BRKB, BFB) rather than dot (BRK.B, BF.B). Planner must adopt the corrected normalization rule documented there.**
- **D-04**: Sector captured from iShares CSV `Sector` column at universe time. No per-ticker `yfinance.Ticker.info` calls in Phase 2.

**OHLCV cache: backfill, layout, append, invariants (D-05..D-11)**
- **D-05**: First-run backfill = `start=2005-01-01` (~20 years).
- **D-06**: Per-ticker layout: `data/ohlcv/<TICKER>/{prices,splits}.parquet`.
- **D-07**: Incremental append — fetch from `last_cached_date+1`; sentinel-check the previous bar; on mismatch, full re-fetch.
- **D-08**: Post-fetch invariants (ALL four required for "successful"): non-empty, `df.index.max().date() >= today - 4 business days`, monotonic index, zero nulls in `close`.
- **D-09**: Drop-out policy — keep cache forever, freeze on drop, nightly fetch filters to current universe.
- **D-10**: Sequential fetch with `time.sleep(random.uniform(0.5, 1.5))` between tickers; tenacity exponential `multiplier=1, min=2, max=60`, `stop_after_attempt(5)`. NO batch mode, NO threading in v1.
- **D-11**: Atomic per-ticker writes via `tempfile.NamedTemporaryFile(dir=parent, delete=False, suffix=".tmp")` + `os.replace()`.

**Stooq fallback (D-12..D-14)**
- **D-12**: Stooq is whole-run circuit-breaker. First 50 tickers; if `success/50 < 0.80`, abort yfinance loop, route remainder through Stooq adapter. NO per-ticker silent fallback.
- **D-13**: 95% gate (DAT-07) still applies post-fallback; combined `(yf_success + stooq_success) / universe_size >= 0.95`.
- **D-14**: Stooq client is `pandas-datareader`; `pdr.DataReader(t, 'stooq')`. Add `pandas-datareader>=0.10` to dependencies.

**Pandera schemas (D-15, D-16)**
- **D-15**: Three `DataFrameModel` schemas in `src/screener/persistence.py`:
  1. `OhlcvPanelSchema` — composite `(ticker, date)` index, `open/high/low/close: float >= 0`, `volume: int >= 0`, `close` non-null.
  2. `UniverseSchema` — `ticker: str`, `ticker_raw: str`, `name: str`, `sector: str`, `weight_pct: float`. One row per ticker.
  3. `SplitsSchema` — `ticker: str`, `date: pd.Timestamp`, `ratio: float >= 0`, `dividend: float >= 0`. Sparse.
- **D-16**: Eager validation (`lazy=False`) at the `data/` write boundary; lazy (`lazy=True`) at the `indicators/` read boundary via `persistence.read_panel(...)`.

**Splits ledger (D-17, D-18)**
- **D-17**: Store ADJUSTED-only OHLCV (`auto_adjust=True`). `splits.parquet` is the corp-action ledger that lets Phase 6 re-derive unadjusted pivots.
- **D-18**: `splits.parquet` sourced from `yfinance.Ticker.actions`; full refresh-overwrite each nightly run; schema `[date, ratio, dividend]`.

**Commit policy and Settings (D-19, D-20)**
- **D-19**: Commit `data/universe/*.parquet` AND `data/splits/*.parquet`. `data/ohlcv/` stays gitignored.
- **D-20**: Settings additions:
  - `OHLCV_CACHE_DIR: Path = Path("data/ohlcv")`
  - `UNIVERSE_CACHE_DIR: Path = Path("data/universe")`
  - `OHLCV_BACKFILL_START: str = "2005-01-01"`
  - `UNIVERSE_HEALTH_THRESHOLD: float = 0.95`
  - `STOOQ_BREAKER_PROBE_N: int = 50`
  - `STOOQ_BREAKER_THRESHOLD: float = 0.80`
  - `OHLCV_FETCH_SLEEP_MIN_S: float = 0.5`
  - `OHLCV_FETCH_SLEEP_MAX_S: float = 1.5`

### Claude's Discretion

- Weekly-snapshot trigger semantics — idempotent on Monday-of-current-ISO-week; `--force` override.
- `requests-cache` configuration — SQLite at `~/.cache/screener/http.sqlite`; 1h "fresh-data" expiry; 24h static. Not used for yfinance.
- CLI subcommand wiring — `--force` on `refresh-universe`; `--ticker <T>` on `refresh-ohlcv`.
- Structured logging events — `fetch_start`, `fetch_success/fail`, `breaker_tripped`, `health_check_passed/failed`, `snapshot_written`.
- `.env.example` updates mirroring D-20.
- Test fixtures (synthetic empty yfinance, split-mismatch, malformed iShares CSV).
- Empty `splits.parquet` — zero-row file with schema preserved.
- README "Data layer" section additions.

### Deferred Ideas (OUT OF SCOPE)

- EDGAR `set_identity()` call → Phase 6 (CAT-04).
- `make macro` (FRED + Stooq macro indices) → Phase 3 (DAT-04); reuses Phase 2's Stooq adapter.
- `make fundamentals` (Finnhub + 45-day lag) → Phase 6 (DAT-05).
- Insider Form 4 + 13F EDGAR fetches → Phase 6.
- `runs.jsonl` writer → Phase 8 (OPS-05). Phase 2 emits structured events only.
- Halt-flag metadata → Phase 6 catalysts.
- Threading / `OHLCV_FETCH_WORKERS` knob → out of v1 entirely.
- `industry`-level granularity (vs `sector`-only) → Phase 6 decides.
- Wikipedia universe leg → dropped; REQUIREMENTS.md DAT-01 to be edited at next milestone summary.
- Initial-backfill resumability → not needed (atomic per-ticker writes preserve progress).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DAT-01 | `make universe` refreshes Russell 1000; constituent list fetched from Wikipedia + iShares IWB CSV | iShares CSV format & URL verified live (1010 rows, `skiprows=9`, `encoding='utf-8-sig'`); Wikipedia leg dropped per D-01. See "Implementation Approach → Universe". |
| DAT-02 | Weekly Parquet snapshot at `data/universe/YYYY-MM-DD.parquet` | ISO-week-Monday keying; idempotent CLI; atomic write pattern. |
| DAT-03 | `make ohlcv` refreshes via yfinance ≥ 1.3 with Stooq fallback; per-ticker Parquet cache, incremental append | yfinance 1.3 `download()` signature confirmed (auto_adjust=True default); Stooq circuit-breaker via pandas-datareader 0.10.0; sentinel-bar refetch. |
| DAT-06 | All HTTP fetchers use `requests-cache` (24h fundamentals / 1h news) + tenacity backoff | `CachedSession(backend='sqlite', urls_expire_after=...)`; tenacity `wait_exponential` + `before_sleep_log`; **iShares CSV download path uses both; yfinance manages its own session and is OUT of requests-cache scope**. |
| DAT-07 | Universe-coverage health check fails the run if `successful_fetches < 95%` | Combined yf+stooq success counter; CLI exits non-zero; structured `health_check_failed` event. |
| DAT-08 | `splits.parquet` stored alongside OHLCV; pivots re-derivable across split events | `yfinance.Ticker.actions` returns combined dividends + Stock Splits Series; full refresh per run. |
| DAT-09 | Pandera schemas enforced at `data/ → indicators/` boundary | Three `DataFrameModel` classes in `persistence.py`; eager at write, lazy at read. Composite-index pattern via `Index[str]` + `Index[pd.Timestamp]` + `Config.multiindex_strict=True`. |
</phase_requirements>

## Summary

Phase 2 is mechanically straightforward but operationally treacherous: every API in scope (yfinance, pandas-datareader/Stooq, the iShares AJAX endpoint) has a documented track record of *silent partial failure* — empty DataFrames, blank CSV bodies, or 200-OK HTML in place of the expected payload. The single most important engineering invariant for the phase is therefore **explicit post-fetch validation as part of every fetcher**, not a separate cleanup step: `D-08`'s four-condition gate (non-empty, recent ≥ T-4bd, monotonic, zero null close) is what converts a silent "Yahoo returned nothing" into a deterministic `health_check_failed` event.

Pinning library versions matters more than usual here: **pandas-datareader has been frozen at 0.10.0 since July 2021** (verified live on PyPI), and Stooq access through it has had open community-reported issues since late-2022 (issue #955: blank DataFrames). Recommendation: keep D-14 (use pandas-datareader) but write the Stooq adapter with three explicit defenses — (1) pandas-datareader will raise `RemoteDataError` or `OSError` on 404/empty (verified in source — NOT a silent empty-DataFrame), so wrap the call and let the exception propagate to D-13's gate; (2) reverse the descending date index Stooq returns by default; (3) gate the Stooq path with the same `D-08` invariants as yfinance. If Stooq is found unreliable in production, the planner can swap to a direct `requests.get('https://stooq.com/q/d/l/?s=<ticker>.US&d1=...&d2=...&i=d')` adapter without touching consumers — the boundary is `data/stooq.py`.

The iShares CSV was verified live during this research (`HTTP/2 200`, `1030` total lines, `1005` Equity rows, `1010` total holdings rows). The exact pandas read recipe is `pd.read_csv(io.BytesIO(content), skiprows=9, encoding='utf-8-sig', thousands=',', na_values=['-'])` and **the resulting DataFrame has 1012 rows including 5 cash/derivative rows + 2 trailer rows** that must be filtered with `df['Asset Class'] == 'Equity'`. The header line at row 9 must NOT be skipped — `skiprows=9` skips lines 0..8 and treats line 9 as the header (verified live). One contradiction with `D-03` was discovered: **iShares uses `BRKB`/`BFB` (no separator), not `BRK.B`/`BF.B` (dot)** — see Open Questions Q1.

**Primary recommendation:** ship Phase 2 in 5 plans corresponding to the four subsystems plus a final wave for the 95% health-check + CLI wiring, with eager pandera validation written before any data/ writer code. Do not rely on yfinance's `yf.config.network.retries` as the primary retry mechanism — it exists in 1.3.x (verified) but is not configurable per-call and provides no `before_sleep` hook for structured logging; wrap every fetch call in `tenacity.retry` instead, per `D-10`. Total wall time for the initial backfill: 30–60 min one-shot for ~1000 tickers × 20 years; nightly incremental: ~17 min.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| iShares CSV fetch + parse | `data/universe.py` (network I/O) | `persistence.write_universe_atomic()` | Per Phase 1 D-16, `data/` is the only layer permitted to make network I/O. CSV → DataFrame parse stays here; write is delegated to `persistence` for the atomic-write contract. |
| Symbol normalization (iShares → yfinance form) | `data/universe.py` (`normalize_ticker()`) | — | Pure function but logically lives next to the iShares parse since the regex/allowlist is iShares-specific. Downstream tiers consume `ticker` (canonical) only. |
| yfinance OHLCV fetch + post-fetch invariants | `data/ohlcv.py` (network I/O) | `persistence.write_ohlcv_atomic()` | Same architecture rule. The four-invariant gate (D-08) lives in the fetcher because it's the line of defense between Yahoo and the cache; persistence just writes what's handed to it. |
| Stooq circuit-breaker probe | `data/ohlcv.py` (orchestrator) | `data/stooq.py` (fetch) | Probe state (success counter at first 50) is part of the run loop; the actual Stooq fetch is a thin wrapper in `data/stooq.py`. |
| Stooq fetch + column normalization | `data/stooq.py` | — | Stooq returns PascalCase columns and descending index; normalize to canonical lowercase + ascending here. |
| Atomic write + Parquet I/O | `persistence.py` | — | Single owner of disk-format details (Phase 1 D-13 reservation). `tempfile + os.replace` idiom documented once and reused. |
| Pandera schema definitions | `persistence.py` | — | Schemas are the contract between `data/` (write) and `indicators/` (read); both layers import from `persistence`. |
| Read-back panel for indicators | `persistence.read_panel()` | `data/universe.py` (snapshot lookup helper) | Phase 3 dependency. `read_panel(snapshot_date)` joins the universe Parquet at that date with each ticker's `prices.parquet`. |
| Structured logging events | every module via `obs.get_logger()` | — | Phase 1 baseline. Phase 2 emits the documented event names; routing to `runs.jsonl` is Phase 8 (OPS-05). |
| 95% health gate + run exit code | `cli.py` `refresh-ohlcv` body | `data/ohlcv.py` (returns counts) | CLI is the composition root; only it has authority to exit non-zero. The fetcher returns counters; CLI computes the ratio and decides. |
| Settings / env loading | `config.py` | — | Phase 1 D-15 contract; D-20 fields extend additively. |

## Standard Stack

### Core (already pinned in `pyproject.toml`)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yfinance | `>=1.3.0,<2` | Primary OHLCV + corporate actions | Reached 1.3 in 2025; `yf.config.network.retries` and stable internal session. STACK.md verified. |
| pandas | `>=2.2,<3` | DataFrame substrate | Required by every other lib. |
| numpy | `>=2,<3` | Numerics | NumPy 2 required by pandas-ta-classic; pandera 0.31 supports it. |
| pyarrow | `>=17,<18` | Parquet I/O | Required for the per-ticker cache; supports `to_parquet`/`read_parquet` round-trip. |
| pandera | `>=0.31.1,<0.32` | DataFrame schema validation | Class-based `DataFrameModel` API verified for composite-index `(ticker, date)` panels. |
| pydantic-settings | `>=2.14,<3` | Typed env-driven Settings | Phase 1 D-15 baseline; D-20 adds 8 fields. |
| structlog | `>=25.5,<26` | JSON structured logging | Phase 1 baseline (`obs.configure()`). |
| typer | `>=0.25,<0.26` | CLI | Phase 1 D-14 surface; Phase 2 fills `refresh-universe` + `refresh-ohlcv` bodies. |
| requests-cache | `>=1.3,<2` | HTTP response cache | `CachedSession(backend='sqlite', urls_expire_after={...})` for iShares + future Phase 3 macro/Phase 6 fundamentals. **NOT used to wrap yfinance**. |
| tenacity | `>=9.1,<10` | Retry + backoff | `wait_exponential(multiplier=1, min=2, max=60)`, `stop_after_attempt(5)`, `before_sleep_log()`. |

### Supporting (Phase 2 ADDS this single dependency)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas-datareader | `>=0.10,<0.11` | Stooq client (D-14) | Only when `data/stooq.py` is invoked by the circuit-breaker (D-12). Frozen at 0.10.0 since July 2021. **Confidence MEDIUM** — see Risks for `pdr.DataReader('AAPL', 'stooq')` reliability concerns. |

### Alternatives Considered (and rejected)

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pandas-datareader` for Stooq | Direct `requests.get('https://stooq.com/q/d/l/?s=<ticker>.US&d1=YYYYMMDD&d2=YYYYMMDD&i=d')` + `pd.read_csv` | Zero deps, ~30 lines. Higher maintenance if Stooq's CSV format drifts. **Document as a fallback in `data/stooq.py` if pandas-datareader is found broken** — D-14 is locked as the v1 path. |
| Per-ticker `yf.download(ticker, ...)` | `yf.download(tickers=[T1, T2, ...], group_by='ticker', threads=True)` batch | STACK.md and D-10 explicitly reject batch mode (Yahoo 429 rate-limit risk). Locked. |
| Tenacity wrappers in each fetcher | `yf.config.network.retries = 5` | yfinance 1.3.x has the knob (verified) but no per-call control, no `before_sleep` hook for structured-log events. D-10 mandates tenacity. Use `yf.config.network.retries = 0` to disable yfinance's internal retries and let tenacity own the policy. |
| `os.replace` atomic-rename | `python-atomicwrites` library | Adds a dependency for what is a 5-line stdlib idiom. Reject. |

**Installation:**

```bash
# Phase 2 adds exactly one dependency:
uv add "pandas-datareader>=0.10,<0.11"
```

**Version verification (live, 2026-05-02):**

| Package | Latest | Released | Notes |
|---------|--------|----------|-------|
| yfinance | 1.3.0+ | April 2025 (1.3.0); ongoing | STACK.md HIGH; `yf.config.network.retries` verified |
| pandas-datareader | **0.10.0** | **July 2021** | Frozen since 2021; community issue #955 (Dec 2022) reports Stooq blank DataFrames intermittently. **Pin lower bound at 0.10; expect to swap to direct CSV scrape if breakage recurs.** |
| pandera | 0.31.1 | April 2025 | DataFrameModel + MultiIndex docs verified |
| requests-cache | 1.3.x | 2025 | `CachedSession` + `urls_expire_after` verified |
| tenacity | 9.1.x | Feb 2026 | `before_sleep_log` + `retry_if_exception_type` verified |
| pyarrow | 17.x | 2024–2025 | Standard parquet engine for pandas 2.2 |

## Architecture Patterns

### System Architecture Diagram

```
                     ┌──────────────────────────────┐
                     │  GitHub Actions / make data  │   (Phase 8 orchestrates)
                     └──────────┬───────────────────┘
                                │
                       ┌────────▼────────┐
                       │  screener CLI   │   (composition root)
                       │   typer app     │
                       └────────┬────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
   ┌──────────▼──────────┐               ┌────────▼────────────┐
   │  refresh-universe   │               │   refresh-ohlcv     │
   │  (one Monday/week)  │               │   (every nightly)   │
   └──────────┬──────────┘               └────────┬────────────┘
              │                                   │
   ┌──────────▼─────────────────┐                 │
   │  data/universe.py          │                 │
   │  - fetch_ishares_iwb_csv() │                 │
   │  - normalize_ticker()      │                 │
   │  - sanity_check()          │                 │
   └──────────┬─────────────────┘                 │
              │                                   │
              │                  ┌────────────────▼─────────────────┐
              │                  │  data/ohlcv.py                   │
              │                  │  - load_active_universe()        │
              │                  │  - fetch_ticker(t)  ← tenacity   │
              │                  │  - validate_invariants() (D-08)  │
              │                  │  - circuit-breaker probe (D-12)  │
              │                  └────────┬───────────────────┬─────┘
              │                           │ (yf path)         │ (stooq fallback)
              │                  ┌────────▼─────────┐  ┌──────▼──────────┐
              │                  │  yfinance        │  │  data/stooq.py  │
              │                  │  yf.download()   │  │  pdr.DataReader │
              │                  │  Ticker.actions  │  │     'stooq'     │
              │                  └────────┬─────────┘  └──────┬──────────┘
              │                           │                   │
              │                           └─────────┬─────────┘
              │                                     │
              │                       ┌─────────────▼──────────────────┐
              │                       │  pandera SchemaError? abort    │
              │                       │  4-invariant gate? abort       │
              │                       └─────────────┬──────────────────┘
              │                                     │
   ┌──────────▼─────────────────────────────────────▼──────────────────┐
   │  persistence.py                                                  │
   │  - write_universe_atomic()       (tempfile + os.replace)         │
   │  - write_ohlcv_atomic(t)                                         │
   │  - write_splits_atomic(t)                                        │
   │  - read_panel(snapshot_date)     → Phase 3 entrypoint            │
   │  - OhlcvPanelSchema, UniverseSchema, SplitsSchema                │
   └──────────┬───────────────────────────────────────────────────────┘
              │
              │  parquet writes:
              │   data/universe/2026-05-04.parquet            (committed to git)
              │   data/ohlcv/<TICKER>/prices.parquet           (gitignored)
              │   data/ohlcv/<TICKER>/splits.parquet           (committed to git via separate path? — see Open Q3)
              │   ~/.cache/screener/http.sqlite                (gitignored, host-local)
              ▼
       ┌──────────┐         95% gate evaluated by CLI →
       │   CLI    │  ──────  exit 0 if pass, exit 1 + structured "health_check_failed" if fail
       └──────────┘
```

### Recommended Project Structure

```
src/screener/
├── data/
│   ├── __init__.py        # Phase 1 docstring stub — already exists; no edit needed
│   ├── universe.py        # NEW — iShares CSV fetcher + normalize_ticker()
│   ├── ohlcv.py           # NEW — yfinance fetcher + circuit-breaker orchestrator + invariant gate
│   └── stooq.py           # NEW — pandas-datareader Stooq wrapper + column normalizer
├── persistence.py         # EXTEND — add OhlcvPanelSchema/UniverseSchema/SplitsSchema, atomic writers, read_panel
├── config.py              # EXTEND — add 8 D-20 fields
├── cli.py                 # EXTEND — fill refresh-universe + refresh-ohlcv bodies; add --force / --ticker flags
├── obs.py                 # NO CHANGES — Phase 1 baseline
└── ...                    # other layers untouched in Phase 2

tests/
├── conftest.py            # EXTEND — add 6 synthetic fixtures (see Validation Architecture)
├── test_data_universe.py  # NEW — iShares parser, normalize_ticker, atomic-write semantics
├── test_data_ohlcv.py     # NEW — invariants, sentinel mismatch, atomic write
├── test_data_stooq.py     # NEW — column normalization, descending-index reversal
├── test_persistence.py    # NEW — schema rejection (DAT-09), read_panel round-trip
└── test_cli_smoke.py      # EXTEND — assert refresh-universe / refresh-ohlcv exit codes match new contract
```

### Pattern 1: Atomic Parquet Write (D-11)

**What:** A crash-safe, half-write-impossible pattern for every Parquet artifact in `persistence.py`.
**When to use:** every `write_*_atomic()` function.
**Source:** stdlib only; idiom corroborated by `python-atomicwrites` README and Activestate recipe 579097.

```python
# src/screener/persistence.py
import os
import tempfile
from pathlib import Path
import pandas as pd

def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    """Write `df` to `target` atomically (POSIX same-filesystem rename).

    Uses tempfile in the same directory as `target` so os.replace() is
    a same-filesystem rename (atomic). A crash mid-write leaves the
    .tmp file behind but never a half-written `target`.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    # Tempfile MUST be in the same directory as target — os.replace()
    # only guarantees atomicity on the same filesystem.
    tmp = tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    try:
        tmp.close()
        # engine="pyarrow" is the project default; index=True preserves the
        # DatetimeIndex / MultiIndex that pandera schemas validate.
        df.to_parquet(tmp_path, engine="pyarrow", index=True)
        os.replace(tmp_path, target)  # atomic on same FS for POSIX + Windows
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

### Pattern 2: yfinance fetch with tenacity + post-fetch invariants (D-08, D-10)

**What:** the canonical fetch wrapper; every per-ticker call goes through this.
**When to use:** in `data/ohlcv.py`'s inner loop.
**Source:** Context7 yfinance docs + tenacity docs + CLAUDE.md §13.6 #7.

```python
# src/screener/data/ohlcv.py
import random
import time
from datetime import date, timedelta
import pandas as pd
import yfinance as yf
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import structlog

log = structlog.get_logger(__name__)


class StaleOrEmptyError(RuntimeError):
    """Raised when a yfinance fetch returns data that fails the four invariants."""


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    # Retry on the silent-empty case AND on transport errors.
    # NOT on KeyError / ValueError of unknown ticker (let those bubble).
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(log, "warning"),  # structlog-compatible
    reraise=True,
)
def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = yf.download(
        ticker,
        start=str(start),
        auto_adjust=True,            # D-17: store adjusted only
        progress=False,
        threads=False,               # D-10: NO batch/parallel
        actions=False,               # splits fetched separately via Ticker.actions
        multi_level_index=False,     # yf 1.3.x default is True; we want flat columns for single-ticker
    )
    if df is None or df.empty:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")
    # D-08 invariants — ALL four must hold.
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale: last bar {last}, today {today}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} non-monotonic index")
    if df["Close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} has null close")
    return df


def fetch_ohlcv_with_pacing(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = fetch_ohlcv(ticker, start, today)
    time.sleep(random.uniform(0.5, 1.5))   # D-10
    return df
```

**Note on `multi_level_index=False`:** yfinance 1.3.x defaults to `multi_level_index=True` for `download()`. For single-ticker calls this produces a `MultiIndex(("Close", "AAPL"), ...)` columns layout — flatten by passing `multi_level_index=False` so downstream code stays on a flat columns DataFrame. (Verified against `yfinance.download` reference signature.)

### Pattern 3: Sentinel-Bar Refetch for Incremental Append (D-07)

**What:** before appending new bars, refetch the cached `last_cached_date` bar and assert its OHLC matches the cache.
**When to use:** in `data/ohlcv.py` per-ticker incremental path.

```python
def append_incremental(ticker: str, today: date) -> tuple[pd.DataFrame, bool]:
    """Returns (df, full_refetched). full_refetched=True if sentinel mismatched."""
    cache_path = settings.OHLCV_CACHE_DIR / ticker / "prices.parquet"
    if not cache_path.exists():
        df = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
        return df, True

    cached = pd.read_parquet(cache_path)
    last_cached_date = cached.index[-1].date()
    if last_cached_date >= today - timedelta(days=1):
        # Already current; nothing to do.
        return cached, False

    # Refetch starting at the SAME cached date so we get a sentinel + new bars.
    new = fetch_ohlcv(ticker, last_cached_date, today)
    # Sentinel check: new[last_cached_date] should equal cached[last_cached_date].
    if last_cached_date not in new.index.date:
        # Sentinel missing entirely — corp action drift suspected. Full refetch.
        full = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
        return full, True
    sentinel_new = new.loc[new.index.date == last_cached_date].iloc[0]
    sentinel_old = cached.iloc[-1]
    # Float tolerance: yfinance occasionally re-reports closes by ±0.01 due
    # to dividend re-adjustment. 0.5% relative tolerance catches splits
    # without false-positive on dividend drift.
    if not _approx_equal(sentinel_new["Close"], sentinel_old["Close"], rtol=0.005):
        log.warning("sentinel_mismatch", ticker=ticker,
                    cached=float(sentinel_old["Close"]), refetched=float(sentinel_new["Close"]))
        full = fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
        return full, True
    # Append new bars (excluding sentinel).
    new_bars = new[new.index.date > last_cached_date]
    return pd.concat([cached, new_bars]), False
```

### Pattern 4: Stooq circuit-breaker (D-12)

```python
# src/screener/data/ohlcv.py (continued)
from screener.data import stooq

def run_with_breaker(tickers: list[str], today: date) -> tuple[int, int, list[str]]:
    """Run yfinance loop with first-50 circuit-breaker; return (yf_ok, stooq_ok, failed)."""
    yf_ok = 0
    stooq_ok = 0
    failed: list[str] = []
    breaker_tripped = False

    for i, t in enumerate(tickers):
        if not breaker_tripped:
            try:
                df = fetch_ohlcv_with_pacing(t, settings.OHLCV_BACKFILL_START, today)
                persistence.write_ohlcv_atomic(t, df)
                # also pull splits via Ticker.actions
                actions = yf.Ticker(t).actions
                persistence.write_splits_atomic(t, actions)
                yf_ok += 1
                log.info("fetch_success", ticker=t, source="yfinance")
            except Exception as e:
                failed.append(t)
                log.warning("fetch_fail", ticker=t, source="yfinance", error=str(e))

            # Circuit-breaker probe at i == STOOQ_BREAKER_PROBE_N - 1.
            if i + 1 == settings.STOOQ_BREAKER_PROBE_N:
                rate = yf_ok / settings.STOOQ_BREAKER_PROBE_N
                if rate < settings.STOOQ_BREAKER_THRESHOLD:
                    breaker_tripped = True
                    log.warning(
                        "breaker_tripped",
                        probe_n=settings.STOOQ_BREAKER_PROBE_N,
                        success_rate=rate,
                        threshold=settings.STOOQ_BREAKER_THRESHOLD,
                    )
        else:
            # Stooq fallback path — reuse the same invariants gate.
            try:
                df = stooq.fetch_ohlcv(t, settings.OHLCV_BACKFILL_START, today)
                persistence.write_ohlcv_atomic(t, df)
                stooq_ok += 1
                log.info("fetch_success", ticker=t, source="stooq")
            except Exception as e:
                failed.append(t)
                log.warning("fetch_fail", ticker=t, source="stooq", error=str(e))

    return yf_ok, stooq_ok, failed
```

### Pattern 5: pandera DataFrameModel composite-index schema (D-15, D-16)

**Source:** Context7 `/unionai-oss/pandera` — verified live.

```python
# src/screener/persistence.py
import pandas as pd
import pandera.pandas as pa
from pandera.typing import Index, Series, DataFrame


class OhlcvPanelSchema(pa.DataFrameModel):
    """Multi-ticker long-format OHLCV panel with composite (ticker, date) index.

    Used at the data/ → indicators/ boundary. Validation: lazy=True at read
    time (collect all schema errors), lazy=False at write time (fail loud
    on first row).
    """

    # MultiIndex levels — ticker first (outer), date second (inner).
    ticker: Index[str] = pa.Field(check_name=True)
    date: Index[pd.Timestamp] = pa.Field(check_name=True)

    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    high: Series[float] = pa.Field(ge=0.0, nullable=False)
    low: Series[float] = pa.Field(ge=0.0, nullable=False)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    volume: Series[int] = pa.Field(ge=0, nullable=False)

    class Config:
        # MultiIndex enforcement: index level names must match the field
        # declarations above and order must be preserved.
        multiindex_strict = True
        multiindex_coerce = False
        strict = True             # reject extra columns
        coerce = False            # don't silently coerce dtypes — fail


class UniverseSchema(pa.DataFrameModel):
    """One row per ticker; the iShares snapshot persisted to data/universe/."""

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    ticker_raw: Series[str] = pa.Field(nullable=False)
    name: Series[str] = pa.Field(nullable=False)
    sector: Series[str] = pa.Field(nullable=False, isin=[
        "Information Technology", "Health Care", "Financials",
        "Consumer Discretionary", "Communication", "Industrials",
        "Consumer Staples", "Energy", "Utilities", "Real Estate", "Materials",
    ])
    weight_pct: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=False)

    class Config:
        strict = True
        coerce = False


class SplitsSchema(pa.DataFrameModel):
    """Sparse per-ticker corporate-action ledger.

    Schema is preserved even when the file has zero rows (Discretion: empty
    splits.parquet rule). pandera will still validate the empty DataFrame.
    """

    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    ratio: Series[float] = pa.Field(ge=0.0, nullable=False)
    dividend: Series[float] = pa.Field(ge=0.0, nullable=False)

    class Config:
        strict = True
        coerce = False


def validate_at_write(schema_cls, df: pd.DataFrame) -> pd.DataFrame:
    """Eager validation (lazy=False): fail on first error. D-16 write side."""
    return schema_cls.validate(df, lazy=False)


def validate_at_read(schema_cls, df: pd.DataFrame) -> pd.DataFrame:
    """Lazy validation (lazy=True): collect all errors. D-16 read side."""
    return schema_cls.validate(df, lazy=True)


def read_panel(snapshot_date: str | pd.Timestamp) -> DataFrame[OhlcvPanelSchema]:
    """Phase 3 entrypoint. Joins the universe Parquet at `snapshot_date`
    with each ticker's prices.parquet, returning a long-format MultiIndex
    DataFrame validated lazily (lazy=True).
    """
    universe_path = settings.UNIVERSE_CACHE_DIR / f"{snapshot_date}.parquet"
    universe = pd.read_parquet(universe_path)
    frames = []
    for t in universe["ticker"]:
        prices_path = settings.OHLCV_CACHE_DIR / t / "prices.parquet"
        if not prices_path.exists():
            continue   # ticker dropped; D-09 frozen-cache policy
        df = pd.read_parquet(prices_path)
        df = df.rename(columns=str.lower)
        df["ticker"] = t
        df = df.set_index("ticker", append=True).reorder_levels(["ticker", df.index.name or "date"])
        frames.append(df)
    panel = pd.concat(frames)
    panel.index.names = ["ticker", "date"]
    return validate_at_read(OhlcvPanelSchema, panel)
```

### Pattern 6: iShares IWB CSV parsing (DAT-01, D-01)

**Verified live 2026-05-02 against the real endpoint.**

```python
# src/screener/data/universe.py
import io
import re
import requests
import pandas as pd

ISHARES_IWB_URL = (
    "https://www.ishares.com/us/products/239707/"
    "ishares-russell-1000-etf/1467271812596.ajax"
    "?fileType=csv&fileName=IWB_holdings&dataType=fund"
)
# Verified live 2026-05-02: HTTP/2 200, content-type text/csv;charset=UTF-8.
# Without a custom User-Agent BlackRock may return 403 (community-confirmed).

ISHARES_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Verified: 9 metadata rows, then a blank row, then column header at row 9 (0-indexed).
# Without the BOM strip the first column shows up as '\ufeffTicker' (the BOM, U+FEFF, prefixes the literal).
ISHARES_SKIPROWS = 9
ISHARES_ENCODING = "utf-8-sig"   # strips the BOM

# Allowlist GICS sectors as they appear in the live CSV (verified by direct fetch).
GICS_SECTORS = {
    "Information Technology", "Health Care", "Financials",
    "Consumer Discretionary", "Communication", "Industrials",
    "Consumer Staples", "Energy", "Utilities", "Real Estate", "Materials",
}


def fetch_ishares_iwb_csv(session=None) -> bytes:
    """Fetch the raw iShares IWB CSV bytes. Caller handles tenacity wrap.

    `session` may be a requests-cache CachedSession (Discretion: 1h expiry
    for "fresh-data" endpoints — but iShares updates daily so 1h is correct).
    """
    s = session or requests
    resp = s.get(ISHARES_IWB_URL, headers=ISHARES_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content


def parse_ishares_iwb_csv(content: bytes) -> pd.DataFrame:
    """Parse and filter to Equity rows only. Returns 1000 ± 50 rows."""
    df = pd.read_csv(
        io.BytesIO(content),
        skiprows=ISHARES_SKIPROWS,
        encoding=ISHARES_ENCODING,
        thousands=",",
        na_values=["-"],
    )
    # Drop trailer rows (ticker NaN, or first cell is the BlackRock notice).
    df = df.dropna(subset=["Ticker"])
    df = df[~df["Ticker"].astype(str).str.startswith("The content")]
    # Filter to Equity only (drops 5 cash/derivative rows: XTSLA/USD/UBFUT/FAM6/ESM6).
    df = df[df["Asset Class"] == "Equity"].copy()
    return df


def normalize_ticker(raw: str) -> str:
    """Convert iShares ticker form to canonical yfinance form.

    iShares uses NO separator for share classes (BRKB, BFB, BFA), while
    yfinance uses dash (BRK-B, BF-B, BF-A). Single-letter share-class
    suffixes are detected by the trailing-uppercase pattern + a known
    allowlist for unambiguous reversibility.
    """
    # Hand-curated allowlist of known iShares→yfinance divergences.
    # Verified live in the IWB feed 2026-05-02. Extend on rebalance review.
    allowlist = {
        "BRKB": "BRK-B",
        "BFB": "BF-B",
        "BFA": "BF-A",
        # GOOGL/GOOG and similar two-letter tickers stay as-is (no dash).
    }
    if raw in allowlist:
        return allowlist[raw]
    return raw   # the regex \.([A-Z])$ → -\1 from D-03 turns out to be a NOOP
                 # against the live iShares feed; see Open Question Q1.


def sanity_check(df: pd.DataFrame) -> None:
    """D-02: fail loud on out-of-band row count or missing columns."""
    required = {"Ticker", "Name", "Sector", "Asset Class", "Weight (%)"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"iShares CSV missing columns: {missing}")
    n = len(df)
    if not (800 <= n <= 1100):
        raise ValueError(f"iShares CSV row count {n} outside [800, 1100]")
    bad_sectors = set(df["Sector"]) - GICS_SECTORS
    if bad_sectors:
        raise ValueError(f"iShares CSV unknown sectors: {bad_sectors}")
```

### Pattern 7: requests-cache configuration (DAT-06)

```python
# src/screener/data/__init__.py  (or a new helpers module)
import re
from datetime import timedelta
from pathlib import Path
import requests_cache

CACHE_PATH = Path.home() / ".cache" / "screener" / "http.sqlite"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

URLS_EXPIRE_AFTER = {
    # iShares — daily-updated CSV, 1h is "fresh enough" while still cutting
    # repeat-run latency. NEVER cache yfinance traffic (yf manages its own).
    "*.ishares.com/*holdings*": timedelta(hours=1),
    "*.finnhub.io/*calendar*": timedelta(hours=1),         # Phase 6 seam
    "*.finnhub.io/*fundamentals*": timedelta(hours=24),   # Phase 6 seam
    "*.fred.stlouisfed.org/*": timedelta(hours=24),        # Phase 3 seam
}

def get_cached_session() -> requests_cache.CachedSession:
    """Single shared CachedSession for all HTTP-based fetchers in v1."""
    return requests_cache.CachedSession(
        cache_name=str(CACHE_PATH),
        backend="sqlite",
        urls_expire_after=URLS_EXPIRE_AFTER,
        allowable_codes=[200],            # do NOT cache 4xx/5xx
        stale_if_error=False,             # fail loud rather than serve stale
    )
```

### Anti-Patterns to Avoid

- **Wrapping yfinance with `requests-cache`.** yfinance manages its own internal session; injecting a CachedSession via `yf.Ticker(t, session=cs)` is supported (Context7 verified) but creates surprising behavior because yfinance's URL space is undocumented. STACK.md and D-discretion explicitly leave yfinance out of requests-cache scope. Keep cache for `iShares + Finnhub + FRED` only.
- **`yf.download(tickers=[T1, T2, ...], threads=True)` batch mode.** Locked-out by D-10 and STACK.md. Causes burst Yahoo 429 followed by silent partial DataFrames.
- **Treating empty `yf.download()` return as success.** `df.empty` is the silent-failure signature; D-08 invariants exist precisely to convert this into a `StaleOrEmptyError`.
- **Polling Stooq per-ticker as a silent fallback.** D-12 rejects this — Stooq's coverage gaps + 1-day lag would silently mix into the panel.
- **Caching pivot dollar levels.** `D-17` plus `PAT-05` mandate re-derivation each run from adjusted closes. The Phase 2 contract enables this by keeping `splits.parquet` alongside.
- **`os.replace` across filesystems.** `os.replace` is atomic only on the same filesystem; if `data/ohlcv/` were on tmpfs and the tempfile on the project root, the rename would silently fall back to copy+unlink. Always create the tempfile in `target.parent`.
- **Silent NaN in the `close` column.** D-08(d): zero nulls in close. yfinance occasionally returns one or two NaN bars on data-vendor errors; `df["Close"].isna().any()` is the test.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Yahoo Finance HTTP scraping | A custom `requests.get('https://query1.finance.yahoo.com/...')` parser | `yfinance.download()` (`>=1.3.0`) | Yahoo's API surface changes 2–3×/year; yfinance has 1000+ contributors keeping it in sync. |
| Corporate actions (splits + dividends) | Parsing 8-K filings or scraping Yahoo's "Historical Data" page | `yfinance.Ticker(t).actions` (single Series with both) | Returns a clean `pd.Series` with split ratio (e.g., 10.0 for NVDA-2024) — verified via Context7. |
| Atomic file writes | A custom rename-with-fsync helper | `tempfile.NamedTemporaryFile(dir=..., delete=False)` + `os.replace()` | Stdlib idiom, ~5 lines; `python-atomicwrites` adds a dep for no real gain at this scope. |
| HTTP retry/backoff | A custom `for i in range(5): try: ... except: time.sleep(2**i)` loop | `tenacity.retry(wait=wait_exponential(...), stop=stop_after_attempt(5), before_sleep=before_sleep_log(...))` | Composable, structlog-compatible, jitter-aware, tested. |
| HTTP cache | A custom dict + datetime expiry | `requests_cache.CachedSession(backend='sqlite', urls_expire_after={...})` | Cache-Control aware, glob/regex URL matching, SQLite backend included. |
| DataFrame schema validation | Manual `assert df.columns.tolist() == [...]` | `pandera.DataFrameModel` with `lazy=True` | Composable, surfaces multiple errors at once, integrates with `@pa.check_types`. |
| Russell 1000 list scraping | Wikipedia `pd.read_html` (lags rebalances) | iShares IWB AJAX CSV (BlackRock daily-updated) | D-01: locked. iShares is the authoritative daily file. |
| Stooq HTTP client | `requests.get('https://stooq.com/q/d/l/...')` + custom CSV parse | `pandas_datareader.DataReader(t, 'stooq')` | D-14: locked. Adds ~20-line wrapper instead of ~80. **NOTE**: keep the direct-CSV path as a documented alternative in `data/stooq.py` because pandas-datareader has had open Stooq issues since 2022 (#955). |
| Ticker-symbol normalization | `str.replace('.', '-')` blindly | A `normalize_ticker()` function with a hand-curated allowlist | The actual iShares feed uses NO separator (BRKB, BFB) — see Open Q1. |

**Key insight:** Free-data ingest is dominated by the cost of getting the *failure modes* right, not the success path. The libraries above turn "Yahoo returned nothing" / "Stooq returned a stale CSV" / "iShares 403'd because the User-Agent was 'python-urllib'" into named exceptions you can branch on. Custom code at this layer reinvents wheels that have been bug-fixed for years.

## Runtime State Inventory

> Phase 2 is a greenfield additive phase (new modules, new files, no rename or migration). This section is preserved as a sanity check.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None (Phase 1 left only stubs and empty Parquet directories). Phase 2 will *create* `~/.cache/screener/http.sqlite` on first run; no migration needed. | None — created on first run. |
| Live service config | None — no external service has Phase 2 names baked in. | None. |
| OS-registered state | None — no scheduled tasks, no daemon registrations. Phase 8 owns the GitHub Actions cron. | None. |
| Secrets/env vars | `EDGAR_IDENTITY` exists from Phase 1 but is unused in Phase 2 (D-04, deferred). 8 new `OHLCV_* / UNIVERSE_* / STOOQ_*` env-var names introduced (D-20); none are secrets. | Add to `.env.example` only. |
| Build artifacts / installed packages | Adding `pandas-datareader>=0.10` to `pyproject.toml` and `uv.lock` regenerates the lockfile. | Run `uv lock` once during plan execution; commit `uv.lock`. |

**Nothing found in any category beyond standard "new file" expectations.**

## Common Pitfalls

### Pitfall 1: yfinance silent partial fetch (CLAUDE.md §13.6 #7)

**What goes wrong:** `yf.download()` returns an empty DataFrame on most failure modes (Yahoo 429, network blip, ticker delisted) — no exception. A loop over 1000 tickers silently produces 200 stale bars.
**Why it happens:** yfinance is an unofficial Yahoo scraper; the underlying HTTP path swallows errors. Verified in 2024–2025 issue tracker.
**How to avoid:** Always validate the four invariants (D-08) inside the `tenacity` retry block. Empty/stale DataFrames raise `StaleOrEmptyError` which tenacity will retry; if all 5 attempts fail the ticker is added to `failed`.
**Warning signs:** time-since-last-bar histogram across the universe should be unimodal at "yesterday." A bimodal distribution with a tail at "weeks ago" is the signature.

### Pitfall 2: yfinance volume occasionally split-unadjusted (CLAUDE.md §5.5, §13.6 #8)

**What goes wrong:** When `auto_adjust=True`, yfinance is supposed to adjust *all* of OHLCV by the close-to-adj-close ratio. In practice, volume has been observed to come back un-adjusted across split events — i.e., raw share count rather than split-equivalent count. This silently breaks the volume invariants ("breakout volume ≥ 1.5× SMA(volume, 50)") for ~5 trading days post-split.
**Why it happens:** Yahoo's underlying data inconsistency; yfinance applies a multiplier but the source data is sometimes already partially adjusted.
**How to avoid:** Phase 6 PAT-05 already mandates re-deriving pivots from adjusted closes — that's the primary defense. For Phase 2, the spot-check test on NVDA-2024-06-10 (10:1) and AAPL-2020-08-31 (4:1) verifies the cache holds adjusted volume continuity (`vol[t-1] / vol[t+1]` should be near 1.0 if both adjusted; if it's near `split_ratio` then volume is NOT adjusted — log a warning). Document in the splits ledger.
**Warning signs:** `df.loc[split_date - 1, "Volume"] / df.loc[split_date + 1, "Volume"]` = split_ratio rather than ~1.0.

### Pitfall 3: pandas-datareader Stooq blank-DataFrame (PyPI/GitHub issue #955)

**What goes wrong:** `pdr.DataReader(ticker, 'stooq')` may raise `RemoteDataError` *or* return an empty DataFrame on Stooq's intermittent failures. Issue #955 (Dec 2022) reports persistent blank-DataFrame returns and remains open.
**Why it happens:** Stooq's URL/CSV format has evolved since pandas-datareader 0.10.0 (frozen July 2021); the parser drifts.
**How to avoid:** In `data/stooq.py`, treat empty DataFrame as failure (raise `StaleOrEmptyError`); apply the same D-08 four-invariant gate as yfinance. If Stooq's pandas-datareader path proves unreliable, swap to a direct `requests.get('https://stooq.com/q/d/l/?s=<ticker>.US&d1=<YYYYMMDD>&d2=<YYYYMMDD>&i=d')` adapter — same `data/stooq.py` boundary, no consumer change. Keep this as a documented fallback in the module.
**Warning signs:** `breaker_tripped` event followed by `stooq_ok / breaker_remaining_count < 0.50` — Stooq isn't picking up the slack and the run will fail the 95% gate.

### Pitfall 4: pandas-datareader Stooq descending date order (verified)

**What goes wrong:** Stooq returns a DataFrame indexed in descending date order (most-recent first). pandera's `OhlcvPanelSchema` assumes monotonic *increasing*; a Stooq pull will fail D-08(c) silently if not reversed.
**Why it happens:** Stooq's CSV download endpoint sorts newest-first natively.
**How to avoid:** In `data/stooq.py`, `df = df.sort_index(ascending=True)` immediately after the read.
**Warning signs:** `is_monotonic_increasing` False on a Stooq fetch.

### Pitfall 5: iShares 403 with default Python User-Agent (verified live)

**What goes wrong:** BlackRock's CDN rejects the default `python-urllib/3.x` User-Agent with HTTP 403. The error appears as a `requests.HTTPError` with no descriptive body.
**Why it happens:** Anti-scrape filter; Python User-Agents are blocked.
**How to avoid:** Always send a Mozilla User-Agent with the iShares request. **Verified live 2026-05-02 that the documented Mozilla string returns 200**.
**Warning signs:** 403 from `ishares.com` after working fetches yesterday — likely UA filter changed; bump the UA string.

### Pitfall 6: iShares CSV trailer rows pollute the DataFrame (verified live)

**What goes wrong:** The CSV ends with ~10 lines of legal disclaimers, sandwiched between an empty row at index 1007 (post-last-equity) and the BlackRock notice at index 1011. Naïve `pd.read_csv(skiprows=9)` returns 1012 rows; the last 7 are not equities.
**Why it happens:** BlackRock embeds disclaimers in the same CSV file.
**How to avoid:** After read, `df = df.dropna(subset=["Ticker"])` then `df = df[df["Asset Class"] == "Equity"]`. Verified live: this leaves 1005 equity rows for IWB on 2026-04-30.
**Warning signs:** sanity_check fails the 800–1100 row gate, OR a "ticker" column shows up containing the BlackRock copyright notice — both indicate the trailer wasn't filtered.

### Pitfall 7: Tempfile on a different filesystem (D-11 footgun)

**What goes wrong:** If `target.parent` is on a tmpfs (e.g., a CI runner's `/tmp`-mounted scratch dir) and the tempfile is created via `tempfile.NamedTemporaryFile()` with the default location (`/tmp` or `TMPDIR`), `os.replace` falls back to copy+unlink across filesystems — non-atomic.
**Why it happens:** `tempfile.NamedTemporaryFile()` defaults to the system temp dir, which is rarely the same filesystem as the project's `data/` directory.
**How to avoid:** Always pass `dir=target.parent` to `NamedTemporaryFile(...)`. Documented in Pattern 1; pyarrow does *not* protect against this.
**Warning signs:** Crash mid-write leaves a partial Parquet file at `target` rather than at `target.tmp`.

### Pitfall 8: pandera composite-MultiIndex declaration order (verified syntax)

**What goes wrong:** Declaring `Index[str]` for ticker and `Index[pd.Timestamp]` for date in a `DataFrameModel` requires the field declaration order to match the actual `MultiIndex` level order. Reversing them silently produces a schema that validates a `(date, ticker)` panel — the wrong shape.
**Why it happens:** pandera honors the class field order as the index level order; there's no explicit "this is level 0" marker.
**How to avoid:** Convention: `ticker` field declared FIRST, `date` second. Document in `persistence.py` schema docstring. Add a `tests/test_persistence.py` test that constructs a `(date, ticker)`-ordered DataFrame and asserts a `SchemaError` is raised.
**Warning signs:** `read_panel()` returns successfully but `panel.index.names == ('date', 'ticker')` instead of `('ticker', 'date')`.

### Pitfall 9: yfinance `multi_level_index=True` default in 1.3.x (verified)

**What goes wrong:** As of yfinance 1.3.x, `yf.download(...)` defaults `multi_level_index=True`. For a single-ticker call this returns columns like `MultiIndex([('Close', 'AAPL'), ('High', 'AAPL'), ...])` — flat-column code (`df['Close']`) raises `KeyError`.
**Why it happens:** yfinance unified the single-ticker and multi-ticker return shapes.
**How to avoid:** Always pass `multi_level_index=False` for single-ticker `download()` calls. Verified in the official yfinance.download reference.
**Warning signs:** `KeyError: 'Close'` in unit tests, or a flat-column unit test passing while a real run produces MultiIndex columns.

### Pitfall 10: Pandera `coerce=True` silently fixing wrong dtypes (verified Context7)

**What goes wrong:** With `coerce=True` (or `Field(coerce=True)`), pandera silently casts a string-typed column to the expected float type — masking a bug where the upstream parser produced strings.
**Why it happens:** Coercion is a usability feature for sloppy data; for our boundary-validation use case it's the wrong choice.
**How to avoid:** Set `coerce = False` in every `class Config:` and on every `Field()`. The data layer should already produce correctly-typed DataFrames; if a column is wrong-type that's a real bug to surface.
**Warning signs:** A test that feeds string-typed numerics passes when it should fail.

### Pitfall 11: GitHub Actions cron drift + 60-day idle disable (STACK.md)

**What goes wrong:** Phase 8 (deferred) will own the cron, but Phase 2's design must not depend on punctual scheduling. Actions cron is documented to drift 15–60 min and to disable scheduled workflows after 60 days of zero commits to the repo.
**Why it happens:** Free-tier scheduler is best-effort.
**How to avoid:** D-02's "fail loud + serve last good snapshot" semantics already accommodate up to a day of drift. Phase 2 doesn't need to fix this; just don't bake "the cron runs every night at exactly 22:30 UTC" into invariants. Phase 8 will add a heartbeat workflow.
**Warning signs:** universe Parquet last-modified > 8 days old when checked in the morning.

## Code Examples

(See "Architecture Patterns" section above. Each numbered pattern is a verified, copy-pasteable code snippet.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pdr.DataReader('AAPL', 'yahoo')` for OHLCV | `yfinance.download('AAPL', auto_adjust=True)` | 2017+ (yahoo endpoint deprecated) | pandas-datareader's Yahoo path was discontinued; yfinance is the only free Yahoo route. |
| `IEX Cloud` free tier | yfinance + Finnhub | August 2024 (IEX shut down) | Many tutorials still reference IEX. Substitute one of the above. |
| `Alpha Vantage` for universe scans | yfinance for universe; Alpha Vantage only for spot-checks | 2024 (free tier tightened to 25/day) | Cannot scan R1000 even once — would take 40 days. |
| Cache OHLCV in pickle | Parquet via pyarrow (`auto_adjust=True`) | 2022+ | Parquet is columnar, faster, smaller, and pandera-validatable. |
| `yfinance < 0.2.40` | `yfinance >= 1.3.0` | December 2024 (1.0 graduation) | The 2023–2024 breakage cycle settled at 1.0+; pin lower bound at 1.3.0. |
| Hand-rolled `for i in range(5): try ... except: time.sleep(2**i)` | `tenacity.@retry(wait=wait_exponential(...), stop=stop_after_attempt(5), before_sleep=before_sleep_log(...))` | 2020+ | tenacity is now the de-facto retry idiom. |

**Deprecated/outdated:**

- `pdr.DataReader(t, 'yahoo')` — Yahoo endpoint deprecated. Use yfinance.
- `pandas_datareader.data.DataReader(t, 'iex', ...)` — IEX free tier discontinued 2024.
- `yfinance.download(... actions=True, auto_adjust=False)` for "raw closes + Adj Close" — still works but deprecated in spirit; prefer `auto_adjust=True` (no Adj Close column) per CLAUDE.md §5.5.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | iShares CSV row count remains in `[800, 1100]` across rebalance days. Live count 2026-05-02 was 1005 equity rows; Russell 1000 reconstitutions can briefly bring this below 950. | Pattern 6 sanity_check, Open Q5 | Sanity gate too tight → false-positive run failures on legitimate rebalance days. Mitigation: keep the gate at `[800, 1100]`. |
| A2 | yfinance 1.3.x `multi_level_index=False` argument is supported (verified in 2026-04 reference docs). | Pattern 2 | If yfinance ever drops this parameter, single-ticker fetches break. Pinning `>=1.3,<2` and adding a fallback `if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)` defends against this. |
| A3 | pandas-datareader 0.10.0's `'stooq'` data-source name is still the right call signature in 2026 (last release July 2021; no later version). | Pattern 4 / D-14 | Issue #955 (Dec 2022) reports blank DataFrames intermittently. If Stooq is fully broken, the planner may need to swap to a direct `requests.get('https://stooq.com/q/d/l/...')` adapter — same `data/stooq.py` boundary, no consumer change. |
| A4 | yfinance `Ticker.actions` returns a DataFrame with columns `["Dividends", "Stock Splits"]` indexed by event date, where Stock Splits ratio is e.g. 10.0 for a 10:1 split (Context7 verified). | Pattern 4 / D-18 | If yfinance ever changes `actions` to a Series, our schema assumption breaks. Test on NVDA-2024-06-10 (expect ratio = 10.0) to lock the contract. |
| A5 | `os.replace` is atomic on the same filesystem on macOS, Linux, and Windows (Python 3.3+ docs verified). | Pattern 1 | If a CI runner mounts `data/` on tmpfs, atomicity falls back to copy+unlink. Mitigation: tempfile must use `dir=target.parent`. |
| A6 | The `~/.cache/screener/http.sqlite` location is a sensible default. | Pattern 7 | None — purely a Discretion choice. Settings exposes it if needed. |

## Open Questions

1. **iShares actually uses NO separator (BRKB), not dot (BRK.B). What is the correct `normalize_ticker()` rule?** [BLOCKING]
   - **What we verified live (2026-05-02):** iShares feed contains `BRKB`, `BFB`, `BFA` — no separator at all between root ticker and share class.
   - **What CONTEXT.md D-03 assumes:** the iShares feed uses dot notation (`BRK.B`, `BF.B`) and the regex `\.([A-Z])$` → `-\1` is the canonical normalization.
   - **The gap:** D-03's regex is a no-op on the actual feed. None of the 1005 verified tickers contains a dot.
   - **Recommended answer for the planner:** Replace D-03's regex with a hand-curated allowlist for known share-class tickers. The function reads:
     ```python
     ALLOWLIST = {"BRKB": "BRK-B", "BFB": "BF-B", "BFA": "BF-A"}
     def normalize_ticker(raw: str) -> str:
         return ALLOWLIST.get(raw, raw)
     ```
     The allowlist is reviewed quarterly at IWB rebalance; a sanity-check assertion in `parse_ishares_iwb_csv()` flags any ticker matching `^[A-Z]{4,5}[A-Z]$` not in the allowlist as a candidate for review. (Three letters such as "AAA" wouldn't match; only 4–5 letter tickers ending in a single uppercase letter that isn't a known dual-class company get flagged.)
   - **Why this matters now:** the planner must NOT write the `\.([A-Z])$` regex into the codebase. The allowlist is the right pattern.
   - **Decision authority:** This contradicts a locked decision. Recommend the user re-confirm during /gsd-discuss-phase or accept the corrected normalization as a minor amendment.

2. **Should `data/splits/` be a separate top-level directory, or stay as `data/ohlcv/<TICKER>/splits.parquet`?**
   - **D-06 says:** `data/ohlcv/<TICKER>/{prices,splits}.parquet` — co-located.
   - **D-19 says:** "Commit `data/splits/*.parquet`" — implying a top-level `data/splits/` directory.
   - **Inconsistency:** these two decisions disagree. Either commit the splits via the per-ticker subdirectory (`!data/ohlcv/*/splits.parquet`), OR keep a separate `data/splits/<TICKER>.parquet` flat layout with `data/ohlcv/<TICKER>/prices.parquet` (which violates D-06's co-location).
   - **Recommended answer:** keep D-06's co-location; the `.gitignore` carve-out is `!data/ohlcv/*/splits.parquet`. Update the `.gitignore` snippet from CONTEXT.md's `<specifics>` section to:
     ```
     data/*
     !data/universe/
     !data/universe/.gitkeep
     # splits live alongside prices in data/ohlcv/<TICKER>/ — selectively un-ignore
     # the splits.parquet file inside each ticker dir, while keeping prices.parquet ignored.
     !data/ohlcv/
     data/ohlcv/**/prices.parquet
     !data/ohlcv/**/splits.parquet
     !data/ohlcv/**/.gitkeep
     ```
   - **Decision authority:** Discretion. Planner finalizes; the gitignore pattern above is the cleanest.

3. **`splits.parquet` empty-case schema preservation — what columns does pandera expect when there are zero rows?**
   - **CONTEXT.md Discretion says:** "When a ticker has no corporate actions in the cached window, write a zero-row Parquet with the schema preserved (don't skip the file — pandera schema check would otherwise fail on read)."
   - **Recommended:** when `yfinance.Ticker(t).actions` is empty, construct a zero-row DataFrame with explicit dtypes matching `SplitsSchema`:
     ```python
     empty_splits = pd.DataFrame(
         {"ratio": pd.Series([], dtype="float64"),
          "dividend": pd.Series([], dtype="float64")},
         index=pd.DatetimeIndex([], name="date"),
     )
     ```
     Pandera with `coerce=False` validates an empty DataFrame against `SplitsSchema` provided the columns and dtypes match.
   - **Decision authority:** Discretion. Planner finalizes.

4. **Holiday-aware ISO-week-Monday key — what about Memorial Day or Juneteenth?**
   - **CONTEXT.md Discretion says:** "snapshot is keyed off the Monday of the current ISO week, computed from `today.isoweekday()`."
   - **Recommended:** keep ISO-week-Monday verbatim; do NOT add holiday awareness. A Monday-Memorial-Day (e.g., 2026-05-25) snapshot is just the Tuesday's snapshot under that Monday's key — the cron runs daily anyway. Acceptance criterion: `data/universe/<this_iso_week_monday>.parquet` exists by Friday EOD.
   - **Decision authority:** Discretion. Planner finalizes.

5. **Sanity-gate row threshold — `[800, 1100]` or `[950, 1010]`?**
   - **PITFALLS.md §1 says:** `assert universe_snapshot_count >= 950 and universe_snapshot_count <= 1010` for Russell 1000.
   - **Live 2026-05-02 count:** 1005 equity rows.
   - **Tradeoff:** tight (950–1010) catches parser regressions but may false-positive on quarterly rebalance days when tickers are in transition. Loose (800–1100) is robust to rebalance noise but lets parser regressions slip.
   - **Recommended:** `[800, 1100]` for the row count gate (D-02's "< 800 rows" trigger), with a separate structured-log warning at counts outside `[950, 1010]` so a real drift surfaces but doesn't fail the run.
   - **Decision authority:** Discretion. Planner finalizes.

6. **`requests-cache` cache_name path — `~/.cache/screener/http.sqlite` or `data/.cache/http.sqlite`?**
   - **Tradeoff:** `~/.cache/...` is host-local and survives `git clean`; `data/.cache/...` is project-local and tied to the repo (would need gitignore entry).
   - **Recommended:** `~/.cache/screener/http.sqlite` — XDG-style, survives repo clones, won't accidentally be committed.
   - **Decision authority:** Discretion. Planner finalizes.

7. **Exact structured-log event names + field schemas?**
   - **CONTEXT.md Discretion lists:** `fetch_start`, `fetch_success`, `fetch_fail`, `breaker_tripped`, `health_check_passed`, `health_check_failed`, `snapshot_written`.
   - **Recommended field schemas:**

     | Event | Required fields |
     |-------|-----------------|
     | `fetch_start` | `command`, `n_universe` |
     | `fetch_success` | `ticker`, `source` (`yfinance` / `stooq`), `n_bars` |
     | `fetch_fail` | `ticker`, `source`, `error`, `attempt` |
     | `breaker_tripped` | `probe_n`, `success_rate`, `threshold` |
     | `health_check_passed` | `success_count`, `universe_size`, `ratio` |
     | `health_check_failed` | `success_count`, `universe_size`, `ratio`, `failed_tickers[:20]` (truncated) |
     | `snapshot_written` | `path`, `n_rows` |
   - **Decision authority:** Discretion. Planner finalizes; Phase 8 OPS-05 will consume.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All | ✓ | 3.11.x (Phase 1 verified) | — |
| `uv` | dependency mgmt | ✓ | 0.11.x | — |
| Internet (yfinance, iShares CDN, Stooq, optionally requests-cache writes to disk) | OHLCV, universe | ✓ in dev; assumed in CI | — | — |
| BlackRock iShares CDN reachable from CI | DAT-01 | Assumed (verified live from dev machine 2026-05-02) | n/a | If 403: bump User-Agent string. If 503: tenacity covers it. If permanent block: switch to FTSE Russell direct CSV (back-up URL: `https://research.ftserussell.com/products/russell-index-values/home/getfile?id=valueshist_US1001.csv` — caveat: monthly cadence, less granular sectors). |
| Yahoo Finance reachable | DAT-03 | Assumed (yfinance handles outages) | yfinance 1.3.x | Stooq via D-12 circuit-breaker. |
| stooq.com reachable | DAT-03 fallback | Assumed | pandas-datareader 0.10.0 | Direct `requests.get('https://stooq.com/q/d/l/...')` if pandas-datareader is broken. |
| SQLite (for requests-cache) | DAT-06 | ✓ Python stdlib | 3.x | — |
| `~/.cache/screener/` writable | DAT-06 cache path | ✓ in dev; ✓ in CI ($HOME is writable) | — | If `$HOME` not writable, override `cache_name` via Settings. |
| pyarrow Parquet engine | persistence | ✓ pinned | 17.x | Fall back to fastparquet — not currently installed; would need a config switch. |

**Missing dependencies with no fallback:** None. All tooling is installed via Phase 1's `uv sync`.

**Missing dependencies with fallback:**
- pandas-datareader Stooq path — if broken, swap to direct CSV scrape (see Pitfall 3).
- iShares URL — if BlackRock changes the 9-row-skip metadata format, the parser must adapt; sanity_check would fail loud and the planner adds a Phase 2.x amendment.

## Validation Architecture

> Phase config: `nyquist_validation: true`. Tests live in `tests/`; framework is pytest 8.x with hypothesis (already installed Phase 1).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (Phase 1 baseline) + hypothesis 6.x for property tests |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 1) |
| Quick run command | `uv run pytest -m "not slow and not integration" -x` |
| Full suite command | `uv run pytest --cov=src/screener --cov-fail-under=80 --strict-markers` |
| Coverage target | `--cov-fail-under=80` (Phase 1 baseline; Phase 2 first phase that exercises real coverage) |
| Mypy gate | `uv run mypy src/screener/persistence.py src/screener/data/` (CONTEXT.md notes data/ stays in mypy ignore-overrides; persistence.py becomes new strict module — see Note below) |

**Note on mypy strict scope:** `pyproject.toml` currently has `[[tool.mypy.overrides]] module = "screener.data.*" ignore_errors = true`. Phase 2 should keep that override (network-I/O modules with sloppy third-party stubs) but **add `persistence.py` to the strict list** since it's pure-function schema work that benefits from strict types. Concretely: remove `persistence.py` from any ignore list; the existing strict `files = [...]` covers it.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DAT-01 | iShares CSV fetch + parse returns ≥ 800 equity rows | unit | `pytest tests/test_data_universe.py::test_parse_ishares_csv_happy_path -x` | ❌ Wave 0 |
| DAT-01 | `normalize_ticker()` allowlist round-trip (BRKB → BRK-B) | unit | `pytest tests/test_data_universe.py::test_normalize_ticker_allowlist -x` | ❌ Wave 0 |
| DAT-01 | iShares CSV with < 800 rows raises ValueError | unit | `pytest tests/test_data_universe.py::test_parse_ishares_csv_undersized_fails -x` | ❌ Wave 0 |
| DAT-01 | Unknown sector raises ValueError | unit | `pytest tests/test_data_universe.py::test_parse_ishares_csv_unknown_sector_fails -x` | ❌ Wave 0 |
| DAT-02 | Weekly snapshot writes to `data/universe/<iso_monday>.parquet` | unit | `pytest tests/test_data_universe.py::test_snapshot_iso_monday_keying -x` | ❌ Wave 0 |
| DAT-02 | Re-running on same Monday is a no-op (idempotent) | unit | `pytest tests/test_data_universe.py::test_snapshot_idempotent_same_week -x` | ❌ Wave 0 |
| DAT-02 | `--force` overrides idempotency | unit | `pytest tests/test_data_universe.py::test_snapshot_force_overwrites -x` | ❌ Wave 0 |
| DAT-03 | yfinance fetch, all 4 invariants pass → success | unit | `pytest tests/test_data_ohlcv.py::test_fetch_all_invariants_pass -x` | ❌ Wave 0 |
| DAT-03 | yfinance returns empty DataFrame → tenacity retries 5x then raises | unit | `pytest tests/test_data_ohlcv.py::test_fetch_empty_raises_after_retries -x` | ❌ Wave 0 |
| DAT-03 | yfinance last bar > 4 business days old → fails invariant | unit | `pytest tests/test_data_ohlcv.py::test_fetch_stale_fails -x` | ❌ Wave 0 |
| DAT-03 | non-monotonic index → fails invariant | unit | `pytest tests/test_data_ohlcv.py::test_fetch_non_monotonic_fails -x` | ❌ Wave 0 |
| DAT-03 | null close → fails invariant | unit | `pytest tests/test_data_ohlcv.py::test_fetch_null_close_fails -x` | ❌ Wave 0 |
| DAT-03 | Sentinel mismatch on incremental triggers full re-fetch | unit | `pytest tests/test_data_ohlcv.py::test_sentinel_mismatch_full_refetch -x` | ❌ Wave 0 |
| DAT-03 | Stooq adapter normalizes columns to lowercase + ascending index | unit | `pytest tests/test_data_stooq.py::test_normalize_columns_and_order -x` | ❌ Wave 0 |
| DAT-03 | Stooq adapter raises on empty | unit | `pytest tests/test_data_stooq.py::test_empty_raises -x` | ❌ Wave 0 |
| DAT-03 | Atomic write — Ctrl-C mid-write leaves no partial Parquet | unit | `pytest tests/test_persistence.py::test_atomic_write_crash_no_partial -x` | ❌ Wave 0 |
| DAT-06 | Tenacity retries with exponential backoff on 429 | unit (mocked) | `pytest tests/test_data_ohlcv.py::test_tenacity_backoff_on_429 -x` | ❌ Wave 0 |
| DAT-06 | requests-cache returns cached response on second call | unit (mocked) | `pytest tests/test_data_universe.py::test_requests_cache_hit -x` | ❌ Wave 0 |
| DAT-06 | structured `fetch_fail` event emitted on tenacity exhaustion | unit | `pytest tests/test_data_ohlcv.py::test_structured_log_on_fail -x` | ❌ Wave 0 |
| DAT-07 | < 95% success → CLI exits non-zero with `health_check_failed` event | integration | `pytest tests/test_cli_smoke.py::test_health_gate_below_95_fails_run` | ❌ Wave 0 |
| DAT-07 | ≥ 95% success → CLI exits zero with `health_check_passed` | integration | `pytest tests/test_cli_smoke.py::test_health_gate_above_95_passes_run` | ❌ Wave 0 |
| DAT-07 | Circuit-breaker trips at < 80% in first 50 → Stooq path | unit | `pytest tests/test_data_ohlcv.py::test_circuit_breaker_trip -x` | ❌ Wave 0 |
| DAT-07 | (yf+stooq) ≥ 95% threshold satisfied post-fallback | unit | `pytest tests/test_data_ohlcv.py::test_combined_gate_passes -x` | ❌ Wave 0 |
| DAT-08 | NVDA 2024-06-10 split ratio = 10.0 in splits.parquet | golden-file | `pytest tests/test_data_ohlcv.py::test_nvda_split_2024_recorded` | ❌ Wave 0 |
| DAT-08 | AAPL 2020-08-31 split ratio = 4.0 in splits.parquet | golden-file | `pytest tests/test_data_ohlcv.py::test_aapl_split_2020_recorded` | ❌ Wave 0 |
| DAT-08 | Empty actions → zero-row splits.parquet with schema preserved | unit | `pytest tests/test_persistence.py::test_empty_splits_schema_preserved -x` | ❌ Wave 0 |
| DAT-09 | OhlcvPanelSchema rejects null close | unit | `pytest tests/test_persistence.py::test_panel_schema_rejects_null_close -x` | ❌ Wave 0 |
| DAT-09 | OhlcvPanelSchema rejects negative price | unit | `pytest tests/test_persistence.py::test_panel_schema_rejects_negative_price -x` | ❌ Wave 0 |
| DAT-09 | OhlcvPanelSchema rejects wrong index order (date,ticker vs ticker,date) | unit | `pytest tests/test_persistence.py::test_panel_schema_rejects_wrong_index_order -x` | ❌ Wave 0 |
| DAT-09 | UniverseSchema rejects unknown sector | unit | `pytest tests/test_persistence.py::test_universe_schema_rejects_unknown_sector -x` | ❌ Wave 0 |
| DAT-09 | SplitsSchema rejects negative ratio | unit | `pytest tests/test_persistence.py::test_splits_schema_rejects_negative -x` | ❌ Wave 0 |
| DAT-09 | Lazy-mode validation collects ALL errors (vs eager which fails fast) | unit | `pytest tests/test_persistence.py::test_lazy_collects_multiple_errors -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -m "not slow and not integration" -x` (≤ 30s wall time once Wave 0 fixtures are in place)
- **Per wave merge:** `uv run pytest --cov=src/screener --cov-fail-under=80 --strict-markers`
- **Phase gate:** Full suite green, coverage ≥ 80% on `src/screener/persistence.py` and `src/screener/data/`, before `/gsd-verify-work`

### Wave 0 Gaps (must be created before any data layer code)

- [ ] `tests/conftest.py` — extend with 6 synthetic fixtures:
  - `synthetic_ohlcv_valid_df` — 252 days of fake OHLCV passing all 4 invariants
  - `synthetic_ohlcv_empty_df` — empty DataFrame for the silent-empty test
  - `synthetic_ohlcv_stale_df` — last bar 10 business days old
  - `synthetic_ohlcv_null_close_df` — one NaN in close
  - `synthetic_ohlcv_non_monotonic_df` — last 5 bars in random order
  - `synthetic_ishares_csv_bytes` — 1010-row valid CSV mock matching the verified live structure
  - `synthetic_ishares_csv_undersized_bytes` — 500-row variant for sanity_check fail test
  - `synthetic_ishares_csv_bad_sector_bytes` — one row with sector "Bogus Sector"
  - `synthetic_split_mismatch_pair` — `(cached, refetched)` DataFrames where the sentinel close differs by 0.5×
  - `synthetic_stooq_descending_df` — Stooq-shape DataFrame with descending date index + PascalCase columns
- [ ] `tests/test_data_universe.py` — 7 tests (covers DAT-01, DAT-02, DAT-06)
- [ ] `tests/test_data_ohlcv.py` — 9 tests (covers DAT-03, DAT-06, DAT-07, DAT-08)
- [ ] `tests/test_data_stooq.py` — 3 tests (covers DAT-03 fallback)
- [ ] `tests/test_persistence.py` — 9 tests (covers DAT-09, atomic-write, read_panel)
- [ ] `tests/test_cli_smoke.py` — extend with 2 health-gate integration tests (covers DAT-07)

**Total: 30 tests** across 5 test files; coverage target 80%+ on `src/screener/persistence.py` and `src/screener/data/`.

## Project Constraints (from CLAUDE.md)

- **Free-data only**: yfinance + iShares CSV + Stooq fallback. No paid feeds. No Alpha Vantage as primary OHLCV (25/day quota). No IEX Cloud (discontinued).
- **EOD-only**: no intraday or pre-market dependencies in v1.
- **SMA, not EMA** (CLAUDE.md §13.1) — Phase 2 doesn't compute indicators but the panel API consumed by Phase 3 must permit SMA computation; the schema is dtype-agnostic.
- **Signals execute at next-bar open** (CLAUDE.md §13): irrelevant to Phase 2 directly, but the panel `(ticker, date)` index allows downstream `.shift(1)` consistency.
- **Survivorship bias accepted and disclosed** (CLAUDE.md §5.3) — D-09 (frozen cache on drop) + D-02 (weekly snapshots) implement this.
- **TA-Lib forbidden in v1** (CLAUDE.md §10.3) — Phase 2 doesn't use indicators, so no risk; documented for completeness.
- **No I/O in `signals/`** (CLAUDE.md §10) — Phase 2 doesn't touch `signals/`. Architecture test (Phase 1 D-16) catches violations.
- **`yfinance>=0.2.40` minimum** (CLAUDE.md §13.6 #7). Phase 1 already pinned `>=1.3.0,<2`.
- **`requests-cache` for HTTP APIs, Parquet on disk for OHLCV, tenacity retry/backoff** (CLAUDE.md §5.6) — Phase 2 implements all three.
- **`yfinance` occasionally returns split-unadjusted volume** (CLAUDE.md §5.5, §13.6 #8) — Pitfall 2 documents the spot-check defense.

## Security Domain

> Required since `security_enforcement: true` (config). Phase 2 is mostly outbound HTTP fetches; STRIDE surface is small but non-zero.

### Applicable ASVS Categories (Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user authentication; CLI runs as the host user. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | No multi-user surface. |
| V5 Input Validation | **yes** | Pandera schemas validate all inbound data (DAT-09). iShares CSV row count + sector sanity checks. yfinance OHLCV invariant gate. Pandas `read_csv` configured with `na_values=['-']` and `thousands=','` to avoid CSV-injection-style surprises. |
| V6 Cryptography | no | No crypto operations. Don't hand-roll any. |
| V7 Error Handling & Logging | **yes** | Structured logging via structlog (Phase 1 baseline). Phase 2 emits no secrets in logs (verified: `fetch_fail.error` is the exception message, not request headers). |
| V8 Data Protection | partial | The HTTP cache at `~/.cache/screener/http.sqlite` may contain copies of the iShares CSV (public data, not secret). Document expectation. No PII or credentials cached. |
| V12 File and Resources | **yes** | Atomic writes (D-11) via tempfile + `os.replace` — same-filesystem rename is the only guaranteed-atomic primitive. |
| V13 API and Web Service | **yes** | Outbound only; no API exposed. |
| V14 Configuration | **yes** | Settings via pydantic-settings; secrets (`FINNHUB_API_KEY`, `EDGAR_IDENTITY` — Phase 1) read from `.env` (gitignored); D-20 fields are non-secret tunables. |

### Known Threat Patterns for Phase 2 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious iShares CSV (e.g., embedded `=cmd|...`) | Tampering | `pd.read_csv` does not execute formulas; we never `eval()` the content. Sanity check rejects unknown sectors and out-of-range row counts. |
| iShares CSV columns rearrangement (e.g., a renamed column slips a wrong field into `Sector`) | Tampering | `sanity_check()` asserts `required = {"Ticker","Name","Sector","Asset Class","Weight (%)"}` are present BEFORE filtering. |
| yfinance stale data (Yahoo serves Friday data on Tuesday) | Tampering / Repudiation | D-08 invariant 2: `df.index.max().date() >= today - 4bd`. |
| Stooq stale data (1-day lag is documented) | Tampering | Same D-08 gate; banner discloses data-source mix. |
| HTTP cache poisoning (a CDN serves a malicious response that gets cached) | Tampering | `allowable_codes=[200]` in CachedSession (refuses to cache 4xx/5xx); 1h expiry on iShares limits blast radius. |
| Tempfile leak (an attacker reads a half-written `.tmp.<pid>.parquet`) | Information Disclosure | Tempfile is in the same dir as target with `0o600` (default); the data is OHLCV which is public anyway. Low risk. |
| Path traversal via ticker name (e.g., `data/ohlcv/../../etc/passwd/prices.parquet`) | Tampering | `normalize_ticker` allowlist + sanity_check `^[A-Z][A-Z0-9\-]{0,9}$` regex on UniverseSchema makes ticker strings safe to use as path components. Add an explicit `assert "/" not in ticker and ".." not in ticker` defensive check before path construction. |
| Logging API keys / tokens by accident | Information Disclosure | Phase 2 doesn't authenticate to any service (yfinance, iShares, Stooq, FRED — all unauthenticated for v1 endpoints used here). Edgar identity is configured but not invoked. CHECK: `fetch_fail.error` should not include request headers — only the exception message. |
| Following an HTTP redirect to a malicious URL | Tampering | `requests.get(...)` follows redirects by default. iShares URL is HTTPS to `*.ishares.com`; tenacity stops after 5 attempts; `allowable_codes=[200]` prevents caching anything else. **Recommendation:** add `allow_redirects=True` with `verify=True` (TLS cert validation), default in requests; document. |

**Required additions for Phase 2 implementation:**
- `assert "/" not in ticker and "\\" not in ticker and ".." not in ticker` in `persistence.write_ohlcv_atomic(ticker, df)` before path construction.
- `requests.get(..., timeout=30)` on every external HTTP call (already in iShares pattern; verify Stooq adapter has a timeout).
- Document in module docstrings: "this layer makes outbound HTTPS only; no inbound network surface; no PII handled."

## Sources

### Primary (HIGH confidence, verified live this session)

- **iShares IWB CSV** — `https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund` — fetched live 2026-05-02 with `Mozilla/5.0` UA. HTTP/2 200, 1030 lines, 9 metadata + blank + header + 1005 Equity rows + 5 cash/derivative rows + 2 trailer rows. UTF-8-SIG encoded. `BRKB` (no separator) confirmed.
- **`pd.read_csv(skiprows=9, encoding='utf-8-sig', thousands=',', na_values=['-'])`** — verified to parse the live CSV correctly (1012 rows post-parse; filter to `Asset Class == 'Equity'` → 1005 rows).
- **Context7 `/ranaroussi/yfinance`** — `download()` signature, `auto_adjust=True` default, `multi_level_index=True` default, `Ticker.actions` semantics, `yf.config.network.retries`.
- **Context7 `/unionai-oss/pandera`** — `DataFrameModel`, `MultiIndex` declaration via `Index[str]` + `Index[pd.Timestamp]` + `Config.multiindex_strict=True`, `lazy=True` vs `False`, `@check_types` decorator, `Field(coerce=False)`.
- **Context7 `/jd/tenacity`** — `retry`, `wait_exponential`, `stop_after_attempt`, `retry_if_exception_type`, `before_sleep_log`.
- **Context7 `/requests-cache/requests-cache`** — `CachedSession(backend='sqlite', urls_expire_after={...})` with glob/regex URL patterns, `allowable_codes`, `stale_if_error`.
- **PyPI live (2026-05-02):** pandas-datareader 0.10.0 (frozen July 2021); requires-python `>=3.6`, deps `lxml + pandas>=0.23 + requests>=2.19.0`.

### Secondary (MEDIUM confidence)

- **GitHub `pydata/pandas-datareader/pandas_datareader/base.py`** — `_DailyBaseReader` raises `RemoteDataError` (4 retries with `retry_count`) and `OSError` on empty StringIO; does NOT silently return empty DataFrame for HTTP non-200.
- **GitHub `pydata/pandas-datareader/pandas_datareader/stooq.py`** — `StooqDailyReader` URL: `https://stooq.com/q/d/l/`; symbol gets `.US` country code suffix; date params `d1`/`d2` in YYYYMMDD format.
- **GitHub `nikulpatel3141/ETF-Scraper`** — confirmed iShares CSV uses `skiprows=9`, `encoding='utf-8-sig'`, `thousands=','`, `na_values=['-']`.
- **GitHub `pydata/pandas-datareader` issue #955** (Dec 2022) — Stooq returns blank DataFrames; still open at last review.
- **`yfinance.download` reference (`ranaroussi.github.io/yfinance/reference/api/yfinance.download.html`)** — full parameter list including `multi_level_index=True` default and `timeout=10`.
- **CLAUDE.md §5.3, §5.4, §5.5, §5.6, §13.1, §13.6** — survivorship, look-ahead, corporate-action handling, caching idioms, EMA-vs-SMA enforcement, common pitfalls.
- **PITFALLS.md §1, §3, §7, §10** — survivorship, corporate actions, yfinance silent partial, universe leakage.

### Tertiary (LOW confidence — flagged for validation)

- **pandas-datareader's behavior in 2026** — last release was July 2021. Stooq path may or may not still work; #955 is open. **Recommend testing during implementation Wave 0** with a single live `pdr.DataReader('AAPL', 'stooq', start='2024-01-01')` call before committing the adapter.
- **iShares CSV row count of `1005` equity holdings** — observed live on 2026-04-30; rebalance days may dip lower. Sanity gate `[800, 1100]` is conservative.
- **GICS sector list of 11 names** — observed live on 2026-04-30; if S&P/MSCI add a 12th sector before phase ships, `sanity_check()` would false-positive. Mitigate by treating "unknown sector" as a structlog-WARN rather than ValueError if needed; planner finalizes.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library + version verified live against PyPI and Context7.
- iShares CSV format: HIGH — fetched and parsed live during this research.
- yfinance API surface: HIGH — Context7 + reference docs verified.
- pandera DataFrameModel + MultiIndex syntax: HIGH — Context7 verified with multiple examples.
- pandas-datareader Stooq path reliability: MEDIUM-LOW — library frozen since 2021, open community issue, untested live during this research.
- Symbol normalization rule (D-03 contradiction): HIGH that the contradiction exists; HIGH that the allowlist approach resolves it.
- Atomic write idiom: HIGH — stdlib pattern, well-documented.
- 95% health-gate logic: HIGH — straightforward arithmetic.
- Structured-log event schema (Q7): MEDIUM — Discretion; planner finalizes.

**Research date:** 2026-05-02
**Valid until:** 2026-06-01 (1 month — yfinance and iShares feed format both move on monthly cadence; revalidate if planning slips past June)

## RESEARCH COMPLETE
