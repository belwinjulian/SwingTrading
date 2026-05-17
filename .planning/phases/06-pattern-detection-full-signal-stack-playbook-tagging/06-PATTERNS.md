# Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging - Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 27 (5 NEW source modules, 11 NEW tests, 11 EXTEND existing)
**Analogs found:** 25 / 27 (2 files have no direct analog — see "No Analog Found" section)

---

## File Classification

### NEW source modules

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `src/screener/indicators/patterns.py` | indicator (pure) | transform (panel-in/panel-out) | `src/screener/indicators/trend.py` + `src/screener/indicators/volume.py` | exact (panel transform); helpers from `volume.py` (`dryup_ratio`) and `trend.py` (`high_52w`/`low_52w`) |
| `src/screener/signals/qullamaggie.py` | signal (pure) | transform (panel-in/panel-out) | `src/screener/signals/minervini.py` | exact (signal scoring pure function) |
| `src/screener/signals/canslim.py` | signal (pure) | transform + read pre-filtered fundamentals | `src/screener/signals/minervini.py` | role-match; fundamentals consumption is novel |
| `src/screener/data/fundamentals.py` | data adapter (network + write) | request-response → atomic Parquet | `src/screener/data/macro.py` (Finnhub date-range + per-ticker yfinance) and `src/screener/data/ohlcv.py` (yfinance throttle + tenacity) | exact (per-source adapter shape; reuses tenacity + four-invariant gate) |
| `src/screener/data/insider.py` | data adapter (network + write) | request-response → SQLite append-only | `src/screener/data/macro.py` (per-series refresh + write); SQLite idiom is new | partial (no existing sqlite3 usage in source layer) |

### NEW tests

| New Test | Role | Closest Analog | Match Quality |
|----------|------|----------------|---------------|
| `tests/test_patterns_golden.py` | golden-file regression | `tests/test_regime_golden.py` | exact |
| `tests/test_patterns_split.py` | pivot continuity across corporate action | `tests/test_regime_golden.py` (synthetic SPY fixture pattern) | role-match |
| `tests/test_qullamaggie.py` | pure-function signal scoring | `tests/test_signals_minervini.py` | exact |
| `tests/test_canslim.py` | pure-function signal scoring | `tests/test_signals_minervini.py` | exact |
| `tests/test_canslim_lag.py` | persistence read-time filter | `tests/test_persistence.py` (read path patterns) | role-match |
| `tests/test_fundamentals_io.py` | mocked data adapter | `tests/test_data_ohlcv.py` (yfinance mock pattern) | exact |
| `tests/test_insider_io.py` | mocked data adapter + SQLite | `tests/test_data_ohlcv.py` (mock); SQLite portion is new | partial |
| `tests/test_insider_cluster_buy.py` | SQL/Python rolling-window | none in repo | NEW (Pitfall 7 fallback) |
| `tests/test_composite_full.py` | composite scoring with all components live | `tests/test_signals_composite.py` | exact (extension of existing) |
| `tests/test_playbook_tagger.py` | playbook tagger tie-breaker matrix | `tests/test_signals_composite.py` | role-match |
| `tests/test_breakout_strength.py` | D-06 graded formula property | `tests/test_signals_composite.py::test_volume_component_d02_anchors` | exact |

### EXTEND existing files

| Existing File | Role | Action |
|---------------|------|--------|
| `src/screener/signals/composite.py` | signal (pure) | Reduce `PHASE_4_ZEROED` to `frozenset()`; add 3 component helpers + `tag_playbook()` + `Final` tie-breaker constants |
| `src/screener/persistence.py` | I/O contract | Add 3 schemas (Fundamentals, Insider, PatternAudit); extend `RankingSnapshotSchema` (+9 cols); add 4 writer/reader helpers |
| `src/screener/publishers/snapshot.py` | publisher | Thin pass-through — schema-extension changes are transparent (no code change required if extended schema lives in persistence) |
| `src/screener/publishers/report.py` | publisher | Replace Phase 4 `--(Phase 6)` placeholders (line 267–268); add "Currently Held / Leaders" section; D-19 per-pick block format |
| `src/screener/publishers/pipeline.py` | orchestrator | Add patterns → qullamaggie → canslim → tag_playbook to the DAG; pass extended cross-section to snapshot + report |
| `src/screener/cli.py` | composition root | Fill `refresh-fundamentals` body (lines 192–195); add `_ensure_edgar_identity()` startup hook; extend score/report to call new modules |
| `src/screener/config.py` | settings | Additive: `FUNDAMENTALS_CACHE_DIR`, `INSIDER_CACHE_PATH`, `PATTERN_AUDIT_DIR` (FINNHUB_API_KEY + EDGAR_IDENTITY already present) |
| `src/screener/data/__init__.py` | barrel | Add `fundamentals` and `insider` re-exports |
| `src/screener/catalysts/__init__.py` | reserve seam | May stay empty (data/ modules carry the load) — D-23 confirms |
| `tests/test_architecture.py` | architecture lock | Extend `ALLOWED` per D-23 (verify signals/ cannot import data/) |
| `tests/test_cli_smoke.py` | CLI surface lock | Add `test_edgar_identity_required`; D14_SUBCOMMANDS MUST NOT change |
| `Makefile` | task runner | Add `make fundamentals` target (D-09) |
| `.env.example` | docs | Document `FINNHUB_API_KEY` + `EDGAR_IDENTITY` as REQUIRED for Phase 6+ |
| `.gitignore` | repo policy | Add `data/pattern_audit/`, `data/insider/`, `data/fundamentals/` |
| `docs/strategy_v1_preregistration.md` | preregistration | Optional amendment line for CANSLIM L/M de-duplication (D-18) |
| `pyproject.toml` | deps | Verify (no add): scipy, finnhub-python, edgartools, pandera already declared |

---

## Pattern Assignments

### `src/screener/indicators/patterns.py` (NEW — indicator, pure transform)

**Analog 1 (panel transform shape):** `src/screener/indicators/trend.py`
**Analog 2 (groupby-level rolling):** `src/screener/indicators/volume.py`

**Module docstring + import pattern** (from `trend.py` lines 1–15):
```python
"""patterns — VCP, continuation flag, post-gap-continuation pattern detection.

Pure-function discipline (Phase 1 D-16): NO I/O, NO global state. Imports only
pandas, scipy.signal, numpy, pandas_ta_classic (third-party math), and stdlib.

VCP thresholds locked as `Final` module-level constants per CONTEXT.md D-03 —
not Settings fields, not env-overridable. Tuned via golden-file tests
(test_patterns_golden.py), never against backtest results (Critical Pitfall #2).
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
```

