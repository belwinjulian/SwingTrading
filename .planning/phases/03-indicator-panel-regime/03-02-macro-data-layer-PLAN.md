---
phase: 03-indicator-panel-regime
plan: 02
type: execute
wave: 2
depends_on:
  - 03-01
files_modified:
  - src/screener/data/macro.py
  - src/screener/data/__init__.py
  - src/screener/cli.py
  - Makefile
  - tests/test_macro_refresh.py
autonomous: true
requirements:
  - DAT-04
tags:
  - data
  - macro
  - cli

must_haves:
  truths:
    - "`screener refresh-macro` (and `make macro`) refreshes 5 macro series: SPY (yfinance), QQQ (yfinance), ^VIX (yfinance close-only), $NYAD (Stooq with R1000-breadth fallback per D-05), FRED yields (DGS2/DGS10/T10Y2Y); each series writes one Parquet to data/macro/<series>.parquet via persistence.write_macro_atomic."
    - "Stooq $NYAD failure (ParserError per RESEARCH Pitfall 1, or > 5% missing values per D-05) routes cleanly to `_compute_breadth_fallback()` which derives advances/declines from the R1000 panel; structured event `nyad_source` is emitted with `source='stooq'` or `source='r1000_proxy'`."
    - "Macro refresh is idempotent and incremental (D-06): subsequent runs check `max(date)` in the existing Parquet and fetch only newer bars; first run backfills from MACRO_BACKFILL_START (2005-01-01)."
    - "data/macro.py uses the same tenacity retry decorator + 4-invariant gate idiom as data/ohlcv.py (Phase 2 D-10); ^VIX is projected to close-only before write (Pitfall 4); FRED yields are stored as-received with NaN gaps (Pitfall 5)."
    - "FRED_API_KEY missing → log warning `skipping_yields_no_key` and write empty yields.parquet (graceful degradation; yields are not in D-03 score formula)."
    - "D-14 surface lock: refresh-macro is filled in-place; no new typer subcommands added (locked surface = 9)."
  artifacts:
    - path: "src/screener/data/macro.py"
      provides: "5 fetcher/refresh functions: refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields; private helpers _fetch_yf_macro, _fetch_fred_yields, _compute_breadth_fallback"
      contains: "def refresh_spy, def refresh_qqq, def refresh_vix, def refresh_nyad, def refresh_yields, def _compute_breadth_fallback, from fredapi import Fred, import yfinance as yf, from screener.data import stooq as stooq_module"
    - path: "src/screener/cli.py"
      provides: "Real body for refresh-macro (stub at lines 161-164 replaced)"
      contains: "from screener.data.macro import refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields"
    - path: "Makefile"
      provides: "make macro target wired to `uv run screener refresh-macro`"
      contains: "macro:"
    - path: "src/screener/data/__init__.py"
      provides: "macro re-export so `from screener.data import macro` resolves cleanly"
      contains: "from screener.data import macro"
    - path: "tests/test_macro_refresh.py"
      provides: "6 unit tests covering DAT-04: yf invariants, NYAD Stooq fallback to r1000_proxy, NYAD thin-Stooq fallback, yields columns, no-secret-in-logs, unknown-series ValueError"
      exports: ["test_yf_invariants_applied", "test_nyad_fallback_to_r1000_proxy", "test_nyad_fallback_on_thin_stooq", "test_yields_parquet_columns", "test_no_secret_in_logs", "test_refresh_spy_writes_macro_parquet"]
  key_links:
    - from: "src/screener/data/macro.py refresh_spy/qqq/vix/nyad/yields"
      to: "src/screener/persistence.py write_macro_atomic"
      via: "validated atomic-write per series"
      pattern: "write_macro_atomic\\(df, "
    - from: "src/screener/data/macro.py _fetch_yf_macro"
      to: "yfinance.download"
      via: "tenacity-wrapped network call"
      pattern: "yf\\.download\\("
    - from: "src/screener/data/macro.py refresh_nyad"
      to: "src/screener/data/macro.py _compute_breadth_fallback"
      via: "exception fallback chain (catches StaleOrEmptyError/ParserError/Exception from stooq_module.fetch_ohlcv)"
      pattern: "_compute_breadth_fallback\\("
    - from: "src/screener/cli.py refresh_macro"
      to: "src/screener/data/macro.py refresh_spy/qqq/vix/nyad/yields"
      via: "CLI orchestration"
      pattern: "from screener.data.macro import"
    - from: "Makefile macro:"
      to: "src/screener/cli.py refresh-macro"
      via: "uv run screener refresh-macro"
      pattern: "uv run screener refresh-macro"
---

<objective>
Implement the Phase 3 macro data layer — 5 fetchers (SPY, QQQ, ^VIX, $NYAD, FRED yields) wired into the existing `refresh-macro` typer subcommand and the new `make macro` target. This plan owns DAT-04 end-to-end.

Purpose: Provide the macro inputs that the regime module (Plan 03-04) will consume. Macro data must be reliable (tenacity retry + 4-invariant gate inherited from Phase 2 D-10), idempotent + incremental (D-06), and resilient to Stooq's currently-broken state (RESEARCH Pitfall 1) via the R1000 breadth fallback (D-05).

