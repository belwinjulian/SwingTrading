# Phase 3: Indicator Panel & Regime — Pattern Map

**Mapped:** 2026-05-10
**Files analyzed:** 18 (7 new modules · 8 modified · 7 test files)
**Analogs found:** 18 / 18 (every Phase 3 file maps to a Phase 1 / Phase 2 analog except `_safe_*` pandas-ta wrapper which is a NEW idiom documented in RESEARCH.md Pattern 1)

**Analog search scope:** `/Users/belwinjulian/Desktop/SwingTrading/src/screener/`, `/Users/belwinjulian/Desktop/SwingTrading/tests/`, `/Users/belwinjulian/Desktop/SwingTrading/.github/workflows/`, `/Users/belwinjulian/Desktop/SwingTrading/Makefile`, `/Users/belwinjulian/Desktop/SwingTrading/.env.example`, `/Users/belwinjulian/Desktop/SwingTrading/pyproject.toml`, `/Users/belwinjulian/Desktop/SwingTrading/.gitignore`.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/screener/indicators/__init__.py` (modify — add `build_panel()`) | indicators (orchestrator) | transform (panel-in / panel-out) | `src/screener/data/universe.py` `refresh_universe()` (composition fn) + RESEARCH Example 1 | role-match (composition) |
| `src/screener/indicators/trend.py` (new) | indicators (math, pure) | transform | `src/screener/data/ohlcv.py` shape but with no I/O; RESEARCH Example 2 (canonical idiom) | role-match (no exact analog — first pure indicator file) |
| `src/screener/indicators/relative_strength.py` (new) | indicators (math, pure) | transform | RESEARCH Pattern 2 (cross-sectional rank); shape-mirrors `trend.py` | role-match |
| `src/screener/indicators/volatility.py` (new) | indicators (math, pure) | transform | RESEARCH Examples 3 + Pattern 3 (ADR%); shape-mirrors `trend.py` | role-match |
| `src/screener/indicators/volume.py` (new) | indicators (math, pure) | transform | shape-mirrors `trend.py`; RESEARCH "Don't Hand-Roll" OBV row | role-match |
| `src/screener/regime.py` (modify — currently 7-line stub) | regime module (top-level) | transform + read | `src/screener/persistence.py` (top-level module shape) + RESEARCH Example 4 | role-match |
| `src/screener/data/macro.py` (new) | data adapter (network I/O) | request-response (yfinance/FRED) + fallback chain | `src/screener/data/ohlcv.py` (yfinance + tenacity + invariants + circuit-breaker) **and** `src/screener/data/stooq.py` (Stooq + StaleOrEmptyError) | exact (yf+tenacity) + exact (stooq fallback) |
| `src/screener/persistence.py` (modify — add 4 schemas + 4 helpers) | schema seam + atomic-write | CRUD (Parquet read/write + pandera validation) | EXISTING `OhlcvPanelSchema`, `_write_parquet_atomic`, `write_ohlcv_atomic`, `read_panel` (extend in-place) | exact |
| `src/screener/config.py` (modify — add 8 D-12 fields) | config (typed env) | additive Settings extension | EXISTING `Settings` class (Phase 2 D-20 added 8 fields the same way) | exact |
| `src/screener/cli.py` (modify — fill `refresh-macro` body) | CLI composition root | orchestration | EXISTING `refresh_universe` and `refresh_ohlcv` commands | exact |
| `Makefile` (modify — add `make macro` target) | build glue | orchestration | EXISTING `data:` target (which already calls `refresh-macro` stub) | exact |
| `.github/workflows/ci.yml` (modify — add EMA grep step) | CI tooling | shell test | EXISTING `lint` / `typecheck` / `test` jobs (single-runner shape) | role-match |
| `.env.example` (modify — mirror 8 D-12 fields) | config (template) | docs/env mirror | EXISTING `.env.example` (Phase 2 D-20 mirror precedent) | exact |
| `.gitignore` (modify — carve out `data/macro/*` and `data/rs_snapshots/*`) | repo policy | gitignore | EXISTING gitignore lines 31–43 (Phase 2 D-19 carve-out for `/data/`) | exact |
| `pyproject.toml` (verify — `fredapi` already pinned) | deps | manifest | EXISTING `dependencies = [...]` array | exact |
| `tests/test_indicators_panel.py` (new — `test_indicators_build_panel.py` per RESEARCH §Wave 0) | unit test | unit | `tests/test_persistence.py` (uses `_make_panel` helper + tmp_path + monkeypatch) | exact |
| `tests/test_indicators_purity.py` (new) | unit test | unit | EXISTING `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` (extend / parallel test) | exact |
| `tests/test_macro_refresh.py` (new — `test_data_macro.py` per RESEARCH §Wave 0) | unit + integration test | unit (`mock.patch`) | `tests/test_data_ohlcv.py` (mock yf.download) + `tests/test_data_stooq.py` (mock pdr.DataReader) | exact |
| `tests/test_regime.py` (new) | unit + golden-file test | unit | `tests/test_persistence.py` (synthetic fixture builders + tmp_path) + `tests/conftest.py` (synthetic OHLCV fixture pattern) | exact |
| `tests/test_regime_score.py` (new) | property test | property (hypothesis) | RESEARCH §Validation Architecture — Phase 3 first property test; pyproject already pins hypothesis | role-match |
| `tests/test_rs_snapshot.py` (new) | unit test | unit | `tests/test_persistence.py::test_atomic_write_crash_no_partial` + `test_empty_splits_schema_preserved` (atomic-write idiom + monkeypatch on `_ohlcv_dir`) | exact |
| `tests/conftest.py` (modify — extend with 4 new synthetic fixtures) | test fixtures | test scaffold | EXISTING `synthetic_ohlcv_*_df` fixtures (Phase 2 added them additively) | exact |

---

## Pattern Assignments

### `src/screener/persistence.py` (modify — add MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema, write_*_atomic + read_*)

**Analog:** `src/screener/persistence.py` itself — extend in place (do **not** create a new module; Phase 1 D-13 locked persistence as the schema seam).

**Existing imports + module header pattern** (lines 25–39 — `persistence.py`):
```python
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa
import structlog
from pandera.typing import Index, Series

from screener.config import get_settings

log = structlog.get_logger(__name__)
```
**Phase 3 keeps this header verbatim.** No new imports needed at module level (pandera, structlog, Path, tempfile, os already present).

**Schema definition pattern** (`OhlcvPanelSchema`, lines 76–100):
```python
class OhlcvPanelSchema(pa.DataFrameModel):
    """Multi-ticker long-format OHLCV panel with composite (ticker, date) index.

    Used at the data/ → indicators/ boundary. Columns are LOWERCASE (yfinance
    PascalCase is normalized at the data/ layer before reaching this schema).
    """

    ticker: Index[str] = pa.Field(check_name=True)
    date: Index[pd.Timestamp] = pa.Field(check_name=True)

    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    high: Series[float] = pa.Field(ge=0.0, nullable=False)
    low: Series[float] = pa.Field(ge=0.0, nullable=False)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    volume: Series[int] = pa.Field(ge=0, nullable=False)

    class Config:
        multiindex_strict = True
        multiindex_coerce = False
        strict = True
        coerce = False
```
**Phase 3 mirror:** `MacroOhlcvSchema` (single `date` Index, lowercase columns, `strict=True`, `coerce=False`). `VixSchema` is close-only Series (RESEARCH Pitfall 4: `^VIX` always has Volume=0). `RsSnapshotSchema` carries `ticker_raw_str`-style regex like `UniverseSchema` line 106 (`str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$"`) and `Series[pd.Int64Dtype]` for `rs_rating` (RESEARCH Pitfall 9: nullable Int64, NOT `int`). Concrete shapes are in RESEARCH Pattern 7 (lines 374–412).

**Atomic-write primitive — REUSE 1:1 — DO NOT redefine** (lines 154–176):
```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    """Write `df` to `target` atomically (POSIX same-filesystem rename)."""
    target.parent.mkdir(parents=True, exist_ok=True)  # covers data/macro/ and data/rs_snapshots/ auto-create (Pitfall 10)
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.to_parquet(tmp_path, engine="pyarrow", index=True)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```
**Phase 3 contract:** every new writer (`write_macro_atomic`, `write_rs_snapshot_atomic`) MUST call `_write_parquet_atomic(validated, target)` directly — no hand-rolled tempfile/replace block. The `mkdir(parents=True, exist_ok=True)` line covers `data/macro/` and `data/rs_snapshots/` auto-create on first run (RESEARCH Pitfall 10).

**Public writer pattern** (`write_universe_atomic`, lines 213–219; `write_ohlcv_atomic`, lines 222–241):
```python
def write_universe_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write a universe snapshot to data/universe/<date>.parquet."""
    validated = validate_at_write(UniverseSchema, df)
    target = _universe_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("snapshot_written", path=str(target), n_rows=len(validated))
    return target
```
**Phase 3 mirror — `write_rs_snapshot_atomic(df, snapshot_date)`:**
```python
def write_rs_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    validated = validate_at_write(RsSnapshotSchema, df)
    target = _rs_snapshot_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("rs_snapshot_written", path=str(target), n_rows=len(validated), snapshot_date=snapshot_date)
    return target
```
And similar `write_macro_atomic(df, series_name)` → `data/macro/{series_name}.parquet` for each of `spy`, `qqq`, `vix`, `nyad`, `yields`. The `_macro_dir()` and `_rs_snapshot_dir()` resolver helpers follow `_ohlcv_dir()` exactly (lines 193–207, getattr fallback for cross-wave Settings race safety):
```python
def _macro_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "MACRO_CACHE_DIR", "data/macro"))

def _rs_snapshot_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "RS_SNAPSHOT_DIR", "data/rs_snapshots"))
```

**Public reader pattern** (lines 276–292):
```python
def read_universe(snapshot_date: str) -> pd.DataFrame:
    path = _universe_dir() / f"{snapshot_date}.parquet"
    df = pd.read_parquet(path)
    return validate_at_read(UniverseSchema, df)
```
**Phase 3 mirror — `read_rs_snapshot`, `read_macro_spy`, `read_macro_vix`, `read_macro_yields`, `read_macro_nyad`** all follow this 3-line shape (`pd.read_parquet` → `validate_at_read(SchemaCls, df)`). No new I/O strategy.

**Validation policy (D-16 — REUSE)** (lines 141–148):
- `validate_at_write(SchemaCls, df)` (lazy=False) — eager, fail loud at the data/ write boundary.
- `validate_at_read(SchemaCls, df)` (lazy=True) — collect-all errors at the indicators/regime read boundary.
- Phase 3 follows the same policy: eager in `write_*_atomic`, lazy in `read_*`.

---

### `src/screener/data/macro.py` (new)

**Analogs:** `src/screener/data/ohlcv.py` (yfinance fetch + tenacity + 4-invariant gate + structured-log events) and `src/screener/data/stooq.py` (Stooq adapter for `$NYAD` attempt).

**Module header pattern** (`data/ohlcv.py` lines 1–48):
```python
"""OHLCV — yfinance fetcher + tenacity wrapper + post-fetch invariants
(D-08) + sentinel-bar refetch (D-07) + circuit-breaker orchestration (D-12)
+ splits ledger (D-18).

Layered-DAG contract: imports only stdlib, third-party, screener.persistence,
screener.config, and (intra-layer) screener.data.stooq.

Structured-log event names (Open Question 7 resolution):
- fetch_start: {command, n_universe} OR {ticker, source}
- fetch_success: {ticker, source, n_bars}
- fetch_fail:    {ticker, source, error, attempt}
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import structlog
import yfinance as yf
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
    make_empty_splits,
    write_ohlcv_atomic,
    write_splits_atomic,
)

log = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)
```
**Phase 3 macro.py mirror header:** copy verbatim, swap `yfinance + stooq` imports for the same set plus `from fredapi import Fred`, swap persistence imports for `write_macro_atomic`, `read_macro_*`, `_write_parquet_atomic`, `StaleOrEmptyError`. The architecture test (`tests/test_architecture.py` line 31, ALLOWED["data"]) permits `data/` to import only `persistence`, `config`, `obs` — `fredapi` is third-party and is allowed.

**yfinance fetcher with tenacity + 4-invariant gate** (`data/ohlcv.py` lines 54–104) — **copy verbatim, retarget for SPY/QQQ/^VIX**:
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
        auto_adjust=True,           # D-17: store adjusted only
        progress=False,
        threads=False,              # D-10: no batch/parallel
        actions=False,
        multi_level_index=False,    # Pitfall 9: yf 1.3.x default is True
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
```
**Phase 3 macro `_fetch_yf_macro(ticker, start, today)`** is this exact body, returning the same lowercase + `index.name='date'` shape. RESEARCH Pitfall 7 confirms this idiom is the single source of truth for column casing — copy verbatim, no defensive renames in callers.

**For VIX (close-only, RESEARCH Pitfall 4):** after `_fetch_yf_macro("^VIX", ...)`, project to `df[["close"]]` before validating against `VixSchema` — `^VIX` always has Volume=0 and is single-column-meaningful.

**Stooq adapter import + fallback chain** (`data/ohlcv.py` lines 273–287 — Stooq fallback path inside `run_with_breaker`):
```python
# Stooq fallback path. The Stooq adapter normalizes to lowercase
# + ascending and is responsible for naming its index "date";
# persistence.write_ohlcv_atomic accepts that shape directly.
try:
    df = stooq_module.fetch_ohlcv(ticker, settings.OHLCV_BACKFILL_START, today)
    write_ohlcv_atomic(ticker, df)
    splits_df = fetch_splits(ticker)
    write_splits_atomic(ticker, splits_df)
    stooq_ok += 1
    log.info("fetch_success", ticker=ticker, source="stooq", n_bars=len(df))
except Exception as e:
    failed.append(ticker)
    log.warning("fetch_fail", ticker=ticker, source="stooq", error=str(e), attempt=1)
```
**Phase 3 NYAD fallback chain** (D-05 + RESEARCH Pattern 6 + Pitfall 1) follows the same try/except shape, but the catch routes to `_compute_breadth_fallback()` instead of failing:
```python
def refresh_nyad(force: bool, today: date) -> Path:
    settings = get_settings()
    log.info("macro_fetch_start", series="nyad", source="stooq")
    try:
        df = stooq_module.fetch_ohlcv("$NYAD", settings.MACRO_BACKFILL_START, today)
        # Heuristic: > 5% missing values over 2005-present → fallback (D-05)
        if df["close"].isna().mean() > 0.05:
            raise StaleOrEmptyError("$NYAD > 5% missing — falling back to R1000 proxy")
        log.info("nyad_source", source="stooq")
    except (StaleOrEmptyError, Exception) as e:  # ParserError per RESEARCH Pitfall 1
        log.warning("macro_fetch_fail", series="nyad", source="stooq", error=str(e))
        df = _compute_breadth_fallback(settings.MACRO_BACKFILL_START, today)
        log.info("nyad_source", source="r1000_proxy")
    return write_macro_atomic(df, "nyad")
```
Note: RESEARCH Pitfall 1 confirms `nyad_source: r1000_proxy` is the operative primary path today (Stooq is broken).

**FRED yields fetcher pattern** (NEW idiom, but follows Phase 2 tenacity wrapper shape):
```python
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def _fetch_fred_yields(start: str, today: date) -> pd.DataFrame:
    settings = get_settings()
    if not settings.FRED_API_KEY:
        log.warning("skipping_yields_no_key")
        # RESEARCH Environment Availability table: skip gracefully; yields are not in D-03 score formula
        return pd.DataFrame(columns=["dgs2", "dgs10", "t10y2y"], index=pd.DatetimeIndex([], name="date"))
    fred = Fred(api_key=settings.FRED_API_KEY)
    s2 = fred.get_series("DGS2", observation_start=start, observation_end=str(today))
    s10 = fred.get_series("DGS10", observation_start=start, observation_end=str(today))
    spread = fred.get_series("T10Y2Y", observation_start=start, observation_end=str(today))
    df = pd.DataFrame({"dgs2": s2, "dgs10": s10, "t10y2y": spread})
    df.index.name = "date"
    # Store AS-RECEIVED with NaN gaps (RESEARCH Pitfall 5; Anti-Pattern: no ffill in data/macro.py)
    return df
```

**Structured log event names — copy from `data/ohlcv.py` line 10–13 verbatim** (D-08 contract):
- `macro_fetch_start: {series, source}` (mirrors `fetch_start: {ticker, source}`)
- `macro_fetch_success: {series, source, n_bars}` (mirrors `fetch_success`)
- `macro_fetch_fail: {series, source, error, attempt}` (mirrors `fetch_fail`)
- `nyad_source: {source: stooq | r1000_proxy}` (NEW Phase 3 event per CONTEXT.md D-05)
- `skipping_yields_no_key` (NEW Phase 3 event per RESEARCH Environment Availability)
- `rs_snapshot_written: {path, n_rows, snapshot_date}` (NEW; mirrors `snapshot_written` in `write_universe_atomic` line 218)

**`_compute_breadth_fallback()` — RESEARCH Pattern 6** lives in `data/macro.py` (NOT `indicators/`, which can't import `data/`). Reads via `persistence.read_panel(snapshot_date)` and `persistence.read_universe(snapshot_date)` (architecture test line 31 permits `data → persistence`).

---

### `src/screener/indicators/__init__.py` (modify — add `build_panel()`)

**Analog:** RESEARCH Example 1 (lines 562–591) — synthesis of Patterns 1+2+3.

**Current state** (`indicators/__init__.py` lines 1–7):
```python
"""indicators — pure-function indicator panel; no I/O, no global state.

Functions take pandas DataFrames in, return DataFrames with identical index.
SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4),
ATR(14), ADR%(20), OBV, RS percentile (universe-relative). May import only
`persistence` and `config` from inside the package.
"""
```
The string `EMAs` on line 4 is INSIDE A COMMENT and per RESEARCH Pitfall 6 the EMA grep gate is scoped only to `signals/minervini.py` and `indicators/trend.py` — `indicators/__init__.py` is intentionally NOT in the gate file list, so this comment stays unchanged.

**`build_panel()` orchestration shape** (RESEARCH Example 1):
```python
from __future__ import annotations
import pandas as pd

from screener.indicators.trend import sma_panel
from screener.indicators.volatility import atr_panel, adr_pct_panel
from screener.indicators.volume import obv_panel, dryup_ratio_panel
from screener.indicators.relative_strength import rs_panel
from screener.persistence import read_panel


def build_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Returns the OHLCV panel + 10 indicator columns. Pure function — reads
    from `persistence.read_panel()`; emits no I/O."""
    panel = read_panel(snapshot_date)  # MultiIndex (ticker, date), validated lazily
    panel = sma_panel(panel, lengths=(10, 20, 50, 150, 200))  # +5 cols
    panel = atr_panel(panel, length=14)                        # +1 col atr_14
    panel = adr_pct_panel(panel, length=20)                    # +1 col adr_pct
    panel = obv_panel(panel)                                   # +1 col obv
    panel = dryup_ratio_panel(panel, length=50)                # +1 col dryup_ratio
    panel = rs_panel(panel)                                    # +2 cols rs_raw, rs_rating
    return panel
```
**Architecture-test compliance** (`tests/test_architecture.py` line 32 ALLOWED["indicators"] = `{"persistence", "config", "obs"}`): `build_panel()` may import from `persistence` only. NO imports of `requests`, `yfinance`, `finnhub`, `fredapi`, `urllib`, `httpx`, `requests_cache`, `sqlite3`, `edgar`, `edgartools` (test line 167–177 forbidden_external set).

---

### `src/screener/indicators/trend.py` (new — SMA only; EMA grep-gated file)

**Analog:** RESEARCH Example 2 (lines 596–626).

**Module docstring (CRITICAL — must NOT contain `ema`):**
```python
"""trend — SMA panel computations. NO EMAs (CLAUDE.md §13.6 pitfall #4).

This module is the SMA-only file gated by the IND-02 CI grep — do not add
EMA code, do not even reference 'ema' in comments here.
"""
```
**ANTI-PATTERN — DO NOT ADD:** any string `ema` or `EMA` anywhere in this file (including comments, docstrings, variable names, type names) — RESEARCH Pitfall 6 + IND-02 CI gate scopes the grep to this file specifically. The substitute character — describe the contrast as "the moving average must not be exponentially weighted; use simple rolling means" with no acronym.

**`_safe_sma` wrapper — NEW Phase 3 idiom** (RESEARCH Pattern 1, Pitfall 2 — pandas-ta-classic returns `None` on short series):
```python
import pandas_ta_classic as ta

def _safe_sma(close: pd.Series, length: int) -> pd.Series:
    """Wrap ta.sma to return a NaN-filled Series when the input is shorter
    than `length`. pandas-ta-classic returns None in that case (verified
    live 2026-05-10 against pandas-ta-classic==0.4.47), which crashes
    downstream `.rename()` and DataFrame assembly.
    """
    result = ta.sma(close, length=length)
    if result is None:
        return pd.Series(float("nan"), index=close.index, name=f"SMA_{length}")
    return result
```
**`sma_panel()` per-ticker apply** (RESEARCH Example 2 + Pitfall 8 — must `groupby(level='ticker')` to prevent shift-across-ticker bleed):
```python
def sma_panel(panel: pd.DataFrame, lengths: tuple[int, ...] = (10, 20, 50, 150, 200)) -> pd.DataFrame:
    out = panel.copy()
    for L in lengths:
        col = f"sma_{L}"
        out[col] = (
            panel.groupby(level="ticker")["close"]
            .apply(lambda c: _safe_sma(c, L).reset_index(level=0, drop=True))
        )
    return out
```

**Pure-function discipline** (architecture test line 164–196 — `test_indicators_signals_pure_no_io_imports`): NO imports of any I/O package. ONLY `pandas`, `pandas_ta_classic`, `numpy` allowed. `from __future__ import annotations` at top.

---

### `src/screener/indicators/relative_strength.py` (new)

**Analog:** RESEARCH Pattern 2 (lines 250–279) — verified live 2026-05-10.

**Imports + signature pattern** (mirrors `trend.py`):
```python
"""relative_strength — IBD-style RS computation (cross-sectional, per-date)."""
from __future__ import annotations
import pandas as pd
```

**`rs_panel()` — verbatim from RESEARCH Pattern 2:**
```python
def rs_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute rs_raw and rs_rating for the (ticker, date) MultiIndex panel.

    Formula (CLAUDE.md §"Signal Formulas — IBD-style RS"):
        rs_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
        rs_rating = (rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(int)

    Cross-sectional rank within each date (groupby level='date'). NaN tickers
    (insufficient history) excluded from the ranking; receive NaN rs_rating.
    """
    by_ticker = panel.groupby(level="ticker")["close"]
    c_63  = by_ticker.shift(63)
    c_126 = by_ticker.shift(126)
    c_189 = by_ticker.shift(189)
    c_252 = by_ticker.shift(252)
    rs_raw = (
        2.0 * (panel["close"] / c_63)
        + (panel["close"] / c_126)
        + (panel["close"] / c_189)
        + (panel["close"] / c_252)
    )
    pct = rs_raw.groupby(level="date").rank(pct=True)
    rs_rating = (pct * 99).round().clip(1, 99)
    rs_rating = rs_rating.astype("Int64")  # nullable Int64 (RESEARCH Pitfall 9)
    out = panel.copy()
    out["rs_raw"] = rs_raw
    out["rs_rating"] = rs_rating
    return out
```
Critical notes:
- **Pitfall 8** — every per-ticker shift uses `.groupby(level="ticker").shift(N)`. Never naked `.shift(N)`.
- **Pitfall 9** — `rs_rating` is `pd.Int64Dtype` (capital I), NOT `int` or `'int64'`. Pandera schema in `RsSnapshotSchema` uses `Series[pd.Int64Dtype]` correspondingly.
- **Anti-pattern** (RESEARCH "Anti-Patterns to Avoid"): "Computing RS per-ticker and then ranking" — never iterate over tickers; always single Series + cross-sectional rank.

---

### `src/screener/indicators/volatility.py` (new)

**Analog:** RESEARCH Example 3 (lines 631–667).

**`_safe_atr()` + `atr_panel()`** (RESEARCH Pattern 1 wrapper applied to `ta.atr`):
```python
from __future__ import annotations
import pandas as pd
import pandas_ta_classic as ta

def _safe_atr(h: pd.Series, l: pd.Series, c: pd.Series, length: int) -> pd.Series:
    result = ta.atr(h, l, c, length=length)
    if result is None:
        return pd.Series(float("nan"), index=c.index, name=f"ATRr_{length}")
    return result

def atr_panel(panel: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Append atr_14 column (Wilder's RMA per docs/methodology.md §6).
    pandas-ta-classic default mamode='rma' is Wilder's smoothing.
    """
    out = panel.copy()
    def _per_ticker(g: pd.DataFrame) -> pd.Series:
        return _safe_atr(g["high"], g["low"], g["close"], length).reset_index(level=0, drop=True)
    out[f"atr_{length}"] = panel.groupby(level="ticker").apply(_per_ticker)
    return out
```

**`adr_pct_panel()` — RESEARCH Pattern 3, verified live (10.526 for high=105/low=95):**
```python
def adr_pct_panel(panel: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """ADR%(20) per CLAUDE.md §"Signal Formulas — ADR%":
        ADR_pct = 100 * (mean(high/low over 20 days) - 1)
    Per-ticker rolling — groupby level='ticker' so window doesn't span tickers.
    """
    out = panel.copy()
    ratio = panel["high"] / panel["low"]
    out["adr_pct"] = (
        100.0
        * (ratio.groupby(level="ticker").rolling(length).mean().droplevel(0) - 1.0)
    )
    return out
```

---

### `src/screener/indicators/volume.py` (new)

**Analog:** shape-mirrors `trend.py`; uses RESEARCH "Don't Hand-Roll" `pandas_ta_classic.obv` row.

**`_safe_obv()` + `obv_panel()` + `dryup_ratio_panel()`** (D-09: dryup formula `volume / SMA(volume, 50)`):
```python
from __future__ import annotations
import pandas as pd
import pandas_ta_classic as ta

def _safe_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    result = ta.obv(close, volume)
    if result is None:
        return pd.Series(float("nan"), index=close.index, name="OBV")
    return result

def obv_panel(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    def _per_ticker(g: pd.DataFrame) -> pd.Series:
        return _safe_obv(g["close"], g["volume"]).reset_index(level=0, drop=True)
    out["obv"] = panel.groupby(level="ticker").apply(_per_ticker)
    return out

def dryup_ratio_panel(panel: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """D-09: dryup_ratio = volume / SMA(volume, 50). Values < 0.5 = significant
    volume contraction. The 50d window aligns with the breakout-volume baseline
    in Phase 6 (VCP: breakout volume >= 1.5 * SMA(volume, 50)).
    """
    out = panel.copy()
    sma_vol = panel.groupby(level="ticker")["volume"].rolling(length).mean().droplevel(0)
    out["dryup_ratio"] = panel["volume"] / sma_vol
    return out
```

---

### `src/screener/regime.py` (modify — currently 7-line stub)

**Analog:** RESEARCH Example 4 (lines 671–763) + existing `regime.py` docstring.

**Architecture-test ALLOWED set** (`tests/test_architecture.py` line 34): `regime` may import from `{data, indicators, persistence, config, obs}`. Phase 3 uses all five — `data/macro.py` reads, `indicators/build_panel`, `persistence` macro readers, `config.get_settings`, `structlog`.

**Module header** (extend the existing 7-line stub):
```python
"""regime — universe-wide market-regime gate (one row per date).

Emits a discrete state in {Confirmed Uptrend, Uptrend Under Pressure,
Correction} plus a continuous regime_score in [0, 1]. Imports `data/`,
`indicators/`, and `persistence/`; consumed by `sizing` and `publishers/`.
"""
from __future__ import annotations
from typing import Literal

import pandas as pd
import structlog

from screener.config import get_settings
from screener.indicators import build_panel
from screener.persistence import (
    read_macro_spy,
    read_macro_vix,
)

log = structlog.get_logger(__name__)

RegimeState = Literal["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"]
```

**`_compute_distribution_days()` — RESEARCH Pattern 4** (verified live 2026-05-10):
```python
def _compute_distribution_days(spy: pd.DataFrame, window: int = 25) -> pd.Series:
    """Strict IBD definition (CONTEXT.md D-02):
       SPY close < prev_close by > 0.2% AND SPY volume > prev_volume.
       Count within rolling 25-session window.
    """
    prev_close = spy["close"].shift(1)
    prev_vol = spy["volume"].shift(1)
    is_dist_day = (spy["close"] / prev_close - 1.0 < -0.002) & (spy["volume"] > prev_vol)
    return is_dist_day.rolling(window).sum().fillna(0).astype(int)
```

**`_classify_state()` — D-01 priority chain (Correction > Pressure > Uptrend)** (RESEARCH Example 4 lines 691–715):
```python
def _classify_state(
    spy_above_200d: bool,
    breadth_pct: float,
    distribution_days: int,
    vix_level: float,
    settings,
) -> RegimeState:
    if (
        not spy_above_200d
        or distribution_days >= settings.REGIME_DIST_DAYS_CORRECTION
        or vix_level >= settings.REGIME_VIX_CORRECTION
    ):
        return "Correction"
    if (
        spy_above_200d
        and breadth_pct >= settings.REGIME_BREADTH_THRESHOLD * 100
        and distribution_days <= settings.REGIME_DIST_DAYS_PRESSURE - 1
        and vix_level < settings.REGIME_VIX_CONFIRMED
    ):
        return "Confirmed Uptrend"
    return "Uptrend Under Pressure"
```

**`_regime_score()` — RESEARCH Pattern 5 (vectorized, verified live):**
```python
def _regime_score(df: pd.DataFrame) -> pd.Series:
    """Vectorized D-03: SPY 30 / Breadth 40 / Dist 20 / VIX 10."""
    spy_component = df["spy_above_200d"].astype(float)
    breadth_norm  = (df["breadth_pct"] / 100.0).clip(0.0, 1.0)
    dist_norm     = (1.0 - df["distribution_days"] / 9.0).clip(0.0, 1.0)
    vix_norm      = (1.0 - (df["vix_level"] - 15.0) / 25.0).clip(0.0, 1.0)
    return 0.30*spy_component + 0.40*breadth_norm + 0.20*dist_norm + 0.10*vix_norm
```

**`compute_for_date()` and `build_history()`** (RESEARCH Example 4 lines 729–763 + CONTEXT.md "Claude's Discretion" — Regime module API).

**Breadth_pct denominator (RESEARCH Pitfall 11):** use `(close.notna() & sma_200.notna())` mask as denominator — tickers without 200d history don't participate. Add a unit test asserting the convention. Emit `regime_computed: {date, state, score}` structured event.

---

### `src/screener/config.py` (modify — additive Settings extension per D-12)

**Analog:** EXISTING `Settings` class (`config.py` lines 20–49) — Phase 2 D-20 added 8 fields the same way (lines 41–49).

**Existing additive pattern** (lines 26–49):
```python
class Settings(BaseSettings):
    """v1 application settings."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # External-service credentials
    FINNHUB_API_KEY: str = ""
    FRED_API_KEY: str = ""        # ALREADY PRESENT — Phase 3 reuses (no new field for FRED key)
    EDGAR_IDENTITY: str = ""

    # Universe selection
    UNIVERSE: str = "russell1000"

    # Indicator + sizing parameters
    RS_LOOKBACK_DAYS: int = 252
    RISK_PCT_PER_TRADE: float = 0.0075
    ACCOUNT_EQUITY: float = 100_000.0

    # Phase 2 (D-20) — data-layer paths and policy
    OHLCV_CACHE_DIR: Path = Path("data/ohlcv")
    UNIVERSE_CACHE_DIR: Path = Path("data/universe")
    OHLCV_BACKFILL_START: str = "2005-01-01"
    UNIVERSE_HEALTH_THRESHOLD: float = 0.95
    STOOQ_BREAKER_PROBE_N: int = 50
    STOOQ_BREAKER_THRESHOLD: float = 0.80
    OHLCV_FETCH_SLEEP_MIN_S: float = 0.5
    OHLCV_FETCH_SLEEP_MAX_S: float = 1.5
```

**Phase 3 D-12 additive block — APPEND verbatim, copying Phase 2's comment-block style:**
```python
    # Phase 3 (D-12) — macro + RS snapshot paths and regime thresholds
    MACRO_CACHE_DIR: Path = Path("data/macro")
    RS_SNAPSHOT_DIR: Path = Path("data/rs_snapshots")
    MACRO_BACKFILL_START: str = "2005-01-01"
    REGIME_BREADTH_THRESHOLD: float = 0.60
    REGIME_DIST_DAYS_PRESSURE: int = 5
    REGIME_DIST_DAYS_CORRECTION: int = 9
    REGIME_VIX_CORRECTION: float = 30.0
    REGIME_VIX_CONFIRMED: float = 20.0
```
**`get_settings()` cached singleton (lines 52–60) — REUSE 1:1**, no changes; existing `lru_cache(maxsize=1)` covers the new fields automatically.

---

### `src/screener/cli.py` (modify — fill `refresh-macro` body)

**Analog:** EXISTING `refresh-universe` (lines 58–76) and `refresh-ohlcv` (lines 91–155) command bodies + RESEARCH Example 5 (lines 769–794).

**Existing command pattern** (lines 58–76):
```python
@app.command("refresh-universe")
def refresh_universe(
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-write this ISO week's snapshot even if it exists."),
    ] = False,
) -> None:
    """Refresh the Russell 1000 universe (iShares IWB CSV); weekly Parquet snapshot (D-01, D-02)."""
    configure_logging()
    try:
        written = refresh_universe_impl(force=force, today=date.today())
    except Exception as e:
        log.error("refresh_universe_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
    if written is None:
        log.info("refresh_universe_skipped", reason="snapshot already exists for this ISO week")
```

**Phase 3 — replace existing `refresh_macro` stub (lines 161–164)** with the real body following the `refresh_universe` template (RESEARCH Example 5):
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
            refresh_spy, refresh_qqq, refresh_vix,
            refresh_nyad, refresh_yields,
        )
        refresh_spy(force=force, today=today)
        refresh_qqq(force=force, today=today)
        refresh_vix(force=force, today=today)
        refresh_nyad(force=force, today=today)  # logs nyad_source: stooq | r1000_proxy
        refresh_yields(force=force, today=today)
        log.info("refresh_macro_ok")
    except Exception as e:
        log.error("refresh_macro_failed", error=str(e), error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

**CRITICAL — D-14 surface lock**: `tests/test_cli_smoke.py` D14_SUBCOMMANDS test asserts the 9-subcommand surface is locked. Phase 3 MUST NOT add or rename a subcommand — `refresh-macro` is already in the surface (line 161); we only fill its body.

**`_latest_universe_snapshot()` helper** (cli.py lines 81–88) — Phase 3 may call this from `data/macro.py:_compute_breadth_fallback()` per RESEARCH Pattern 6. RESEARCH note line 343–344: "snap = _latest_universe_snapshot()  # cli.py helper; promote into persistence". The planner should decide: either (a) move the helper into `persistence.py` and import from both, or (b) re-implement in `data/macro.py` (simple `Path.glob("*.parquet")` + sort).

---

### `Makefile` (modify — add `make macro` target)

**Analog:** EXISTING `data:` target (Makefile lines 16–20) which already calls `refresh-macro` as part of the daily DAG.

**Existing pattern** (Makefile lines 16–20):
```makefile
data:  ## Refresh universe, OHLCV, macro, and fundamentals (Phase 1: stub no-ops)
    uv run screener refresh-universe
    uv run screener refresh-ohlcv
    uv run screener refresh-macro
    uv run screener refresh-fundamentals
```

**Phase 3 — add the new `macro:` target alongside existing targets** (line 7 `.PHONY` and add a new recipe):
```makefile
.PHONY: help setup data macro rank report backtest backtest-audit journal lint typecheck test all clean

macro:  ## Refresh macro inputs only (SPY, QQQ, ^VIX, NYSE A/D, FRED yields)
    uv run screener refresh-macro
```
The `data:` aggregate target already calls `refresh-macro`, so it picks up the real body automatically.

---

### `.github/workflows/ci.yml` (modify — add EMA grep step)

**Analog:** EXISTING `lint` / `typecheck` / `test` jobs (CI yaml lines 17–84) — single-job, single-runner pattern.

**Existing job shape** (CI yaml lines 17–40):
```yaml
  lint:
    name: lint
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      - name: Install uv
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e  # v6.8.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python from pyproject
        run: uv python install

      - name: Install dependencies (frozen)
        run: uv sync --frozen --extra dev

      - name: ruff format --check
        run: uv run ruff format --check .

      - name: ruff check
        run: uv run ruff check .
```

**Phase 3 — add a `sma-not-ema-gate` step inside the existing `lint` job, after `ruff check`** (RESEARCH Pitfall 6 + Assumption A5 — file may not exist when CI runs first):
```yaml
      - name: SMA-not-EMA gate (IND-02)
        run: |
          if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then
            echo "ERR: 'ema' reference found in SMA-only files. See IND-02 / CLAUDE.md §13.6 pitfall #4."
            exit 1
          fi
```
**Critical detail (RESEARCH Pitfall 6 + A5):** the `2>/dev/null` is REQUIRED because `signals/minervini.py` doesn't exist until Phase 4 — without stderr redirect, `grep` exits with status 2 and breaks CI on Phase 3 PR. The `-i` flag is case-insensitive (matches `EMA`, `Ema`, `ema`); `-l` lists matched filenames; `-E` enables extended regex.

**Use `grep` not `rg`** — RESEARCH Environment Availability table confirms ripgrep is NOT preinstalled on `ubuntu-latest` runner (Assumption A5, LOW confidence but mitigation works either way).

---

### `.env.example` (modify — mirror 8 D-12 fields)

**Analog:** EXISTING `.env.example` lines 32–39 (Phase 2 D-20 added 8 fields the same way).

**Existing Phase 2 mirror block** (lines 32–39):
```
# Phase 2 — data-layer paths and policy (D-20)
OHLCV_CACHE_DIR=data/ohlcv
UNIVERSE_CACHE_DIR=data/universe
OHLCV_BACKFILL_START=2005-01-01
UNIVERSE_HEALTH_THRESHOLD=0.95
STOOQ_BREAKER_PROBE_N=50
STOOQ_BREAKER_THRESHOLD=0.80
OHLCV_FETCH_SLEEP_MIN_S=0.5
OHLCV_FETCH_SLEEP_MAX_S=1.5
```

**Phase 3 — APPEND new mirror block at end of file:**
```
# Phase 3 — macro + RS snapshot paths and regime thresholds (D-12)
MACRO_CACHE_DIR=data/macro
RS_SNAPSHOT_DIR=data/rs_snapshots
MACRO_BACKFILL_START=2005-01-01
REGIME_BREADTH_THRESHOLD=0.60
REGIME_DIST_DAYS_PRESSURE=5
REGIME_DIST_DAYS_CORRECTION=9
REGIME_VIX_CORRECTION=30.0
REGIME_VIX_CONFIRMED=20.0
```
Pattern: name = string default (no quotes for paths; raw numbers for ints/floats). One-line comment header naming the phase + decision ID.

---

### `.gitignore` (modify — carve out `data/macro/*` and `data/rs_snapshots/*`)

**Analog:** EXISTING gitignore lines 31–43 (Phase 2 D-19 carve-out for `/data/`).

**Existing Phase 2 carve-out pattern** (lines 31–43):
```
# Output directories — selective carve-out for committed audit artifacts.
# Anchored to repo root so source-layer dirs (src/screener/data/) are NOT
# ignored. Universe Parquet snapshots and per-ticker splits ledgers ARE
# committed (small, audit-relevant); per-ticker prices.parquet stays local.
# Phase 1 originally said `/data/`; Phase 2 (D-19 reconciled with D-06 per
# Amendment 2026-05-02) carves out two committed paths.
/data/*
!/data/universe/
!/data/universe/.gitkeep
!/data/ohlcv/
/data/ohlcv/**/prices.parquet
!/data/ohlcv/**/splits.parquet
!/data/ohlcv/**/.gitkeep
```

**Phase 3 carve-out (D-11):** `/data/*` already ignores `data/macro/` and `data/rs_snapshots/` (the leading `/data/*` line catches every subdir). Phase 3 just needs to NOT add carve-outs for them — they remain gitignored by default. Optional `.gitkeep` if planner wants directory existence:
```
# Phase 3 (D-11) — macro and RS snapshot caches stay local (D-19 default)
# data/macro/* and data/rs_snapshots/* gitignored by the leading /data/* rule
# (no negation — these are large, re-creatable from `make macro` / `make rank`).
```
**No actual lines need to be added to `.gitignore`** — the existing `/data/*` rule already covers Phase 3's directories. The planner should verify by running `git check-ignore -v data/macro/spy.parquet` after creating any test macro file.

---

### `pyproject.toml` (verify — `fredapi` already pinned)

**Verified pinned** (pyproject.toml line 30): `"fredapi>=0.5.2,<0.6"` — already in the `dependencies` array. No change needed.

**Mypy override** (pyproject.toml line 102) already includes `fredapi` in `ignore_missing_imports` set, and `screener.data.*` is under `ignore_errors = true` (line 78–79). Phase 3's `data/macro.py` inherits the existing override.

**Architecture-test ALLOWED** (`tests/test_architecture.py` line 31): `data` may import only `{persistence, config, obs}` plus stdlib + third-party. `fredapi`, `yfinance`, `pandas-datareader` are third-party — allowed.

---

### `tests/test_indicators_panel.py` (new — `test_indicators_build_panel.py` per RESEARCH Wave 0)

**Analog:** `tests/test_persistence.py` (synthetic-fixture + tmp_path + monkeypatch pattern).

**Existing imports + helpers pattern** (test_persistence.py lines 1–61):
```python
"""Persistence schema + atomic-write tests (DAT-09, DAT-08, DAT-03).

Covers the 9 tests in 02-VALIDATION.md lines 52-59. Uses synthetic fixtures
from tests/conftest.py — no network, no live yfinance / iShares calls.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa
import pytest

from screener.persistence import (
    OhlcvPanelSchema,
    SplitsSchema,
    UniverseSchema,
    _write_parquet_atomic,
    make_empty_splits,
    read_panel,
    read_splits,
    validate_at_read,
    validate_at_write,
    write_ohlcv_atomic,
    write_splits_atomic,
    write_universe_atomic,
)


def _make_panel(close_vals: list[float], open_vals: list[float] | None = None) -> pd.DataFrame:
    n = len(close_vals)
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=n)],
        names=["ticker", "date"],
    )
    return pd.DataFrame(
        {
            "open": open_vals if open_vals is not None else [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": close_vals,
            "volume": [1_000_000] * n,
        },
        index=idx,
    )
```
**Phase 3 reuse:** copy this `_make_panel()` helper as the seed for `tests/test_indicators_*.py` (or extend it in `conftest.py` as a shared fixture). Add a `_make_multi_ticker_panel(tickers, n_days, close_init)` variant for cross-sectional RS tests.

**Round-trip test pattern with monkeypatched dirs** (test_persistence.py lines 161–192):
```python
def test_read_panel_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ohlcv_dir = tmp_path / "ohlcv"
    universe_dir = tmp_path / "universe"
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: ohlcv_dir)
    monkeypatch.setattr("screener.persistence._universe_dir", lambda: universe_dir)
    universe = pd.DataFrame({...})
    write_universe_atomic(universe, "2026-04-27")
    ...
    panel = read_panel("2026-04-27")
    assert panel.index.names == ["ticker", "date"]
```
**Phase 3 mirror — `test_indicators_panel.py` round-trip:** monkeypatch `_ohlcv_dir` and `_universe_dir`, write 2 tickers × 252 bars, call `build_panel("2026-04-27")`, assert 10 new columns are present, assert `(ticker, date)` MultiIndex preserved, assert short-history ticker has NaN in `sma_200` and `rs_rating`.

**Required test functions** (RESEARCH §Phase Requirements → Test Map):
- `test_build_panel_returns_10_new_cols` (IND-01)
- `test_build_panel_preserves_multiindex` (IND-01)
- `test_short_history_nan_warmup` (IND-01, D-08)
- `test_safe_sma_short_series_returns_nan_series` — covers `_safe_sma(close, 200)` on 50-bar Series returns NaN-Series, NOT `None` (RESEARCH Pitfall 2)

---

### `tests/test_indicators_purity.py` (new — IND-05 architecture invariant)

**Analog:** EXISTING `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` (lines 164–196) — already enforces the invariant.

**Existing test** (already passes — NEW test is a parallel/extension):
```python
def test_indicators_signals_pure_no_io_imports(src_screener: Path) -> None:
    """indicators/ and signals/ MUST NOT import requests/yfinance/finnhub/edgartools/sqlite3/etc."""
    forbidden_external = {
        "requests", "yfinance", "finnhub", "edgar", "edgartools", "fredapi",
        "sqlite3", "urllib", "urllib3", "httpx", "requests_cache",
    }
    for layer in ("indicators", "signals"):
        layer_dir = src_screener / layer
        if not layer_dir.exists():
            continue
        for path in _iter_source_files(layer_dir):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module.split(".")[0]]
                for name in names:
                    assert name not in forbidden_external, (
                        f"{path}: layer '{layer}' imports I/O package "
                        f"'{name}' — pure-function discipline violated."
                    )
```
**Phase 3 NEW test (`test_indicators_purity.py`):** complementary functional purity check — call `build_panel()` twice with the same input, assert identical output (no global state); call with read-only input panel, assert input is not mutated (defensive `.copy()` per Examples 2/3).

---

### `tests/test_macro_refresh.py` (new — `test_data_macro.py`)

**Analogs:** `tests/test_data_ohlcv.py` (yf.download mock pattern, lines 35–80) and `tests/test_data_stooq.py` (pdr.DataReader mock pattern).

**yfinance mock pattern** (`test_data_ohlcv.py` lines 35–42):
```python
def test_fetch_all_invariants_pass(synthetic_ohlcv_valid_df: pd.DataFrame) -> None:
    with mock.patch("screener.data.ohlcv.yf.download", return_value=synthetic_ohlcv_valid_df):
        df = fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
    assert len(df) > 0
    assert "close" in df.columns or "Close" in df.columns
    assert df.index.name is None or df.index.name.lower() == "date"
```
**Phase 3 mirror:** `mock.patch("screener.data.macro.yf.download", return_value=synthetic_ohlcv_valid_df)`, then assert SPY/QQQ/VIX paths return correctly-shaped frames.

**Stooq fallback test pattern** (`test_data_stooq.py` lines 23–43):
```python
def test_normalize_columns_and_order(synthetic_stooq_descending_df: pd.DataFrame) -> None:
    with mock.patch(
        "screener.data.stooq.pdr.DataReader", return_value=synthetic_stooq_descending_df
    ):
        df = fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
    assert df.index.is_monotonic_increasing
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}

def test_empty_raises() -> None:
    empty = pd.DataFrame({"Open": [], ...}, index=pd.DatetimeIndex([]))
    with mock.patch("screener.data.stooq.pdr.DataReader", return_value=empty):
        with pytest.raises(StaleOrEmptyError, match="empty"):
            fetch_ohlcv("AAPL", "2024-01-01", REF_DATE)
```
**Phase 3 mirror — NYAD fallback test:**
```python
def test_nyad_fallback_to_r1000_proxy() -> None:
    """Stooq raises (per RESEARCH Pitfall 1) → falls back to _compute_breadth_fallback."""
    with mock.patch("screener.data.macro.stooq_module.fetch_ohlcv", side_effect=StaleOrEmptyError("ParserError")):
        with mock.patch("screener.data.macro._compute_breadth_fallback", return_value=<synthetic ad_line df>):
            refresh_nyad(force=True, today=REF_DATE)
    # Assert structured log emitted nyad_source=r1000_proxy
```

**Required test functions** (RESEARCH Wave 0 + Phase Requirements → Test Map):
- `test_refresh_all_writes_files` (DAT-04, marked `@pytest.mark.integration`)
- `test_yf_invariants_applied` (DAT-04, reuse Phase 2 idiom)
- `test_nyad_fallback_to_r1000_proxy` (DAT-04, D-05)
- `test_nyad_fallback_on_thin_stooq` (D-05 heuristic: > 5% missing)
- `test_yields_parquet_columns` (DAT-04)
- `test_no_secret_in_logs` (RESEARCH Security Recommendation 1)

---

### `tests/test_regime.py` (new — REG-01..04 + golden-file tests)

**Analog:** `tests/test_persistence.py` synthetic-builder pattern + RESEARCH §"Golden-file fixture design" (synthetic SPY/VIX series with deterministic distribution-day positions).

**Synthetic SPY+VIX fixture pattern** (extend conftest.py):
```python
def _make_synthetic_spy_for_correction(
    start: str, end: str, sma_break_dates: list[str]
) -> pd.DataFrame:
    """Build a synthetic SPY OHLCV series whose close crosses below 200d SMA
    at known dates. Deterministic — used by REG-04 golden-file tests.
    """
    idx = pd.bdate_range(start=start, end=end)
    close = np.full(len(idx), 100.0)
    # Inject a sharp drop on each break date
    for d in sma_break_dates:
        i = idx.get_loc(pd.Timestamp(d))
        close[i:] *= 0.7  # 30% drop
    return pd.DataFrame({"open": close, "high": close*1.01, "low": close*0.99, "close": close, "volume": [1_000_000]*len(idx)}, index=pd.DatetimeIndex(idx, name="date"))
```

**Required test functions (RESEARCH Wave 0):**
- `test_compute_for_date_columns` — REG-01: 6 columns present
- `test_distribution_day_idiom` — REG-01: `_compute_distribution_days` correctness on a hand-picked fixture
- `test_regime_state_enum` — REG-02: discrete state ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction}
- `test_correction_overrides_pressure` — REG-02 D-01 priority
- `test_regime_score_seam_exists` — REG-03 column exists
- `test_2008q4_correction` — REG-04 golden-file (date range 2008-10-01 to 2009-03-01, ≥1 Correction)
- `test_2020q1_correction` — REG-04 golden-file (2020-02-15 to 2020-04-15)
- `test_2022h1_correction` — REG-04 golden-file (2022-01-01 to 2022-07-01)
- `test_breadth_pct_denominator_uses_valid_sma` — RESEARCH Pitfall 11 convention test

---

### `tests/test_regime_score.py` (new — property test using hypothesis)

**Analog:** No existing property test; pyproject.toml line 46 pins `hypothesis>=6,<7`. RESEARCH §Validation Architecture confirms first property test in the project.

**Pattern:**
```python
from hypothesis import given, strategies as st

@given(
    spy_above=st.booleans(),
    breadth=st.floats(min_value=0.0, max_value=100.0),
    dist=st.integers(min_value=0, max_value=20),
    vix=st.floats(min_value=10.0, max_value=80.0),
)
def test_regime_score_in_unit_interval(spy_above, breadth, dist, vix):
    df = pd.DataFrame({
        "spy_above_200d": [spy_above],
        "breadth_pct": [breadth],
        "distribution_days": [dist],
        "vix_level": [vix],
    })
    score = _regime_score(df).iloc[0]
    assert 0.0 <= score <= 1.0
```

---

### `tests/test_rs_snapshot.py` (new)

**Analog:** `tests/test_persistence.py::test_atomic_write_crash_no_partial` (lines 133–145) and `test_empty_splits_schema_preserved` (lines 151–158).

**Atomic-write crash test pattern** (test_persistence.py lines 133–145):
```python
def test_atomic_write_crash_no_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "x.parquet"
    df = pd.DataFrame({"a": [1, 2, 3]})

    def _raise(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
        raise OSError("simulated mid-write crash")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise)
    with pytest.raises(OSError):
        _write_parquet_atomic(df, target)
    assert not target.exists(), "target Parquet must not exist after a mid-write crash"
    leftover = list(tmp_path.glob(".x.parquet.*.tmp"))
    assert leftover == [], f"No tmp residue should remain; found {leftover}"
```
**Phase 3 mirror:** apply same crash test to `write_rs_snapshot_atomic` → assert no `data/rs_snapshots/<date>.parquet` partial after `to_parquet` raises. Round-trip test: write 1000-ticker `RsSnapshotSchema`-shaped df, read back, assert preserved.

**Required test functions (RESEARCH Wave 0):**
- `test_rs_snapshot_atomic_write` (Persistence)
- `test_rs_snapshot_round_trip`
- `test_rs_snapshot_schema_rejects_bad_rating` — non-Int64 dtype raises (RESEARCH Pitfall 9)
- `test_read_macro_spy_validates` — lazy validation against `MacroOhlcvSchema`

---

### `tests/conftest.py` (modify — extend with 4 new synthetic fixtures)

**Analog:** EXISTING `tests/conftest.py` (Phase 2 synthetic fixtures, lines 39–258).

**Existing additive pattern** (lines 24–27, 39–42, 124–127, 205–208, 241–245):
```python
# --- Phase 1 fixtures (KEEP unchanged) --------------------------------------
...
# --- Phase 2 OHLCV fixtures -------------------------------------------------
...
# --- Phase 2 iShares CSV fixtures (BYTES, encoded UTF-8 with BOM) ----------
...
# --- Phase 2 sentinel-mismatch fixture --------------------------------------
...
# --- Phase 2 Stooq-shaped fixture -------------------------------------------
```

**Phase 3 — APPEND new section** (RESEARCH Wave 0 last bullet):
```python
# --- Phase 3 indicator + regime fixtures -----------------------------------

@pytest.fixture(scope="session")
def synthetic_short_history_panel() -> pd.DataFrame:
    """50-bar single-ticker panel — exercises SMA200 NaN warmup path (D-08)."""
    ...

@pytest.fixture(scope="session")
def synthetic_multi_ticker_panel() -> pd.DataFrame:
    """5-ticker × 252-bar MultiIndex panel for RS cross-sectional tests."""
    ...

@pytest.fixture(scope="session")
def synthetic_spy_2008q4() -> pd.DataFrame:
    """Synthetic SPY OHLCV crossing 200d SMA on 2008-09-15 (REG-04 golden-file)."""
    ...

@pytest.fixture(scope="session")
def synthetic_vix_panic() -> pd.DataFrame:
    """Synthetic ^VIX series with a spike >= 30 (Correction trigger D-01)."""
    ...
```
Pattern: `@pytest.fixture(scope="session")`, deterministic seeded numpy / `pd.bdate_range(end=_REF_DATE, periods=N)`, lowercase columns, `index.name="date"`.

---

## Shared Patterns

### Atomic Parquet Write (D-11)
**Source:** `src/screener/persistence.py` lines 154–176 (`_write_parquet_atomic`)
**Apply to:** Every Phase 3 writer in `persistence.py` — `write_macro_atomic`, `write_rs_snapshot_atomic`, and any other new writer. NEVER hand-roll a tempfile + os.replace block.
```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.to_parquet(tmp_path, engine="pyarrow", index=True)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

### Validation Policy (D-16)
**Source:** `src/screener/persistence.py` lines 141–148 (`validate_at_write`, `validate_at_read`)
**Apply to:** Every new writer/reader in Phase 3.
- **Eager** (`validate_at_write`, `lazy=False`) at the data/ → persistence write boundary so a bad row aborts loud.
- **Lazy** (`validate_at_read`, `lazy=True`) at the persistence → indicators/regime read boundary so multiple errors surface together.
```python
def validate_at_write(schema_cls, df): return schema_cls.validate(df, lazy=False)
def validate_at_read(schema_cls, df):  return schema_cls.validate(df, lazy=True)
```

### Pandera Schema Definition (D-15)
**Source:** `src/screener/persistence.py` lines 76–135 (`OhlcvPanelSchema`, `UniverseSchema`, `SplitsSchema`)
**Apply to:** All 5 new Phase 3 schemas (`MacroOhlcvSchema`, `VixSchema`, `YieldsSchema`, `NyadMacroSchema`, `RsSnapshotSchema`).
- Class subclasses `pa.DataFrameModel`.
- `Index[<dtype>] = pa.Field(check_name=True)` for each index level (in MultiIndex declaration order).
- `Series[<dtype>] = pa.Field(ge=..., le=..., nullable=False/True, str_matches=...)` for columns.
- Inner `class Config: strict=True; coerce=False` (and `multiindex_strict=True; multiindex_coerce=False` for MultiIndex schemas).
- Lowercase column names (RESEARCH Pitfall 7 — yfinance PascalCase is normalized at the data/ layer before reaching schema).

### tenacity Retry Wrapper
**Source:** `src/screener/data/ohlcv.py` lines 54–60 (`@retry` decorator) and lines 44–48 (`_stdlib_log` for `before_sleep_log`)
**Apply to:** `data/macro.py` yfinance + FRED fetchers.
```python
_stdlib_log = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
```
Note: tenacity's `before_sleep_log` requires a stdlib logger, NOT structlog (per `data/ohlcv.py` line 45–48 comment).

### structlog Event Naming
**Source:** `src/screener/data/ohlcv.py` lines 10–13 (event name registry comment)
**Apply to:** All Phase 3 modules (data/macro.py, regime.py, persistence.py new writers).
- Event names are snake_case verbs: `<noun>_<verb>` — `fetch_start`, `fetch_success`, `fetch_fail`, `snapshot_written`, `breaker_tripped`.
- Phase 3 events: `macro_fetch_start`, `macro_fetch_success`, `macro_fetch_fail`, `nyad_source`, `skipping_yields_no_key`, `rs_snapshot_written`, `regime_computed`.
- Always pass kwargs (never f-strings): `log.info("fetch_success", ticker=t, source="yfinance", n_bars=n)` — JSON-friendly.
- Use `log.warning(...)` for fallback/recovery; `log.error(...)` for terminal failures; `log.info(...)` for success/state changes.

### Path-Resolver Helper Pattern
**Source:** `src/screener/persistence.py` lines 193–207 (`_ohlcv_dir`, `_universe_dir`)
**Apply to:** `_macro_dir()`, `_rs_snapshot_dir()` in `persistence.py`.
```python
def _macro_dir() -> Path:
    s: Any = get_settings()
    return Path(getattr(s, "MACRO_CACHE_DIR", "data/macro"))
```
The `getattr(s, "X", default)` pattern provides a hard-coded fallback for cross-wave Settings race safety (per existing line 196 comment "Wave-1 race against 02-02"). Once Settings has the field, getattr returns the pydantic default; the fallback is identical so behavior is stable.

### Additive Settings Extension (D-20 → D-12)
**Source:** `src/screener/config.py` lines 41–49 (Phase 2 D-20 extension)
**Apply to:** Phase 3 D-12 fields (8 new fields appended to the same `Settings` class).
- Append new fields under a comment block `# Phase N (D-XX) — <category>`.
- Always use typed defaults (`Path`, `str`, `int`, `float`).
- `get_settings()` lru_cache singleton (line 52) covers new fields automatically — no changes there.
- `.env.example` mirror gets a parallel comment block.

### Architecture-Test Compliance
**Source:** `tests/test_architecture.py` lines 30–44 (ALLOWED dict)
**Apply to:** All new Phase 3 source files.
| Layer | Allowed peer imports | Phase 3 use |
|-------|----------------------|-------------|
| `data` | `persistence`, `config`, `obs` | `data/macro.py` ✓ |
| `indicators` | `persistence`, `config`, `obs` | `indicators/*` ✓ (only `persistence` used) |
| `regime` | `data`, `indicators`, `persistence`, `config`, `obs` | `regime.py` ✓ |
| `persistence` | `config`, `obs` | unchanged |

`indicators/` MUST NOT import any I/O package (test line 164–196 forbidden_external set). `cli.py` is the composition root and is exempt from layer checks.

### Synthetic Test Fixture Pattern
**Source:** `tests/conftest.py` lines 42–58 (`synthetic_ohlcv_valid_df`)
**Apply to:** All Phase 3 new fixtures.
```python
@pytest.fixture(scope="session")
def synthetic_ohlcv_valid_df() -> pd.DataFrame:
    idx = pd.bdate_range(end=_REF_DATE, periods=252)
    return pd.DataFrame(
        {
            "Open": np.full(len(idx), 100.0),
            "High": np.full(len(idx), 101.0),
            ...
        },
        index=idx,
    )
```
- `scope="session"` — fixtures are session-cached and immutable (the test code constructs new derived frames per test).
- `_REF_DATE = pd.Timestamp("2026-04-30")` (line 21) — pinned for deterministic business-day arithmetic.
- Numpy `np.full` for constant series — deterministic, no random seed required.
- For randomized series, use `np.random.RandomState(seed)` not the global numpy RNG (RESEARCH §Validation Architecture).

### Mock-and-Patch Test Pattern
**Source:** `tests/test_data_ohlcv.py` lines 35–80, `tests/test_data_stooq.py` lines 23–43
**Apply to:** `tests/test_macro_refresh.py` (mock yf.download, mock pdr.DataReader, mock fredapi.Fred).
```python
from unittest import mock

with mock.patch("screener.data.<module>.<symbol>", return_value=<fixture>):
    df = function_under_test(...)

with mock.patch("screener.data.<module>.<symbol>", side_effect=<exception>):
    with pytest.raises(StaleOrEmptyError, match="<msg>"):
        function_under_test(...)
```
Always patch the symbol **at the import site**, not the source module — `screener.data.macro.yf.download` not `yfinance.download`.

---

## No Analog Found

| File | Role | Reason | Reference instead |
|------|------|--------|-------------------|
| `_safe_sma`, `_safe_atr`, `_safe_obv` wrappers in `indicators/trend.py`, `indicators/volatility.py`, `indicators/volume.py` | indicator math defensive wrapper | NEW idiom: pandas-ta-classic returns `None` (not NaN-Series) on short input. No Phase 1/2 analog because Phase 1/2 doesn't call pandas-ta. | RESEARCH Pattern 1 (lines 224–237), Pitfall 2 |
| `_compute_breadth_fallback()` in `data/macro.py` | data adapter (proxy computation) | NEW idiom: computes A/D line cross-sectionally from R1000 panel. Not a fetch — it's a transform on persisted data. | RESEARCH Pattern 6 (lines 335–355) |
| Synthetic golden-file SPY/VIX fixtures for 2008-Q4, 2020-Q1, 2022-H1 | test fixture | NEW: REG-04 golden-file requires deterministic price series crossing 200d SMA at known dates | RESEARCH §Validation Architecture "Golden-file fixture design" + Wave 0 conftest extensions |
| Property test using hypothesis (`tests/test_regime_score.py`) | property-based test | NEW: first hypothesis-based test in the project (pyproject pins hypothesis but no analog test exists yet) | RESEARCH §Phase Requirements → Test Map (REG-02 row uses `property` test type) |

---

## Metadata

**Pattern extraction date:** 2026-05-10
**Files scanned:** 14 source modules + 6 test files + 4 config/CI files = 24 files read
**Source-of-truth references:**
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/persistence.py` (332 lines) — schemas, atomic-write, validation policy
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/data/ohlcv.py` (288 lines) — yfinance + tenacity + 4-invariant gate + structured-log event names
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/data/stooq.py` (60 lines) — Stooq adapter with column normalization, StaleOrEmptyError contract
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/data/universe.py` (276 lines) — composition function pattern, tenacity HTTP wrapper
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/config.py` (61 lines) — additive Settings extension pattern
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/cli.py` (201 lines) — typer command body pattern, configure_logging convention
- `/Users/belwinjulian/Desktop/SwingTrading/src/screener/obs.py` (40 lines) — structlog configure
- `/Users/belwinjulian/Desktop/SwingTrading/tests/test_persistence.py` (193 lines) — synthetic + tmp_path + monkeypatch test pattern
- `/Users/belwinjulian/Desktop/SwingTrading/tests/test_architecture.py` (197 lines) — layer-import contract + pure-import contract
- `/Users/belwinjulian/Desktop/SwingTrading/tests/conftest.py` (259 lines) — additive synthetic-fixture pattern
- `/Users/belwinjulian/Desktop/SwingTrading/.github/workflows/ci.yml` (84 lines) — CI job pattern
- `/Users/belwinjulian/Desktop/SwingTrading/Makefile` (52 lines) — make target pattern
- `/Users/belwinjulian/Desktop/SwingTrading/.env.example` (37 lines) — phase-block mirror pattern
- `/Users/belwinjulian/Desktop/SwingTrading/.gitignore` (50 lines) — Phase 2 D-19 carve-out pattern
- `/Users/belwinjulian/Desktop/SwingTrading/pyproject.toml` (113 lines) — deps + mypy + pytest config

**Confidence:** HIGH — every cited line number verified by direct file read on 2026-05-10. Every pattern extracted is from production code (not from RESEARCH.md scaffolding), except the four "No Analog Found" entries which are explicitly NEW idioms documented in RESEARCH.md with verified-live primitives.