**`Final`-constant locking pattern** (from `signals/composite.py` lines 14, 22–36):
```python
# Source: src/screener/signals/composite.py (DEFAULT_WEIGHTS + PHASE_4_ZEROED proven pattern)
# Phase 6 D-03 verbatim — VCP detection thresholds (CLAUDE.md §"Signal Formulas")
PRIOR_UPTREND_MIN_PCT: Final[float] = 0.30
N_CONTRACTIONS_MIN: Final[int] = 2
N_CONTRACTIONS_MAX: Final[int] = 6
DEPTH_CONTRACTION_MAX_RATIO: Final[float] = 0.85
FIRST_LEG_MAX_DEPTH_PCT: Final[float] = 0.35
FINAL_CONTRACTION_MAX_DEPTH_PCT: Final[float] = 0.12
BREAKOUT_VOLUME_MIN_MULTIPLE: Final[float] = 1.5
SMA_VOLUME_BASELINE_DAYS: Final[int] = 50
PIVOT_ORDER: Final[int] = 5  # argrelextrema window; tune via 4 golden files
```

**Per-ticker rolling pattern to copy** (from `indicators/volume.py` lines 42–52):
```python
def dryup_ratio_panel(panel: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """D-09: dryup_ratio = volume / SMA(volume, length)."""
    out = panel.copy()
    sma_vol = (
        panel.groupby(level="ticker")["volume"]
        .rolling(length)
        .mean()
        .droplevel(0)
    )
    out["dryup_ratio"] = panel["volume"] / sma_vol
    return out
```

**Per-ticker `_safe_*` wrapper + concat pattern** (from `indicators/volatility.py` lines 22–37) — pivot detection per-ticker:
```python
def atr_panel(panel: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Append atr_<length> column. Per-ticker rolling (Pitfall 8).

    Uses explicit per-ticker concat instead of groupby.apply to avoid
    pandas returning a wide (ticker x date) DataFrame when the apply
    function returns a Series with the date as index.
    """
    out = panel.copy()
    parts: list[pd.Series] = []
    for _ticker, g in panel.groupby(level="ticker"):
        s = _safe_atr(g["high"], g["low"], g["close"], length)
        parts.append(s)
    combined = pd.concat(parts)
    combined.name = f"atr_{length}"
    out[f"atr_{length}"] = combined
    return out
```

**What to copy / adapt / add new:**
- COPY: module-docstring shape, `from __future__ import annotations`, `Final[...]` constant locking idiom, the per-ticker concat pattern (Pitfall 8 — no naked `.shift()` on MultiIndex)
- ADAPT: replace `ta.atr` with `argrelextrema(highs, np.greater_equal, order=PIVOT_ORDER)` for pivot detection (Research §Code Examples §2; Pitfall 2 — `order` truncates near edges)
- ADD NEW: `find_vcp_pattern(panel) -> dict`, `find_flag_pattern(panel) -> dict`, `post_gap_continuation(panel) -> Series[bool]` (D-04: `close >= low + (2/3)*(high-low)` AND `gap_pct >= 0.08` AND `vol > 1.5 * sma_vol_50`), `breakout_strength(vol, sma_vol_50) -> Series[float]` (D-06 formula with Pitfall 10 NaN→0 guard), `vcp_passes` / `flag_passes` / `pivot_price` / `pattern_diagnostics` columns appended to panel

---

### `src/screener/signals/qullamaggie.py` (NEW — signal, pure transform)

**Analog:** `src/screener/signals/minervini.py`

**Module docstring + import pattern** (from `signals/minervini.py` lines 1–22):
```python
"""minervini — Trend Template gate (8 SMA-based conditions; pass/fail + 0-8 score).

Pure-function discipline (Phase 1 D-16 architecture lock): no I/O, no global
state, panel-in / panel-out. Imports only pandas + stdlib.

Pitfalls handled:
- Per-ticker shift via groupby(level='ticker').shift(22) for cond 3
- Nullable Int64 NaN propagation: rs_rating >= 70 returns pd.NA on NaN
- Tickers with insufficient history get NaN -> False -> score 0
"""

from __future__ import annotations

import pandas as pd
```

**Multi-condition AND-gate pattern** (from `signals/minervini.py` lines 25–90):
```python
def passes_trend_template(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `passes_trend_template` (bool) and `trend_template_score` (Int64 0-8)."""
    out = panel.copy()

    close = panel["close"]
    sma_50 = panel["sma_50"]
    # ... pull all required columns from panel ...
    rs_rating = panel["rs_rating"]

    cond1 = (close > sma_150) & (close > sma_200)
    # ... cond2..cond8 ...

    # NaN-safe boolean coercion (Pitfall 3): pd.NA in `&` raises ambiguous;
    # any NaN input must propagate to False (ticker fails the condition).
    conds = [cond1, cond2, cond3, cond4, cond5, cond6, cond7, cond8]
    bool_conds: list[pd.Series] = [c.fillna(False).astype(bool) for c in conds]

    score: pd.Series = pd.concat(
        [bc.astype("Int64") for bc in bool_conds], axis=1
    ).sum(axis=1).astype("Int64")

    out["trend_template_score"] = score
    out["passes_trend_template"] = (score == 8).fillna(False).astype(bool)
    return out
```

**What to copy / adapt / add new:**
- COPY VERBATIM: docstring structure, pure-function contract, NaN-safe `fillna(False).astype(bool)` pattern before booleans are AND-ed
- ADAPT: replace the 8 trend-template conditions with the Qullamaggie Setup A 3-condition AND-gate (SIG-02): `(rs_rating >= top-1-2% threshold) AND (avg_dollar_volume_50d > 1.5e6) AND (adr_pct >= 4)`. All three columns already present in panel (`rs_rating` from `indicators/relative_strength.py`, `adr_pct` from `indicators/volatility.py`; `avg_dollar_volume` = `(close * volume).rolling(50).mean()` per-ticker — add as a helper)
- ADD NEW: emit single column `qullamaggie_score` (0/1) — D-12 says binary in v1; output column matches the playbook tagger's expected input

---

### `src/screener/signals/canslim.py` (NEW — signal, pure transform; consumes pre-filtered fundamentals)