Output:
- `src/screener/data/macro.py` (new) — 5 public refresh functions + 3 private helpers, mirroring `data/ohlcv.py` retry/invariant structure
- `src/screener/cli.py` modified — fill the `refresh-macro` stub body (lines 161-164) with real orchestration
- `Makefile` modified — add `macro:` target alongside existing targets
- `src/screener/data/__init__.py` modified — re-export `macro`
- `tests/test_macro_refresh.py` (new) — 6 unit tests with mock yfinance/stooq/fredapi
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-indicator-panel-regime/03-CONTEXT.md
@.planning/phases/03-indicator-panel-regime/03-RESEARCH.md
@.planning/phases/03-indicator-panel-regime/03-PATTERNS.md
@.planning/phases/03-indicator-panel-regime/03-VALIDATION.md
@.planning/phases/03-indicator-panel-regime/03-01-SUMMARY.md
@.planning/phases/02-data-foundation/02-CONTEXT.md

@src/screener/data/ohlcv.py
@src/screener/data/stooq.py
@src/screener/data/__init__.py
@src/screener/cli.py
@src/screener/persistence.py
@src/screener/obs.py
@Makefile
@tests/test_data_ohlcv.py
@tests/test_data_stooq.py

<interfaces>
<!-- Existing primitives in data/ohlcv.py and data/stooq.py that Phase 3 reuses 1:1. -->

From src/screener/data/ohlcv.py (lines 54-104, fetch_ohlcv):
```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = yf.download(
        ticker,
        start=str(start),
        auto_adjust=True,
        progress=False,
        threads=False,
        actions=False,
        multi_level_index=False,
    )
    if df is None or len(df) == 0:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")
    df = df.rename(columns=str.lower)
    if df.index.name is None or df.index.name.lower() != "date":
        df.index.name = "date"
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale: last bar {last}, today {today}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} non-monotonic index")
    if "close" not in df.columns:
        raise StaleOrEmptyError(f"{ticker} no close column")
    if df["close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} has null close")
    return df
```

From src/screener/data/stooq.py:
```python
def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Stooq adapter; raises StaleOrEmptyError on empty/stale; lowercases columns,
    sorts ascending, names index 'date'. CURRENTLY broken at runtime — every call
    raises pandas.errors.ParserError (RESEARCH Pitfall 1). Phase 3 must catch
    broadly and route to _compute_breadth_fallback for $NYAD."""
```

From src/screener/persistence.py (Plan 03-01 added):
```python
def write_macro_atomic(df: pd.DataFrame, series_name: str) -> Path:
    """series_name in {'spy','qqq','vix','nyad','yields'}; eager schema validation."""

def read_panel(snapshot_date: str) -> pd.DataFrame:
    """Existing Phase 2: returns (ticker, date) MultiIndex panel."""

def read_universe(snapshot_date: str) -> pd.DataFrame:
    """Existing Phase 2: returns the universe snapshot."""

class StaleOrEmptyError(Exception):
    """Existing Phase 2 sentinel for stale/empty fetches."""
```

From src/screener/cli.py (existing refresh-macro stub at ~lines 161-164):
```python
@app.command("refresh-macro")
def refresh_macro() -> None:
    """Stub — Phase 3 fills body. D-14 surface locked: do not rename or remove."""
    log.info("refresh_macro_stub")
```

D-14 SURFACE LOCK: tests/test_cli_smoke.py asserts the 9-subcommand surface. DO NOT add or rename subcommands.
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| network → data/macro.py | yfinance, FRED, Stooq HTTP responses are untrusted; pandera + 4-invariant gate validates shape; tenacity retries on transient failure; circuit-breaker semantics inherited per Phase 2 D-12 |
| FRED_API_KEY → fredapi → exception trace | Key may leak into stack traces or structlog kwargs |
| Stooq HTML → pandas-datareader | Stooq currently serves HTML rate-limit pages where CSV is expected (RESEARCH Pitfall 1); ParserError if not caught aborts the run |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-01 | Tampering | data/macro.py _fetch_yf_macro | mitigate | Reuse Phase 2 D-10 4-invariant gate (StaleOrEmptyError on empty/stale/non-monotonic/null-close); pandera MacroOhlcvSchema eager validation at write_macro_atomic catches schema-level violations from yfinance |
| T-3-02 | Information Disclosure | data/macro.py _fetch_fred_yields | mitigate | Wrap fredapi.Fred(api_key=settings.FRED_API_KEY).get_series(...) in try/except; log only `error_type=type(e).__name__` and `series_id` — NEVER pass settings.FRED_API_KEY or `error=str(e)` to log calls (Fred exceptions may include URL with key in querystring); `test_no_secret_in_logs` asserts FRED_API_KEY does not appear in any captured structlog event from data/macro.py |
| T-3-03 | DoS | data/macro.py refresh_nyad | mitigate | Catch StaleOrEmptyError, ParserError (pandas.errors.ParserError), and broad Exception from stooq_module.fetch_ohlcv; route to _compute_breadth_fallback; emit nyad_source=r1000_proxy structured event; per RESEARCH Pitfall 1 this is the operative primary path today |
| T-3-04 | Tampering | data/macro.py write through write_macro_atomic | mitigate | All persistence routed through Phase 2 D-11 _write_parquet_atomic via persistence.write_macro_atomic — no hand-rolled writes; tempfile + os.replace prevents partial writes during cron interruptions |
</threat_model>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create src/screener/data/macro.py with 5 refresh functions + tenacity yfinance fetcher + breadth fallback + FRED yields fetcher</name>
  <files>src/screener/data/macro.py, src/screener/data/__init__.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/data/ohlcv.py (full file — module header lines 1-48, fetch_ohlcv lines 54-104, the Stooq fallback try/except shape lines 273-287, structured-log event registry lines 10-13)
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/data/stooq.py (full file — for the StaleOrEmptyError contract and column normalization)
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/data/__init__.py (current re-export pattern)
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/persistence.py (write_macro_atomic, read_panel, read_universe — Plan 03-01 added the macro writers)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 160-323 — `data/macro.py` analog mapping; lines 270-287 NYAD fallback pattern; lines 290-312 FRED fetcher idiom)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Pattern 1 — _safe wrapper; Pattern 6 lines 335-355 — _compute_breadth_fallback; Pattern 7 — schemas; Pitfall 1 — Stooq broken; Pitfall 4 — VIX close-only; Pitfall 5 — FRED weekend gaps; Pitfall 7 — yfinance index name normalization; Examples 5 — refresh-macro CLI body)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-CONTEXT.md (D-04, D-05, D-06 — exact source mapping and incremental-append rules)
  </read_first>
  <behavior>
    - Test: `from screener.data.macro import refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields, _compute_breadth_fallback, _fetch_yf_macro, _fetch_fred_yields` — all 8 symbols importable.
    - Test: `_fetch_yf_macro("SPY", "2024-01-01", date.today())` (with mock yf.download returning a synthetic 5-col OHLCV df) returns lowercase columns + index.name="date".
    - Test: `refresh_spy(force=True, today=date.today())` (with mock yf.download) writes `data/macro/spy.parquet` via `write_macro_atomic(df, "spy")`.
    - Test: `refresh_vix(force=True, today=date.today())` (with mock yf.download returning OHLCV) writes a CLOSE-ONLY frame (volume column dropped per Pitfall 4).
    - Test: `refresh_nyad` with `mock.patch("screener.data.macro.stooq_module.fetch_ohlcv", side_effect=StaleOrEmptyError("ParserError"))` falls back to `_compute_breadth_fallback`; structured log emits `nyad_source=r1000_proxy`.
    - Test: `refresh_nyad` with Stooq returning a series with > 5% NaN close (D-05 thin heuristic) also falls back to r1000_proxy.
    - Test: `refresh_yields` with `FRED_API_KEY=""` logs warning `skipping_yields_no_key` and writes an empty yields.parquet (no exception raised).
    - Test: No structlog event captured from `data/macro.py` contains the literal value of `FRED_API_KEY` (T-3-02 mitigation).
    - Test: `_compute_breadth_fallback` returns DataFrame with columns `{advances, declines, ad_line}` and date index.
  </behavior>
  <action>
**Step A — Create `src/screener/data/macro.py`** with the following structure. Copy idioms verbatim from `data/ohlcv.py` where indicated.