**Analog:** `src/screener/signals/minervini.py` (signal contract); `src/screener/persistence.py::read_panel` consumption pattern from `src/screener/indicators/__init__.py::build_panel`

**Pre-filtered data consumption pattern** (from `indicators/__init__.py` lines 22–39):
```python
def build_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Returns the OHLCV panel + 13 indicator columns. Pure function — reads
    from persistence.read_panel(); emits no I/O.
    """
    panel = read_panel(snapshot_date)  # MultiIndex (ticker, date), validated lazily
    panel = sma_panel(panel, lengths=(10, 20, 50, 150, 200))
    # ... more pure transforms ...
    return panel
```

**What to copy / adapt / add new:**
- COPY: pure-function contract; signal takes panel (and pre-filtered fundamentals frame) → returns panel with new columns
- ADAPT: signals/ cannot import data/ per D-23, so `canslim.py` accepts the fundamentals frame as an argument — the CALLER (publishers/pipeline.py) calls `persistence.read_fundamentals(as_of_date)` and passes the result in. This preserves D-13b structural enforcement.
- ADD NEW: function signature `canslim_c_overlay(panel: pd.DataFrame, fundamentals: pd.DataFrame, as_of_date: pd.Timestamp) -> pd.DataFrame`. Returns panel with `canslim_c_passes: bool` column. D-18 dedup: only the C component is scored here (L is `rs_rating >= 80` already in `rs_component`; M is `regime_state == "Confirmed Uptrend"` already in the regime soft gate). Missing fundamentals → `False` (D-13b honest-failure).

---

### `src/screener/data/fundamentals.py` (NEW — data adapter; Finnhub + yfinance)

**Analog 1 (yfinance per-ticker + throttle + tenacity):** `src/screener/data/ohlcv.py` lines 54–104
**Analog 2 (date-range bulk fetch + structured logging + write):** `src/screener/data/macro.py` lines 63–96, 156–187

**Module docstring + tenacity-wrapped yfinance pattern** (from `data/ohlcv.py` lines 1–13, 54–104):
```python
"""OHLCV — yfinance fetcher + tenacity wrapper + post-fetch invariants
(D-08) + sentinel-bar refetch (D-07) + circuit-breaker orchestration (D-12)
+ splits ledger (D-18).

Layered-DAG contract: imports only stdlib, third-party, screener.persistence,
screener.config, and (intra-layer) screener.data.stooq.
"""

import logging
import random
import time
# ...
log = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)  # tenacity needs stdlib logger

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((StaleOrEmptyError, ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)
def fetch_ohlcv(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    df = yf.download(ticker, start=str(start), auto_adjust=True, ...)
    if df is None or len(df) == 0:
        raise StaleOrEmptyError(f"yf returned empty for {ticker}")
    # ... four-invariant gate (D-08) ...
    return df
```

**Per-ticker pacing pattern** (from `data/ohlcv.py` lines 110–120):
```python
def fetch_ohlcv_with_pacing(ticker: str, start: str | date, today: date) -> pd.DataFrame:
    """Wraps fetch_ohlcv with the inter-ticker random sleep (D-10)."""
    settings = get_settings()
    df = fetch_ohlcv(ticker, start, today)
    time.sleep(random.uniform(settings.OHLCV_FETCH_SLEEP_MIN_S, settings.OHLCV_FETCH_SLEEP_MAX_S))
    return df
```

**Incremental refresh + atomic write pattern** (from `data/macro.py` lines 156–187):
```python
def refresh_spy(force: bool, today: date) -> Path:
    from screener import persistence

    settings = get_settings()
    existing = persistence.read_macro_spy() if not force else None
    start = (settings.MACRO_BACKFILL_START
             if (existing is None or existing.empty)
             else _incremental_start(existing, settings.MACRO_BACKFILL_START))
    if start is None:
        log.info("macro_refresh_skip_up_to_date", series="spy", ...)
        return _macro_dir_for_log() / "spy.parquet"
    log.info("macro_fetch_start", series="spy", source="yfinance", start=start)
    new_bars = _fetch_yf_macro("SPY", start, today)
    combined = _append_new_bars(existing, new_bars)
    return write_macro_atomic(combined, "spy")
```

**What to copy / adapt / add new:**
- COPY: docstring layered-DAG contract preamble; structlog + stdlib-logger dual setup (tenacity requires stdlib); `@retry` decorator with `StaleOrEmptyError` retry target; `random.uniform(0.5, 1.5)` pacing inside the success branch (Pitfall 4 — Finnhub 60/min ceiling)
- ADAPT: replace `yf.download(...)` with `finnhub_client.earnings_calendar(_from=..., to=..., symbol=None)` (date-range query, NOT per-ticker — Pitfall 4 mitigation); use `requests_cache` 24h backend per `docs/data-architecture.md` §7. For EPS history: `yf.Ticker(t).quarterly_income_stmt` (Pitfall 5 — `.quarterly_earnings` is deprecated), extract "Diluted EPS" row
- ADD NEW: `knowable_from = fiscal_quarter_end + pd.Timedelta(days=45)` column on every row written (D-13b); structured-log event names follow `macro.py` convention: `fundamentals_fetch_start`, `fundamentals_fetch_success`, `fundamentals_fetch_fail`. Write via new `persistence.write_fundamentals_atomic(df, ticker)`.

---

### `src/screener/data/insider.py` (NEW — data adapter; edgartools Form 4 → SQLite append-only)

**Analog 1 (per-source adapter shape):** `src/screener/data/macro.py` (refresh_* functions)
**Analog 2 (atomic write + structured logging):** `src/screener/data/ohlcv.py`

**Module docstring shape** (from `data/macro.py` lines 1–22):
```python
"""macro — Phase 3 macro data layer (DAT-04).

Fetches 5 macro series and writes each to data/macro/<series>.parquet:
...

Layered-DAG contract (Phase 1 D-16 / tests/test_architecture.py): imports only
stdlib, third-party (yfinance, fredapi, ...), screener.persistence,
screener.config, and intra-layer screener.data.stooq.

Structured-log event names:
- macro_fetch_start: {series, source}
- macro_fetch_success: {series, source, n_bars}
- macro_fetch_fail: {series, source, error_type, attempt}
"""
```

**SQLite append-only pattern (NEW — no source-layer precedent in repo; one in-source reference is `data/universe.py` line 102 for requests-cache backend):**

The closest existing-codebase shape is `persistence._write_parquet_atomic` (atomic POSIX rename). For SQLite, the canonical idiom per Research §Common Pitfalls #7 and CONTEXT.md D-10 is:
```python
import sqlite3

def _ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS form4 (
                filing_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                insider TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                type TEXT NOT NULL,
                shares REAL NOT NULL,
                value_usd REAL NOT NULL,
                ingested_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_form4_ticker_date ON form4(ticker, transaction_date)")

def append_form4_rows(db_path: Path, rows: list[dict]) -> int:
    """Idempotent append — ON CONFLICT(filing_id) DO NOTHING per D-10."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.executemany(
            """INSERT INTO form4(filing_id, ticker, insider, transaction_date,
                                  type, shares, value_usd, ingested_at)
               VALUES (:filing_id, :ticker, :insider, :transaction_date,
                       :type, :shares, :value_usd, :ingested_at)
               ON CONFLICT(filing_id) DO NOTHING""",
            rows,
        )
        return cur.rowcount
```

**What to copy / adapt / add new:**
- COPY: docstring layered-DAG contract preamble; `log = structlog.get_logger(__name__)`; tenacity retry decorator (though edgartools auto-enforces 10 req/sec, ConnectionError/TimeoutError retry is still prudent)
- ADAPT: replace `yf.download` with `edgar.get_filings(form="4", filing_date="-35d:")` then `.obj().get_transaction_activities()` (Research §"Don't Hand-Roll" — never parse Form 4 XBRL by hand)
- ADD NEW: SQLite schema setup + idempotent append (above); pandera `InsiderSchema` validates the DataFrame view BEFORE the SQLite insert (eager validation per D-16)

---

### `src/screener/signals/composite.py` (EXTEND)

**Current state:** lines 22–36 carry `DEFAULT_WEIGHTS` (Final dict) + `PHASE_4_ZEROED` (Final frozenset). Lines 92–115 are the scoring loop.

**`Final`-constant locking pattern to extend** (current file, lines 14, 22–36 — these stay, but `PHASE_4_ZEROED` shrinks):
```python
from typing import Final

DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "rs": 0.25,
    "trend": 0.20,
    "pattern": 0.20,    # zeroed in Phase 4 (D-01); active in Phase 6
    "volume": 0.10,
    "earnings": 0.15,   # zeroed in Phase 4 (D-01); active in Phase 6
    "catalyst": 0.10,   # zeroed in Phase 4 (D-01); active in Phase 6
}

# Phase 6 D-16: empty frozenset — all components are now live.
PHASE_4_ZEROED: Final[frozenset[str]] = frozenset()
```

**Scoring-loop sanctity (Pitfall 6)** — current file, lines 90–115. **DO NOT TOUCH this loop:**
```python
out = panel.copy()
out["rs_component"] = (panel["rs_rating"].astype("Float64") / 99.0).fillna(0.0)
out["trend_component"] = (panel["trend_template_score"].astype("Float64") / 8.0).fillna(0.0)
out["volume_component"] = ((1.0 - (panel["dryup_ratio"] - 0.5) / 1.5).clip(0.0, 1.0).fillna(0.0))
# Phase 4 placeholders REPLACED in Phase 6 — but the LOOP below is untouched:
out["pattern_component"] = score_pattern_component(panel)      # NEW helper call
out["earnings_component"] = score_earnings_component(panel)    # NEW helper call
out["catalyst_component"] = score_catalyst_component(panel)    # NEW helper call

composite = pd.Series(0.0, index=panel.index)
for key, w in weights.items():
    composite = composite + w * out[f"{key}_component"]
out["composite_score"] = (composite * 100.0).astype(float)
```