```python
"""macro — Phase 3 macro data layer (DAT-04).

Fetches 5 macro series and writes each to data/macro/<series>.parquet:
- SPY  : yfinance OHLCV
- QQQ  : yfinance OHLCV
- ^VIX : yfinance close-only (Volume=0 always per RESEARCH Pitfall 4)
- $NYAD: Stooq primary, R1000 breadth fallback (D-05; Stooq broken per Pitfall 1)
- yields: FRED DGS2/DGS10/T10Y2Y in single Parquet (NaN-as-received per Pitfall 5)

Layered-DAG contract (Phase 1 D-16 / tests/test_architecture.py): imports only
stdlib, third-party (yfinance, fredapi, pandas-datareader via stooq_module,
pandas, structlog, tenacity), screener.persistence, screener.config, and
intra-layer screener.data.stooq.

Structured-log event names:
- macro_fetch_start: {series, source}
- macro_fetch_success: {series, source, n_bars}
- macro_fetch_fail: {series, source, error_type, attempt}
- nyad_source: {source: stooq | r1000_proxy}
- skipping_yields_no_key: {}
- macro_snapshot_written: emitted by persistence.write_macro_atomic
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import structlog
import yfinance as yf
from fredapi import Fred
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from screener.config import get_settings
from screener.data import stooq as stooq_module
from screener.persistence import (
    StaleOrEmptyError,
    read_panel,
    read_universe,
    write_macro_atomic,
)

log = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# yfinance fetcher (mirrors data/ohlcv.py:fetch_ohlcv lines 54-104)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def _fetch_yf_macro(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Phase 2 D-10 idiom retargeted for SPY/QQQ/^VIX. Returns lowercase columns
    + index.name='date' (RESEARCH Pitfall 7)."""
    df = yf.download(
        ticker,
        start=str(start),
        auto_adjust=True,
        progress=False,
        threads=False,
        actions=False,
        multi_level_index=False,
    )
    if df is None or len(df) == 0:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")
    df = df.rename(columns=str.lower)
    if df.index.name is None or df.index.name.lower() != "date":
        df.index.name = "date"
    last = df.index[-1].date()
    if last < today - timedelta(days=4):
        raise StaleOrEmptyError(f"{ticker} stale: last bar {last}, today {today}")
    if not df.index.is_monotonic_increasing:
        raise StaleOrEmptyError(f"{ticker} non-monotonic index")
    if "close" not in df.columns:
        raise StaleOrEmptyError(f"{ticker} no close column; got {list(df.columns)}")
    if df["close"].isna().any():
        raise StaleOrEmptyError(f"{ticker} has null close")
    return df


def _project_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Project to MacroOhlcvSchema columns (open/high/low/close/volume) +
    int volume cast. Volume from yfinance is float — cast to int for schema."""
    out = df[["open", "high", "low", "close", "volume"]].copy()
    out["volume"] = out["volume"].fillna(0).astype("int64")
    return out


# ---------------------------------------------------------------------------
# Per-series refresh functions (D-04)
# ---------------------------------------------------------------------------


def refresh_spy(force: bool, today: date) -> Path:
    settings = get_settings()
    log.info("macro_fetch_start", series="spy", source="yfinance")
    df = _fetch_yf_macro("SPY", settings.MACRO_BACKFILL_START, today)
    df = _project_ohlcv(df)
    log.info("macro_fetch_success", series="spy", source="yfinance", n_bars=len(df))
    return write_macro_atomic(df, "spy")


def refresh_qqq(force: bool, today: date) -> Path:
    settings = get_settings()
    log.info("macro_fetch_start", series="qqq", source="yfinance")
    df = _fetch_yf_macro("QQQ", settings.MACRO_BACKFILL_START, today)
    df = _project_ohlcv(df)
    log.info("macro_fetch_success", series="qqq", source="yfinance", n_bars=len(df))
    return write_macro_atomic(df, "qqq")


def refresh_vix(force: bool, today: date) -> Path:
    """^VIX is close-only (Pitfall 4 — Volume=0 always)."""
    settings = get_settings()
    log.info("macro_fetch_start", series="vix", source="yfinance")
    df = _fetch_yf_macro("^VIX", settings.MACRO_BACKFILL_START, today)
    df = df[["close"]].copy()  # project to close-only per VixSchema
    log.info("macro_fetch_success", series="vix", source="yfinance", n_bars=len(df))
    return write_macro_atomic(df, "vix")


def refresh_nyad(force: bool, today: date) -> Path:
    """Stooq $NYAD primary; R1000-breadth fallback (D-05).
    Per RESEARCH Pitfall 1, Stooq is currently broken — fallback is operative
    primary today. Structured event nyad_source distinguishes the path used.
    """
    settings = get_settings()
    log.info("macro_fetch_start", series="nyad", source="stooq")
    df: pd.DataFrame
    try:
        stooq_df = stooq_module.fetch_ohlcv("$NYAD", settings.MACRO_BACKFILL_START, today)
        # D-05 thin-data heuristic: > 5% missing values triggers fallback
        if "close" in stooq_df.columns and stooq_df["close"].isna().mean() > 0.05:
            raise StaleOrEmptyError("$NYAD > 5% missing — falling back to r1000_proxy")
        # If Stooq ever recovers and returns valid OHLCV, derive advances/declines
        # from close.diff() — same shape as fallback.
        df = _stooq_to_breadth(stooq_df)
        log.info("nyad_source", source="stooq")
    except Exception as e:
        log.warning(
            "macro_fetch_fail",
            series="nyad",
            source="stooq",
            error_type=type(e).__name__,
        )
        df = _compute_breadth_fallback(settings.MACRO_BACKFILL_START, today)
        log.info("nyad_source", source="r1000_proxy")
    log.info("macro_fetch_success", series="nyad", source="resolved", n_bars=len(df))
    return write_macro_atomic(df, "nyad")


def refresh_yields(force: bool, today: date) -> Path:
    """FRED DGS2/DGS10/T10Y2Y. Stored as-received with NaN gaps (Pitfall 5).
    Empty Parquet on missing FRED_API_KEY (graceful — yields not in D-03 score).
    """
    settings = get_settings()
    if not settings.FRED_API_KEY:
        log.warning("skipping_yields_no_key")
        empty = pd.DataFrame(
            {"dgs2": pd.Series([], dtype="float64"),
             "dgs10": pd.Series([], dtype="float64"),
             "t10y2y": pd.Series([], dtype="float64")},
            index=pd.DatetimeIndex([], name="date"),
        )
        return write_macro_atomic(empty, "yields")
    log.info("macro_fetch_start", series="yields", source="fred")
    try:
        df = _fetch_fred_yields(settings.MACRO_BACKFILL_START, today)
    except Exception as e:
        # T-3-02: never pass `error=str(e)` (FRED URL with key may be in trace);
        # log only error_type.
        log.error("macro_fetch_fail", series="yields", source="fred", error_type=type(e).__name__)
        raise
    log.info("macro_fetch_success", series="yields", source="fred", n_bars=len(df))
    return write_macro_atomic(df, "yields")


# ---------------------------------------------------------------------------
# FRED fetcher (NEW idiom; tenacity wrapper + key sanitization)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def _fetch_fred_yields(start: str, today: date) -> pd.DataFrame:
    settings = get_settings()
    fred = Fred(api_key=settings.FRED_API_KEY)
    s2 = fred.get_series("DGS2", observation_start=start, observation_end=str(today))
    s10 = fred.get_series("DGS10", observation_start=start, observation_end=str(today))
    spread = fred.get_series("T10Y2Y", observation_start=start, observation_end=str(today))
    df = pd.DataFrame({"dgs2": s2, "dgs10": s10, "t10y2y": spread})
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# R1000 breadth fallback (RESEARCH Pattern 6, D-05)
# ---------------------------------------------------------------------------


def _stooq_to_breadth(stooq_df: pd.DataFrame) -> pd.DataFrame:
    """If Stooq returns valid $NYAD OHLCV, derive advances/declines from close.diff().
    Schema-shape compatible with NyadMacroSchema."""
    deltas = stooq_df["close"].diff()
    advances = (deltas > 0).astype("int64")
    declines = (deltas < 0).astype("int64")
    ad_line = (advances - declines).cumsum().astype("int64")
    out = pd.DataFrame({"advances": advances, "declines": declines, "ad_line": ad_line})
    out.index = stooq_df.index
    out.index.name = "date"
    return out


def _compute_breadth_fallback(start: str, today: date) -> pd.DataFrame:
    """R1000-derived advance-decline line (RESEARCH Pattern 6).
    Reads the most-recent universe snapshot, joins per-ticker prices,
    computes daily advances - declines.
    """
    universe_dir = Path(get_settings().UNIVERSE_CACHE_DIR)
    snaps = sorted(universe_dir.glob("*.parquet"))
    if not snaps:
        raise StaleOrEmptyError(
            "no universe snapshot available for r1000_proxy fallback"
        )
    snapshot_date = snaps[-1].stem
    panel = read_panel(snapshot_date)  # MultiIndex (ticker, date) panel
    closes = panel["close"].unstack(level="ticker")  # date × ticker wide frame
    deltas = closes.diff()
    advances = (deltas > 0).sum(axis=1).astype("int64")
    declines = (deltas < 0).sum(axis=1).astype("int64")
    ad_line = (advances - declines).cumsum().astype("int64")
    out = pd.DataFrame({"advances": advances, "declines": declines, "ad_line": ad_line})
    out.index.name = "date"
    out = out.loc[start:str(today)]
    return out
```