**`tag_playbook` tie-breaker pattern — Final constants per D-13 (NEW, no exact analog; closest is composite's DEFAULT_WEIGHTS):**
```python
# Phase 6 D-13 — tie-breaker thresholds (Final, not Settings-overridable)
QULL_MAX_BARS: Final[int] = 25
QULL_MIN_ADR_PCT: Final[float] = 5.0
MINERVINI_MIN_BARS: Final[int] = 25
MINERVINI_MAX_FINAL_CONTRACTION_PCT: Final[float] = 8.0
LEADER_MIN_RS: Final[int] = 90


def tag_playbook(panel: pd.DataFrame) -> pd.DataFrame:
    """Co-located playbook tagger (CMP-04). Pure: panel-in, panel-out.

    Emits four new columns: playbook_tag (str), qullamaggie_score (Int 0/1),
    minervini_score (Int 0/1), leader_hold_score (Int 0/1).

    D-14 tie-break: Qullamaggie wins over Minervini when both fire.
    D-15: playbook_tag == "none" picks are dropped from the report.
    """
    out = panel.copy()
    # ... extract pattern_diagnostics, adr_pct, rs_rating, passes_trend_template ...
    # D-14 cascade: q wins > m wins > leader_hold > none
```

**What to copy / adapt / add new:**
- COPY VERBATIM: `Final[...]` annotation, the scoring-loop body lines 112–115 (Pitfall 6: this loop is sacred — adding components is ABOVE the loop, never inside)
- ADAPT: change `PHASE_4_ZEROED` from `frozenset({"pattern","earnings","catalyst"})` to `frozenset()` — this single line change activates the loop pickup of the three new components (D-16)
- ADD NEW: three component helpers (`score_pattern_component`, `score_earnings_component`, `score_catalyst_component`) above the scoring loop; `tag_playbook(panel)` function co-located per CMP-04; five `Final` tie-breaker constants per D-13; JSON `encode_pattern_diagnostics` / `decode_pattern_diagnostics` helpers (Pitfall 8 — JSON validation lives in custom `@pa.check`, encode/decode lives here)

---

### `src/screener/persistence.py` (EXTEND — add 3 schemas, extend 1, add 4 helpers)

**Current state:** Atomic-write helper `_write_parquet_atomic` at lines 273–295. Eight pandera schemas. Eight writers/readers. `RankingSnapshotSchema` at lines 221–254.

**Pandera schema pattern to copy** (from `persistence.py::RankingSnapshotSchema` lines 221–254):
```python
class RankingSnapshotSchema(pa.DataFrameModel):
    """Daily ranking snapshot — full universe with composite scores and ranks.

    Written by publishers/snapshot.py via persistence.write_snapshot_atomic.
    Used by Phase 5 backtest harness for no-look-ahead reproduction.
    Schema enforced eagerly at the write boundary (D-16 validation policy).
    """

    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rank: Series[pd.Int64Dtype] = pa.Field(ge=1, nullable=True)
    composite_score: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=True)
    # ... 13 more component / pivot / regime columns ...
    regime_score: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)

    class Config:
        strict = True
        coerce = False
```

**Atomic-write helper pattern to reuse** (from `persistence.py` lines 273–295):
```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    """Write `df` to `target` atomically (POSIX same-filesystem rename)."""
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

**Eager-validate-then-write pattern to copy** (from `persistence.py` lines 422–438):
```python
def write_snapshot_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write a ranking snapshot to data/snapshots/<date>.parquet."""
    _assert_safe_snapshot_date(snapshot_date)
    validated = validate_at_write(RankingSnapshotSchema, df)
    target = _snapshot_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("snapshot_written", path=str(target), n_rows=len(validated), snapshot_date=snapshot_date)
    return target
```

**Settings-with-fallback helper pattern** (from `persistence.py` lines 324–356):
```python
def _snapshot_dir() -> Path:
    """Resolve the daily ranking-snapshot directory, with cross-wave fallback."""
    s: Any = get_settings()
    return Path(getattr(s, "SNAPSHOT_DIR", "data/snapshots"))
```

**What to copy / adapt / add new:**
- COPY VERBATIM: `_write_parquet_atomic` (no changes); `validate_at_write` / `validate_at_read` policy (D-16); the `_X_dir()` helpers with `getattr` fallback idiom
- ADAPT: extend `RankingSnapshotSchema` with the 9 new columns per D-19 (`playbook_tag: Series[str] = pa.Field(isin=["qullamaggie_continuation","minervini_vcp","leader_hold","none"])`, `qullamaggie_score: Series[pd.Int64Dtype]`, `minervini_score: Series[pd.Int64Dtype]`, `leader_hold_score: Series[pd.Int64Dtype]`, `pattern_diagnostics: Series[str]` with custom `@pa.check` for JSON validity (Pitfall 8), `breakout_strength: Series[float]`, `days_to_next_earnings: Series[pd.Int64Dtype]`, `crossed_52w_high_within_60d: Series[bool]`, `insider_cluster_buy: Series[bool]`, `earnings_in_3d_warn: Series[bool]`)
- ADD NEW: `FundamentalsSchema`, `InsiderSchema`, `PatternAuditSchema` (Research §Pattern 4 has the FundamentalsSchema spec verbatim); `write_fundamentals_atomic(df, ticker)`, `write_pattern_audit_atomic(df, snapshot_date)`, `read_fundamentals(as_of_date)` (filters `knowable_from <= as_of_date` per D-13b — this is the structural defense of the 45-day lag), `read_insider_cluster_buy(window_days=30, cluster_size=2, dt=5)` (SQL with Python rolling-window fallback per Research Pitfall 7)

---

### `src/screener/publishers/report.py` (EXTEND — D-19 format + leader-hold section)

**Current `_format_breakdown` placeholder pattern** (lines 99–123):
```python
def _format_breakdown(row: pd.Series) -> str:
    """D-04 per-pick breakdown line -- iterates DEFAULT_WEIGHTS keys,
    renders PHASE_4_ZEROED entries as '--(Phase 6)' placeholders."""
    parts: list[str] = []
    for key in DEFAULT_WEIGHTS:
        label = key.capitalize()
        if key in PHASE_4_ZEROED:
            parts.append(f"{label}=--(Phase 6)")
        elif key == "rs":
            rs_val = row.get("rs_rating")
            rs_str = "?" if pd.isna(rs_val) else str(int(rs_val))
            parts.append(f"RS={rs_str}")
        # ... trend, volume branches ...
    return " | ".join(parts)
```

**Current per-pick rendering with placeholders** (lines 251–269):
```python
for i, (_, row) in enumerate(top.iterrows(), start=1):
    ticker = str(row["ticker"])
    composite = float(row["composite_score"])
    lines.append(f"### {i}. {ticker} -- Composite {composite:.1f}")
    lines.append("")
    lines.append("```")
    lines.append(_format_breakdown(row))
    lines.append("```")
    # ...
    lines.append("- **Playbook:** --(Phase 6)")        # REPLACE in Phase 6
    lines.append("- **Catalysts:** --(Phase 6)")        # REPLACE in Phase 6
```

**What to copy / adapt / add new:**
- COPY: `_write_text_atomic` (lines 126–169) — no changes; the iteration-over-DEFAULT_WEIGHTS pattern in `_format_breakdown`; the no-emoji ASCII-only convention (line 14 docstring + Pitfall 12)
- ADAPT: extend `_format_breakdown` to render the three previously-placeholder components per D-19 format: `Pattern=0.67 (VCP, 4 contractions, brk_vol=2.1x)`, `Earnings=1 (EPS YoY 32%)`, `Catalyst=0.67 (2/3 flags)` — pulls from `pattern_diagnostics` JSON column + new component score columns. The PHASE_4_ZEROED branch will hit zero keys (since PHASE_4_ZEROED is now empty) — placeholders auto-disappear.
- ADD NEW: `## Currently Held / Leaders` section AFTER the top-N table — filter `scored_cross[playbook_tag == "leader_hold"]`, ranked by composite_score, all rendered (not top-N capped, per D-15); also filter the existing top-N to `playbook_tag in {"qullamaggie_continuation","minervini_vcp"}` (Pitfall 9: two-pass selection — prevents leader_hold picks from polluting top-N). Add `WARNING: Earnings in 2d` annotation per pick where `earnings_in_3d_warn=True` (D-11a; same ASCII WARNING convention as line 280).

---

### `src/screener/publishers/pipeline.py` (EXTEND — add patterns/qullamaggie/canslim/tag_playbook to DAG)

**Current `run_pipeline` DAG** (lines 116–193) — Phase 6 inserts new steps:
```python
def run_pipeline(snapshot_date: str, write_report: bool = True) -> None:
    settings = get_settings()
    panel = build_panel(snapshot_date)                                # step 1
    panel = passes_trend_template(panel)                              # step 2
    # Phase 6 inserts HERE:
    #   panel = patterns.detect_all_patterns(panel)                   # NEW
    #   panel = qullamaggie.qullamaggie_setup_a(panel)                # NEW
    #   fundamentals = persistence.read_fundamentals(snap_ts)         # NEW
    #   panel = canslim.canslim_c_overlay(panel, fundamentals, snap_ts)  # NEW
    panel = score(panel, DEFAULT_WEIGHTS)                             # step 3 (extended automatically)
    # Phase 6 inserts HERE:
    #   panel = composite.tag_playbook(panel)                         # NEW
    snap_ts = pd.Timestamp(snapshot_date)
    today_panel = panel.xs(snap_ts, level="date")                     # step 4
    # ... regime gate (5), validate_run (6), publisher cols (7) ...
    write_snapshot(today_panel, snapshot_date)                        # step 8 (extended schema)
    if write_report:
        write_report_md(today_panel, regime_row, snapshot_date, ...)  # step 9 (extended format)
    # Phase 6 adds:
    #   persistence.write_pattern_audit_atomic(pattern_audit_df, snapshot_date)  # NEW
```

**What to copy / adapt / add new:**
- COPY: the late-import idiom (lines 164, 169, 175) to avoid circular imports; the validate-before-write sequencing (Pitfall 7)
- ADD NEW: insert 4 new pure-function calls between `passes_trend_template` and `score`; one new `tag_playbook` call after `score`; one new `write_pattern_audit_atomic` after `write_snapshot`. CALLER (pipeline.py) bridges data/ → signals/ per D-13b: it calls `persistence.read_fundamentals(snap_ts)` and passes the result into `canslim.canslim_c_overlay(...)` — signals/canslim.py never imports data/.

---

### `src/screener/cli.py` (EXTEND — fill refresh-fundamentals body, add EDGAR identity startup hook)

**Current stub** (lines 192–195):
```python
@app.command("refresh-fundamentals")
def refresh_fundamentals() -> None:
    """Refresh fundamentals (Finnhub earnings + EPS); 45-day post-quarter-end lag enforced."""
    _stub("refresh-fundamentals")
```

**Current real-body pattern to mirror** (`cli.py::refresh_macro` lines 158–189):
```python
@app.command("refresh-macro")
def refresh_macro(
    force: Annotated[bool, typer.Option("--force", ...)] = False,
) -> None:
    """Refresh macro inputs (SPY, QQQ, ^VIX, NYSE A/D, FRED yields). DAT-04."""
    configure_logging()
    today = date.today()
    try:
        from screener.data.macro import (refresh_nyad, refresh_qqq, refresh_spy, refresh_vix, refresh_yields)
        refresh_spy(force=force, today=today)
        refresh_qqq(force=force, today=today)
        refresh_vix(force=force, today=today)
        refresh_nyad(force=force, today=today)
        refresh_yields(force=force, today=today)
        log.info("refresh_macro_ok")
    except Exception as e:
        log.error("refresh_macro_failed", error_type=type(e).__name__)
        raise typer.Exit(code=1) from e
```

**EDGAR identity startup hook (NEW)** — Research §Code Examples §1:
```python
def _ensure_edgar_identity() -> None:
    """Fail loud at startup if EDGAR_IDENTITY env var is unset. (CAT-04 + Pitfall 3)"""
    from edgar import set_identity
    identity = get_settings().EDGAR_IDENTITY
    if not identity:
        raise SystemExit(
            "EDGAR_IDENTITY env var is unset. SEC requires 'Name <email>' "
            "for User-Agent. See .env.example."
        )
    set_identity(identity)  # idempotent; safe to call repeatedly
```

**What to copy / adapt / add new:**
- COPY: `refresh_macro` body shape — `configure_logging()` first, try/except with `log.error(..., error_type=type(e).__name__)` (NEVER `error=str(e)` — Pitfall T-3-02 — exception messages may contain API keys)
- ADAPT: 3-step orchestration body for `refresh-fundamentals` — Finnhub `/calendar/earnings` → yfinance EPS per-ticker → EDGAR Form 4 bulk. Add `--skip-insider` / `--insider-only` typer options per D-09.
- ADD NEW: `_ensure_edgar_identity()` called inside any subcommand that needs EDGAR (refresh-fundamentals, score, report) BEFORE any work; D24 — DO NOT add a 10th subcommand. T-3-02 carry-forward: every new `except` block logs `error_type` only.

---

### `src/screener/config.py` (EXTEND — 3 new path fields)

**Current additive-extension pattern** (lines 41–70):
```python
# Phase 2 (D-20) — data-layer paths and policy
OHLCV_CACHE_DIR: Path = Path("data/ohlcv")
UNIVERSE_CACHE_DIR: Path = Path("data/universe")
# ...

# Phase 3 (D-12) — macro + RS snapshot paths and regime thresholds
MACRO_CACHE_DIR: Path = Path("data/macro")
RS_SNAPSHOT_DIR: Path = Path("data/rs_snapshots")
# ...

# Phase 4 (D-07/D-08, CONTEXT.md "Claude's Discretion") — report config
SNAPSHOT_DIR: Path = Path("data/snapshots")
REPORT_DIR: Path = Path("reports")
REPORT_TOP_N: int = 15
```

**What to copy / adapt / add new:**
- COPY: the `# Phase N (D-XX) — …` comment block pattern; typed Path fields with defaults; pydantic-settings additive style (no field removal — backwards-compatible)
- ADD NEW:
```python
# Phase 6 — fundamentals + insider + pattern audit paths
FUNDAMENTALS_CACHE_DIR: Path = Path("data/fundamentals")
INSIDER_CACHE_PATH: Path = Path("data/insider/form4.sqlite")
PATTERN_AUDIT_DIR: Path = Path("data/pattern_audit")
```
- Mirror to `.env.example` (Research Runtime State Inventory). FINNHUB_API_KEY + EDGAR_IDENTITY are already declared (lines 29, 31) — just promote `.env.example` comments to "REQUIRED for Phase 6+".

---

### `tests/test_architecture.py` (EXTEND — D-23 ALLOWED dict extension)

**Current ALLOWED dict** (lines 30–44):
```python
ALLOWED: dict[str, set[str]] = {
    "data": {"persistence", "config", "obs"},
    "indicators": {"persistence", "config", "obs"},
    "signals": {"indicators", "regime", "persistence", "config", "obs"},
    "regime": {"data", "indicators", "persistence", "config", "obs"},
    # ...
    "catalysts": {"persistence", "config", "obs"},
    "ml": {"persistence", "config", "obs"},
    "persistence": {"config", "obs"},
    "config": set(),
    "obs": set(),
}
```

**Forbidden-external-imports test** (lines 164–197) — already enforces signals/ + indicators/ cannot import `requests`/`yfinance`/`finnhub`/`edgar`/`sqlite3` etc. **Phase 6 NEW modules MUST pass this test as-written:**
```python
def test_indicators_signals_pure_no_io_imports(src_screener: Path) -> None:
    """indicators/ and signals/ MUST NOT import requests/yfinance/finnhub/edgartools/sqlite3/etc."""
    forbidden_external = {
        "requests", "yfinance", "finnhub", "edgar", "edgartools",
        "fredapi", "sqlite3", "urllib", "urllib3", "httpx", "requests_cache",
    }
```

**What to copy / adapt / add new:**
- COPY: ALLOWED dict structure; the AST-based scanner stays unchanged
- ADAPT: NO change to ALLOWED keys/sets — D-23 says the new modules (`data/fundamentals`, `data/insider`, `indicators/patterns`, `signals/qullamaggie`, `signals/canslim`) inherit their layer's existing entry. Verify: `signals/qullamaggie.py` and `signals/canslim.py` and `indicators/patterns.py` MUST NOT contain `from screener.data.fundamentals import ...` or any data/ import (structural defense of D-13b).
- ADD NEW: a single explicit regression test `test_signals_canslim_does_not_import_data_layer()` if Phase 6 wants extra belt-and-suspenders (optional — the existing `test_layer_import_contract` already covers it). Verify `finnhub` and `sqlite3` are in `forbidden_external` (line 168, 172) — they ARE.

---

### `tests/test_cli_smoke.py` (EXTEND — preserve D14, add EDGAR identity test)

**D14_SUBCOMMANDS lock** (lines 20–30) — Phase 6 MUST NOT change:
```python
D14_SUBCOMMANDS = [
    "refresh-universe",
    "refresh-ohlcv",
    "refresh-macro",
    "refresh-fundamentals",
    "score",
    "report",
    "journal",
    "backtest",
    "backtest-audit",
]
```

**PHASE_1_STUBS shrinks** (lines 38–41) — Phase 6 removes `"refresh-fundamentals"`:
```python
PHASE_1_STUBS = [
    "refresh-fundamentals",   # REMOVE in Phase 6 (real body lands)
    "journal",
]
```

**What to copy / adapt / add new:**
- COPY: D14_SUBCOMMANDS list — must remain identical (D-24 hard lock)
- ADAPT: remove `"refresh-fundamentals"` from PHASE_1_STUBS; add a `test_refresh_fundamentals_subcommand_no_longer_stub` (mirrors `test_score_subcommand_no_longer_stub` at lines 232–242)
- ADD NEW: `test_edgar_identity_required` — monkeypatch `EDGAR_IDENTITY=""` in env, invoke `refresh-fundamentals`, assert exit non-zero AND error message references `EDGAR_IDENTITY` AND `.env.example` (per Research §Code Examples §1)

---

### `tests/test_patterns_golden.py` (NEW — 4 golden-file regression)

**Analog:** `tests/test_regime_golden.py` (synthetic-data-with-deterministic-injection pattern, lines 23–106)

**Synthetic-fixture pattern to follow** (from `test_regime_golden.py` lines 23–64):
```python
def _make_synthetic_spy_for_correction(
    start: str,
    end: str,
    sma_break_dates: list[str],
) -> pd.DataFrame:
    """Build a synthetic SPY OHLCV series whose close crosses below 200d SMA
    at known dates and has injected distribution days. Deterministic — used
    by REG-04 golden-file tests."""
    pad_start = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    idx = pd.bdate_range(start=pad_start, end=end)
    close = np.full(len(idx), 100.0)
    # ... deterministic price shape injection ...
    return pd.DataFrame({"open": close, "high": close * 1.005, ...}, index=...)
```

**Pytest fixture pattern** (lines 89–110):
```python
@pytest.fixture(scope="session")
def synthetic_spy_2008q4() -> pd.DataFrame:
    return _make_synthetic_spy_for_correction(
        start="2008-10-01",
        end="2009-03-01",
        sma_break_dates=["2008-10-06"],
    )
```

**What to copy / adapt / add new:**
- COPY: session-scoped fixtures, deterministic synthetic data construction (`pd.bdate_range`, `np.full`, in-place injection), `pad_start` warmup to defeat SMA NaN warmup
- ADAPT: construct each of the 4 D-02 golden series (NVDA 2023 base, AAPL 2020, NVDA 2024 split-adjusted, NVDA 2023-05-25..2023-06-12 flag). Real OHLCV fetched once via yfinance and cached as Parquet under `tests/fixtures/` — NOT synthetic — because the golden gate is "did our detector recognize the real historical pattern?"
- ADD NEW: 4 tests, each asserting `vcp_passes` / `flag_passes` is True on the breakout date for that fixture. NVDA 2024 split test asserts `pivot_price` is from adjusted closes (defeats Pitfall 1).

---

## Shared Patterns (cross-cutting)

### Pattern A: Atomic Parquet Write (D-11 / Phase 2)
**Source:** `src/screener/persistence.py` lines 273–295 (`_write_parquet_atomic`)
**Apply to:** `write_fundamentals_atomic` (new), `write_pattern_audit_atomic` (new) — both reuse `_write_parquet_atomic` directly via the validated wrapper pattern (lines 422–438 `write_snapshot_atomic` template).

```python
def write_pattern_audit_atomic(df: pd.DataFrame, snapshot_date: str) -> Path:
    """Validate + atomically write per-leg pattern audit to data/pattern_audit/<date>.parquet."""
    _assert_safe_snapshot_date(snapshot_date)
    validated = validate_at_write(PatternAuditSchema, df)
    target = _pattern_audit_dir() / f"{snapshot_date}.parquet"
    _write_parquet_atomic(validated, target)
    log.info("pattern_audit_written", path=str(target), n_rows=len(validated), snapshot_date=snapshot_date)
    return target
```

### Pattern B: Pandera Schema-at-IO-Boundary (D-15 / Phase 2)
**Source:** `src/screener/persistence.py` lines 74–254 (8 existing schemas all with `Config: strict = True, coerce = False`)
**Apply to:** `FundamentalsSchema`, `InsiderSchema`, `PatternAuditSchema`, extended `RankingSnapshotSchema`.

```python
class FundamentalsSchema(pa.DataFrameModel):
    """Per-ticker fundamentals row (EPS history + upcoming earnings)."""
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    fiscal_quarter_end: Series[pd.Timestamp] = pa.Field(nullable=False)
    eps_actual: Series[float] = pa.Field(nullable=True)
    eps_yoy_growth: Series[float] = pa.Field(nullable=True)
    knowable_from: Series[pd.Timestamp] = pa.Field(nullable=False)   # D-13b
    next_earnings_date: Series[pd.Timestamp] = pa.Field(nullable=True)
    next_earnings_hour: Series[str] = pa.Field(isin=["bmo","amc","dmh","unknown"], nullable=False)

    class Config:
        strict = True
        coerce = False
```

### Pattern C: `Final[...]`-Locked Thresholds (D-03 + D-13 / extends Phase 4 DEFAULT_WEIGHTS)
**Source:** `src/screener/signals/composite.py` line 14, 22–36 (`Final[dict]`, `Final[frozenset]`)
**Apply to:** all 8 VCP thresholds in `indicators/patterns.py`; all 5 tie-breaker thresholds in `signals/composite.py`; `PIVOT_ORDER` in `indicators/patterns.py`. Defends against Critical Pitfall #2 (in-sample weight optimization).

```python
from typing import Final

PRIOR_UPTREND_MIN_PCT: Final[float] = 0.30
# ... and 12 more constants ...
```

### Pattern D: `PHASE_4_ZEROED` frozenset reduction (D-16 / proven in Phase 4 D-13)
**Source:** `src/screener/signals/composite.py` line 36 (frozenset literal) and lines 113–115 (scoring loop iterates `weights.items()` and reads `out[f"{key}_component"]`)
**Apply to:** Phase 6 single-line change: `PHASE_4_ZEROED: Final[frozenset[str]] = frozenset()`. The scoring loop discovers the three new component columns with **zero refactor** — Pitfall 6 is the regression to avoid (don't add per-key special cases inside the loop).

### Pattern E: Pure-Function Signals + Indicators / no-I/O (Phase 1 D-16 + tests/test_architecture.py)
**Source:** every `src/screener/indicators/*.py` and `src/screener/signals/*.py` file. Enforced by `tests/test_architecture.py::test_layer_import_contract` + `::test_indicators_signals_pure_no_io_imports` (lines 100–197).
**Apply to:** `indicators/patterns.py`, `signals/qullamaggie.py`, `signals/canslim.py`, and the `tag_playbook` extension to `signals/composite.py`. **Structural defense of D-13b 45-day lag:** signals/canslim.py accepts a pre-filtered fundamentals DataFrame as an argument; it CANNOT call `persistence.read_fundamentals(...)` because `persistence` is in its ALLOWED list but the lag-filter logic lives at `persistence.read_fundamentals` (data-layer-adjacent). Pipeline.py bridges data → signals.

---

## Pre-existing Auxiliary Patterns

### Late-import idiom (avoids circular imports between publishers/pipeline.py and publishers/snapshot.py + persistence)
**Source:** `src/screener/publishers/pipeline.py` lines 164, 169, 175 (`from screener.publishers.report import _add_publisher_columns` *inside* `run_pipeline`)
**Apply to:** Phase 6's added pipeline steps when they reference the extended `persistence.write_pattern_audit_atomic` — keeps import-time graph stable.

### T-3-02 secret-redaction (never `error=str(e)`)
**Source:** `src/screener/cli.py` line 188, 213, 228, 285, 427 (every `log.error(...)` call uses `error_type=type(e).__name__`, NOT `error=str(e)`)
**Apply to:** every new `try/except` in `cli.py refresh-fundamentals`, in `data/fundamentals.py`, in `data/insider.py`. Finnhub + EDGAR exceptions may include API-key URL fragments.

### structlog + stdlib-logger dual setup (tenacity compatibility)
**Source:** `src/screener/data/ohlcv.py` lines 43–48 + `src/screener/data/macro.py` lines 50–55
**Apply to:** `src/screener/data/fundamentals.py`, `src/screener/data/insider.py`.

```python
log = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)  # tenacity requires stdlib logger
```

### Settings additive extension + cache-clear test idiom
**Source:** `src/screener/config.py` (file-end docstring) + `src/screener/persistence.py` lines 612–620 (REVIEW IN-01 iter 2 note)
**Apply to:** Phase 6 `Settings` additions — tests that override env vars MUST call `get_settings.cache_clear()` first.

---

## No Analog Found

| File | Role | Data Flow | Reason | Mitigation |
|------|------|-----------|--------|------------|
| `tests/test_insider_cluster_buy.py` | unit test of SQL+Python rolling-window cluster query | SQLite read | No existing test exercises `sqlite3` read with date-window cluster logic; Pitfall 7 establishes the algorithmic precedent (SQLite RANGE INTERVAL is unsupported). | Use Research §Code Examples §5 template; build SQLite fixture in-memory (`sqlite3.connect(":memory:")`) seeded with 6 synthetic Form 4 rows; assert cluster detector returns expected tickers. |
| `src/screener/data/insider.py` SQLite append portion | SQLite append-only event log writer | event-driven append | No source-layer module currently uses `sqlite3` (only `data/universe.py` uses requests-cache's SQLite *backend*, which is a different concern); `cli.py` line 234 references the future Phase 7 `data/journal.sqlite` but it doesn't exist yet. | Follow Research §"Don't Hand-Roll" recommendation: single `INSERT ... ON CONFLICT(filing_id) DO NOTHING` per nightly batch in one transaction. Phase 6's `insider.py` SETS THE PRECEDENT for the Phase 7 journal SQLite. |

---

## Metadata

**Analog search scope:**
- `src/screener/indicators/` (5 files)
- `src/screener/signals/` (2 files)
- `src/screener/data/` (4 files)
- `src/screener/publishers/` (3 files)
- `src/screener/persistence.py`, `cli.py`, `config.py`, `regime.py`
- `tests/` (32 files)
- `Makefile`, `.env.example`, `.gitignore`, `pyproject.toml`

**Files scanned:** 53
**Pattern extraction date:** 2026-05-16

**Phase 6 design discipline summary:** every locked decision (D-01..D-25) maps to an existing-codebase pattern; the only NEW algorithmic territory is SQLite cluster-buy detection (Pitfall 7 fallback) and `scipy.signal.argrelextrema` pivot finding (Pitfall 2 edge-truncation). All atomic-write, pandera schema, `Final[...]`-locking, scoring-loop-iteration, pure-function discipline, and tenacity-throttle patterns are copy-with-adapt from Phases 1–5.