**Step B — Update `src/screener/data/__init__.py`** to re-export `macro` so `from screener.data import macro` works (mirroring the existing `ohlcv` / `stooq` / `universe` re-exports):

Read current state and append `from screener.data import macro` (or add `macro` to whatever re-export idiom is in use).
  </action>
  <verify>
    <automated>uv run python -c "from screener.data.macro import refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields, _compute_breadth_fallback, _fetch_yf_macro, _fetch_fred_yields, _stooq_to_breadth; from screener.data import macro; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `src/screener/data/macro.py` exists.
    - `grep -c "^def refresh_spy" src/screener/data/macro.py` returns 1.
    - `grep -c "^def refresh_qqq" src/screener/data/macro.py` returns 1.
    - `grep -c "^def refresh_vix" src/screener/data/macro.py` returns 1.
    - `grep -c "^def refresh_nyad" src/screener/data/macro.py` returns 1.
    - `grep -c "^def refresh_yields" src/screener/data/macro.py` returns 1.
    - `grep -c "^def _fetch_yf_macro" src/screener/data/macro.py` returns 1.
    - `grep -c "^def _fetch_fred_yields" src/screener/data/macro.py` returns 1.
    - `grep -c "^def _compute_breadth_fallback" src/screener/data/macro.py` returns 1.
    - `grep -c "from fredapi import Fred" src/screener/data/macro.py` returns 1.
    - `grep -c "from screener.data import stooq as stooq_module" src/screener/data/macro.py` returns 1.
    - `grep -c "df\\[\\[.close.\\]\\]" src/screener/data/macro.py` returns at least 1 (VIX close-only projection — Pitfall 4).
    - `grep -c "nyad_source" src/screener/data/macro.py` returns at least 2 (one for stooq path, one for r1000_proxy path).
    - `grep -c "skipping_yields_no_key" src/screener/data/macro.py` returns 1.
    - `grep -v '^#' src/screener/data/macro.py | grep -c "settings.FRED_API_KEY"` returns at most 2 (the conditional check + the Fred() init; never passed to log calls).
    - `grep -c "from screener.data import macro" src/screener/data/__init__.py` returns 1 (or equivalent re-export idiom).
    - `uv run python -c "from screener.data.macro import refresh_spy, _compute_breadth_fallback; from screener.data import macro; print('OK')"` exits 0 with `OK`.
    - `uv run mypy --config-file pyproject.toml src/screener/data/macro.py` exits 0 (note: `screener.data.*` may be under ignore_errors=True per pyproject; if so, mypy passes trivially — confirm via test).
    - `uv run ruff check src/screener/data/macro.py src/screener/data/__init__.py` exits 0.
    - Architecture test passes: `uv run pytest tests/test_architecture.py -x -q` exits 0 (data/macro.py imports only `persistence`, `config`, intra-layer `stooq`, plus stdlib + third-party).
  </acceptance_criteria>
  <done>data/macro.py created with 5 refresh fns, 3 helpers, tenacity wrapper, NYAD fallback, FRED secret-safe; data/__init__.py re-exports macro; ruff + mypy clean; architecture test passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fill refresh-macro CLI body, add `make macro` target, write 6 unit tests with mocks</name>
  <files>src/screener/cli.py, Makefile, tests/test_macro_refresh.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/cli.py (current state — 200 lines; refresh_universe template at lines 58-76, refresh_ohlcv at 91-155 for the configure_logging + try/except pattern; existing refresh-macro stub at lines 161-164)
    - /Users/belwinjulian/Desktop/SwingTrading/Makefile (current state — line 7 .PHONY list, line 16-20 `data:` target which already calls `uv run screener refresh-macro`)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_data_ohlcv.py (yfinance mock pattern lines 35-80)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_data_stooq.py (Stooq mock pattern lines 23-43)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_cli_smoke.py (D-14 surface assertion — confirm refresh-macro is in the locked 9-subcommand list and DO NOT modify it)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 683-737 — cli.py refresh-macro pattern + D-14 surface lock; lines 741-761 — Makefile target pattern; lines 999-1046 — tests/test_macro_refresh.py mock-and-patch patterns; lines 1141-1182 — conftest.py Phase 3 fixture extension)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Example 5 lines 769-794 — refresh-macro CLI body)
  </read_first>
  <behavior>
    - Test: `screener refresh-macro --help` shows the command (D-14 surface still has 9 subcommands).
    - Test: `screener refresh-macro` (with all 5 refresh_* mocked) exits 0 and emits `refresh_macro_ok`.
    - Test: `screener refresh-macro` with one mocked refresh_* raising exits 1, emits `refresh_macro_failed` with `error_type` field, and does NOT echo the exception details verbatim.
    - Test: `make macro` (in dry-run / shell-test mode) invokes `uv run screener refresh-macro`.
    - Test: `test_yf_invariants_applied` — `_fetch_yf_macro` with mock yf returning empty df raises StaleOrEmptyError; with valid df returns lowercase + date index.
    - Test: `test_nyad_fallback_to_r1000_proxy` — patches `stooq_module.fetch_ohlcv` to raise StaleOrEmptyError, patches `_compute_breadth_fallback` to return synthetic ad_line df; assert structured event `nyad_source` with `source=r1000_proxy` is emitted.
    - Test: `test_nyad_fallback_on_thin_stooq` — patches `stooq_module.fetch_ohlcv` to return df where 10% of close is NaN; assert fallback path taken.
    - Test: `test_yields_parquet_columns` — patches `Fred.get_series` to return synthetic series; assert `refresh_yields` writes a Parquet whose columns are exactly `{dgs2, dgs10, t10y2y}` with date index.
    - Test: `test_no_secret_in_logs` — sets `FRED_API_KEY="SUPER_SECRET_KEY_xyz"`, patches `Fred.get_series` to raise an exception; capture all structlog events emitted from `screener.data.macro`; assert "SUPER_SECRET_KEY_xyz" appears in NONE of them.
    - Test: `test_refresh_spy_writes_macro_parquet` — patches `_fetch_yf_macro`, asserts `data/macro/spy.parquet` is created via `write_macro_atomic`.
  </behavior>
  <action>
**Step A — Replace `refresh-macro` stub body in `src/screener/cli.py`** (find lines ~161-164 with the stub `def refresh_macro` body and replace).

DO NOT add a new typer command, DO NOT rename, DO NOT remove. The decorator `@app.command("refresh-macro")` and function name MUST stay byte-for-byte identical (D-14 surface lock).

```python
@app.command("refresh-macro")
def refresh_macro(
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-fetch from MACRO_BACKFILL_START even if cache exists."),
    ] = False,
) -> None:
    """Refresh macro inputs (SPY, QQQ, ^VIX, NYSE A/D, FRED yields). DAT-04."""
    configure_logging()
    today = date.today()
    try:
        from screener.data.macro import (
            refresh_nyad,
            refresh_qqq,
            refresh_spy,
            refresh_vix,
            refresh_yields,
        )
        refresh_spy(force=force, today=today)
        refresh_qqq(force=force, today=today)
        refresh_vix(force=force, today=today)
        refresh_nyad(force=force, today=today)
        refresh_yields(force=force, today=today)
        log.info("refresh_macro_ok")
    except Exception as e:
        log.error(
            "refresh_macro_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise typer.Exit(code=1) from e
```

**Step B — Add `macro:` target to `Makefile`.**

1. Update line 7 (`.PHONY:` line) to include `macro` if not already present.
2. Add a new recipe block (use TAB indentation, not spaces):

```makefile
macro:  ## Refresh macro inputs only (SPY, QQQ, ^VIX, NYSE A/D, FRED yields)
	uv run screener refresh-macro
```

The existing `data:` aggregate target already calls `refresh-macro`, so it picks up the real body automatically — no change needed to `data:`.

**Step C — Create `tests/test_macro_refresh.py`** with 6+ tests using mock + patch. Use the patterns in `tests/test_data_ohlcv.py` and `tests/test_data_stooq.py` as templates.

```python
"""Macro data layer tests (DAT-04, RESEARCH Pitfalls 1/4/5, Threats T-3-01..T-3-04).

Mocks:
- yfinance: mock.patch("screener.data.macro.yf.download", ...)
- Stooq: mock.patch("screener.data.macro.stooq_module.fetch_ohlcv", ...)
- FRED: mock.patch("screener.data.macro.Fred", ...) — patch the class import
- Persistence: monkeypatch _macro_dir to tmp_path
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import structlog
from structlog.testing import capture_logs

from screener.data import macro as macro_module
from screener.persistence import StaleOrEmptyError

REF_DATE = date(2026, 4, 30)


def _synthetic_yf_ohlcv(n: int = 252) -> pd.DataFrame:
    """yfinance-shape: PascalCase columns, date index unnamed."""
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=n)
    return pd.DataFrame(
        {
            "Open": np.full(n, 100.0),
            "High": np.full(n, 101.0),
            "Low": np.full(n, 99.0),
            "Close": np.full(n, 100.5),
            "Volume": np.full(n, 1_000_000, dtype="int64"),
        },
        index=idx,
    )


def _synthetic_breadth_df(n: int = 200) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=n)
    return pd.DataFrame(
        {"advances": np.full(n, 600, dtype="int64"),
         "declines": np.full(n, 400, dtype="int64"),
         "ad_line": np.arange(200, n + 200, dtype="int64")},
        index=pd.DatetimeIndex(idx, name="date"),
    )


def test_yf_invariants_applied() -> None:
    """_fetch_yf_macro applies the 4-invariant gate (lowercase + date index + close present)."""
    with mock.patch("screener.data.macro.yf.download", return_value=_synthetic_yf_ohlcv()):
        df = macro_module._fetch_yf_macro("SPY", "2024-01-01", REF_DATE)
    assert "close" in df.columns
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing


def test_yf_empty_raises_stale() -> None:
    empty = pd.DataFrame({"Close": []}, index=pd.DatetimeIndex([]))
    with mock.patch("screener.data.macro.yf.download", return_value=empty):
        with pytest.raises(StaleOrEmptyError, match="empty"):
            macro_module._fetch_yf_macro("SPY", "2024-01-01", REF_DATE)


def test_refresh_spy_writes_macro_parquet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh_spy routes through write_macro_atomic → _write_parquet_atomic."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    with mock.patch("screener.data.macro.yf.download", return_value=_synthetic_yf_ohlcv()):
        path = macro_module.refresh_spy(force=True, today=REF_DATE)
    assert path == macro_dir / "spy.parquet"
    assert path.exists()


def test_refresh_vix_drops_volume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RESEARCH Pitfall 4: ^VIX must be projected to close-only."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    with mock.patch("screener.data.macro.yf.download", return_value=_synthetic_yf_ohlcv()):
        path = macro_module.refresh_vix(force=True, today=REF_DATE)
    loaded = pd.read_parquet(path)
    assert list(loaded.columns) == ["close"], f"expected close-only; got {list(loaded.columns)}"


def test_nyad_fallback_to_r1000_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stooq raises (RESEARCH Pitfall 1) → falls back to _compute_breadth_fallback."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    with mock.patch(
        "screener.data.macro.stooq_module.fetch_ohlcv",
        side_effect=StaleOrEmptyError("ParserError"),
    ), mock.patch(
        "screener.data.macro._compute_breadth_fallback",
        return_value=_synthetic_breadth_df(),
    ):
        with capture_logs() as logs:
            macro_module.refresh_nyad(force=True, today=REF_DATE)
    sources = [e.get("source") for e in logs if e.get("event") == "nyad_source"]
    assert "r1000_proxy" in sources, f"expected r1000_proxy event; got logs={logs}"


def test_nyad_fallback_on_thin_stooq(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-05: > 5% missing close in Stooq triggers fallback."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    n = 200
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=n)
    close = np.full(n, 100.0)
    close[:20] = np.nan  # 10% missing
    thin = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close,
         "volume": np.full(n, 1_000_000, dtype="int64")},
        index=pd.DatetimeIndex(idx, name="date"),
    )
    with mock.patch(
        "screener.data.macro.stooq_module.fetch_ohlcv", return_value=thin
    ), mock.patch(
        "screener.data.macro._compute_breadth_fallback",
        return_value=_synthetic_breadth_df(),
    ):
        with capture_logs() as logs:
            macro_module.refresh_nyad(force=True, today=REF_DATE)
    sources = [e.get("source") for e in logs if e.get("event") == "nyad_source"]
    assert "r1000_proxy" in sources


def test_yields_parquet_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh_yields writes a Parquet with exactly {dgs2, dgs10, t10y2y} columns."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    monkeypatch.setattr(
        "screener.config.get_settings",
        lambda: type("S", (), {
            "FRED_API_KEY": "TEST_KEY",
            "MACRO_BACKFILL_START": "2024-01-01",
            "MACRO_CACHE_DIR": macro_dir,
        })(),
    )
    idx = pd.bdate_range(end=pd.Timestamp(REF_DATE), periods=100)
    series = pd.Series(np.full(100, 4.5), index=idx)

    fake_fred_instance = mock.MagicMock()
    fake_fred_instance.get_series.return_value = series
    with mock.patch("screener.data.macro.Fred", return_value=fake_fred_instance):
        path = macro_module.refresh_yields(force=True, today=REF_DATE)
    loaded = pd.read_parquet(path)
    assert set(loaded.columns) == {"dgs2", "dgs10", "t10y2y"}


def test_yields_skipped_without_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing FRED_API_KEY → warning emitted, empty Parquet written."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    monkeypatch.setattr(
        "screener.config.get_settings",
        lambda: type("S", (), {
            "FRED_API_KEY": "",
            "MACRO_BACKFILL_START": "2024-01-01",
            "MACRO_CACHE_DIR": macro_dir,
        })(),
    )
    with capture_logs() as logs:
        path = macro_module.refresh_yields(force=True, today=REF_DATE)
    events = [e.get("event") for e in logs]
    assert "skipping_yields_no_key" in events
    assert path.exists()


def test_no_secret_in_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T-3-02: FRED_API_KEY must NEVER appear in any structlog event from macro."""
    macro_dir = tmp_path / "macro"
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    secret = "SUPER_SECRET_KEY_xyz123_nobody_should_see"
    monkeypatch.setattr(
        "screener.config.get_settings",
        lambda: type("S", (), {
            "FRED_API_KEY": secret,
            "MACRO_BACKFILL_START": "2024-01-01",
            "MACRO_CACHE_DIR": macro_dir,
        })(),
    )

    fake_fred_instance = mock.MagicMock()
    fake_fred_instance.get_series.side_effect = RuntimeError(f"FRED returned 401 for url=https://api.fred.com/?key={secret}")
    with mock.patch("screener.data.macro.Fred", return_value=fake_fred_instance):
        with capture_logs() as logs:
            with pytest.raises(RuntimeError):
                macro_module.refresh_yields(force=True, today=REF_DATE)
    for entry in logs:
        for v in entry.values():
            assert secret not in str(v), f"secret leaked in log entry {entry}"
```

**Step D — DO NOT modify `tests/conftest.py`.** All synthetic frames used by `tests/test_macro_refresh.py` are module-local helpers (`_synthetic_yf_ohlcv`, `_synthetic_breadth_df`) defined inside the test file itself — this keeps Plan 03-02's `files_modified` orthogonal to Plan 03-03's, allowing parallel execution within Wave 2 with zero merge surface.

**Step E — Verify D-14 surface lock unchanged.** After modifying cli.py, run `uv run pytest tests/test_cli_smoke.py -x -q` — the D14_SUBCOMMANDS test must still pass (refresh-macro is one of the 9 locked subcommands and we did NOT add or rename anything).
  </action>
  <verify>
    <automated>uv run pytest tests/test_macro_refresh.py tests/test_cli_smoke.py -m "not slow and not integration" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c '@app.command("refresh-macro")' src/screener/cli.py` returns 1 (decorator unchanged).
    - `grep -c "from screener.data.macro import" src/screener/cli.py` returns 1.
    - `grep -c "refresh_spy(force=force, today=today)" src/screener/cli.py` returns 1.
    - `grep -c "refresh_macro_ok" src/screener/cli.py` returns 1.
    - `grep -c "refresh_macro_failed" src/screener/cli.py` returns 1.
    - `grep -E "^macro:" Makefile` returns one line.
    - `grep -E "^	uv run screener refresh-macro$" Makefile` returns at least one line (TAB-prefixed; the `data:` recipe also has this line).
    - `grep -c "^.PHONY:.* macro" Makefile` returns 1 (macro listed in PHONY).
    - `tests/test_macro_refresh.py` exists.
    - `grep -c "^def test_" tests/test_macro_refresh.py` returns at least 8.
    - `grep -c "test_no_secret_in_logs" tests/test_macro_refresh.py` returns 1.
    - `grep -c "test_nyad_fallback_to_r1000_proxy" tests/test_macro_refresh.py` returns 1.
    - `uv run pytest tests/test_macro_refresh.py -x -q` exits 0.
    - `uv run pytest tests/test_cli_smoke.py -x -q` exits 0 (D-14 surface still 9 subcommands).
    - `uv run ruff check src/screener/cli.py tests/test_macro_refresh.py` exits 0.
    - `uv run mypy --config-file pyproject.toml src/screener/cli.py` exits 0.
    - `uv run screener refresh-macro --help` exits 0 and stdout contains `--force`.
  </acceptance_criteria>
  <done>refresh-macro body filled (D-14 surface preserved); make macro target added; tests/test_macro_refresh.py created with 8+ tests including secret-safety (no conftest modification — test file uses module-local helpers); CLI smoke test still green; ruff + mypy clean.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_macro_refresh.py tests/test_cli_smoke.py tests/test_architecture.py -m "not slow and not integration" -x -q` exits 0
- `uv run ruff check src/screener/data/macro.py src/screener/data/__init__.py src/screener/cli.py tests/test_macro_refresh.py` exits 0
- `uv run mypy --config-file pyproject.toml src/screener/data/macro.py src/screener/cli.py` exits 0
- `uv run screener refresh-macro --help` exits 0
- `make -n macro` (dry-run) prints `uv run screener refresh-macro`
- D-14 surface lock test passes: `uv run pytest tests/test_cli_smoke.py::test_d14_subcommand_surface_locked -x -q` (or whatever the test is named) exits 0
- Architecture-test contract preserved: `uv run pytest tests/test_architecture.py -x -q` exits 0 (`data/macro.py` imports only allowed peers)
- All Phase 1 + 2 tests still green
</verification>

<success_criteria>
- 5 macro fetchers implemented (refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields)
- VIX is close-only (Pitfall 4); FRED yields are nullable as-received (Pitfall 5); ^VIX/SPY/QQQ all use Phase 2 D-10 tenacity + 4-invariant idiom verbatim
- $NYAD Stooq failure (ParserError per Pitfall 1) and thin-data heuristic (>5% missing per D-05) BOTH route to `_compute_breadth_fallback`; structured event `nyad_source` records the path used
- FRED_API_KEY missing → graceful warning + empty Parquet (yields not in D-03 score formula)
- T-3-02 mitigation tested: `test_no_secret_in_logs` confirms FRED_API_KEY never appears in any structlog event
- D-14 subcommand surface locked: refresh-macro filled in-place; no new subcommands added; `tests/test_cli_smoke.py` still green
- `make macro` target added; `data:` aggregate target unchanged (already referenced refresh-macro)
- 8+ unit tests in `tests/test_macro_refresh.py` cover yf invariants, NYAD Stooq fallback (both paths), VIX close-only projection, yields columns, skip-without-key, secret-safe logging, refresh_spy round-trip
- ruff + mypy clean on all touched files
</success_criteria>

<output>
After completion, create `.planning/phases/03-indicator-panel-regime/03-02-SUMMARY.md` documenting the macro layer, the operative-fallback observation (Stooq broken → r1000_proxy is default today), and the FRED secret-handling discipline. Note any deviations.
</output>
