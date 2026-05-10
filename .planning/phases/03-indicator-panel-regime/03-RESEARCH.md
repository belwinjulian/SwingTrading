# Phase 3: Indicator Panel & Regime — Research

**Researched:** 2026-05-10
**Domain:** Pure-function cross-sectional indicator panel (SMA/ATR/ADR%/OBV/RS/dryup) + macro data ingest + three-state regime gate with continuous score
**Confidence:** HIGH (pandas-ta-classic 0.4.47, fredapi 0.5.2, yfinance 1.3.0, pandas-datareader 0.10.0 all live-verified against the installed `.venv`; one critical pitfall discovered — pandas-ta returns `None` on short series — and one CONTEXT.md assumption invalidated — Stooq is currently broken via pandas-datareader)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Regime classification thresholds (REG-01, REG-02)**
- **D-01: IBD Market Pulse-inspired three-state thresholds:**
  - **Confirmed Uptrend:** SPY above 200d SMA AND breadth_pct ≥ 60% AND distribution_days ≤ 4 AND VIX < 20
  - **Uptrend Under Pressure:** any single condition fails, OR distribution_days ∈ [5, 8]
  - **Correction:** SPY below 200d SMA OR distribution_days ≥ 9 OR VIX ≥ 30
  - Priority: Correction overrides Uptrend Under Pressure — if any Correction condition fires, the state is Correction regardless of other inputs.
- **D-02: Distribution day counting — SPY-only, strict IBD definition.** SPY close < prev_close by > 0.2% AND SPY volume > prev_volume. Count within rolling 25-session window. Uses only `data/macro/spy.parquet`.

**regime_score formula (REG-02, REG-03)**
- **D-03: Weighted linear blend SPY 30% / Breadth 40% / Dist-days 20% / VIX 10%:**
  ```
  spy_component    = 1.0 if spy_above_200d else 0.0
  breadth_norm     = clip(breadth_pct / 100, 0, 1)
  dist_norm        = clip(1 - (distribution_days / 9), 0, 1)
  vix_norm         = clip(1 - ((vix_level - 15) / 25), 0, 1)
  regime_score     = 0.30*spy_component + 0.40*breadth_norm + 0.20*dist_norm + 0.10*vix_norm
  ```
  Result naturally in [0, 1]. Phase 7 sizing multiplies base risk by `regime_score`.

**Macro data sources (DAT-04)**
- **D-04: Source mapping:** `data/macro/spy.parquet` (yfinance `SPY` OHLCV), `data/macro/qqq.parquet` (yfinance `QQQ` OHLCV), `data/macro/vix.parquet` (yfinance `^VIX` close), `data/macro/nyad.parquet` (Stooq `$NYAD` with R1000-breadth fallback per D-05), `data/macro/yields.parquet` (FRED DGS2/DGS10/T10Y2Y).
- **D-05: NYSE A/D line — Stooq `$NYAD` primary, R1000-breadth fallback.** If Stooq returns empty or > 5% missing values over 2005–present, fall back to `advances - declines` from R1000 panel. Log `nyad_source: stooq | r1000_proxy`. Stored in same `data/macro/nyad.parquet` regardless.
- **D-06: Macro refresh idempotent + incremental.** Same append-from-last-cached-date pattern as Phase 2 D-07. First run backfills from `2005-01-01`.

**Indicator panel structure (IND-01, IND-05)**
- **D-07: `build_panel(snapshot_date)` consumes `persistence.read_panel(snapshot_date)` and returns same (ticker, date) MultiIndex DataFrame with 10 additional columns.** No new I/O. No state, no side effects in `indicators/`.
- **D-08: Tickers with insufficient history get NaN for long-lookback columns.** No drop, no backfill with shorter windows. Downstream signals treat NaN trend-template conditions as `False`.
- **D-09: dryup-ratio = `volume / SMA(volume, 50)`.** Column name `dryup_ratio`. Aligns with VCP Phase 6 breakout-volume baseline.

**RS snapshot persistence (IND-03, look-ahead)**
- **D-10: Phase 3 writes daily RS snapshots to `data/rs_snapshots/YYYY-MM-DD.parquet` after each `make rank` run.** Each snapshot has one row per ticker with `rs_raw` and `rs_rating` (1–99 int). Phase 5 backtest harness reads these point-in-time snapshots.
- **D-11: `data/rs_snapshots/` is gitignored.** `persistence.py` gets `write_rs_snapshot_atomic()` and `read_rs_snapshot()` following Phase 2 D-11 atomic pattern.

**Settings additions (D-12)**
- `MACRO_CACHE_DIR: Path = Path("data/macro")`
- `RS_SNAPSHOT_DIR: Path = Path("data/rs_snapshots")`
- `MACRO_BACKFILL_START: str = "2005-01-01"`
- `REGIME_BREADTH_THRESHOLD: float = 0.60`
- `REGIME_DIST_DAYS_PRESSURE: int = 5`
- `REGIME_DIST_DAYS_CORRECTION: int = 9`
- `REGIME_VIX_CORRECTION: float = 30.0`
- `REGIME_VIX_CONFIRMED: float = 20.0`

### Claude's Discretion

- **Indicator module layout:** `src/screener/indicators/trend.py` (SMA), `relative_strength.py` (RS), `volatility.py` (ATR, ADR%), `volume.py` (OBV, dryup). `indicators/__init__.py` exports `build_panel()` calling each in sequence.
- **Macro CLI:** `screener refresh-macro` (stub from Phase 1) gets a real body. `make macro` calls it. Same `--force` pattern as `refresh-universe`.
- **Regime module API:** `regime.compute_for_date(date, panel) -> pd.Series` and `regime.build_history(start, end) -> pd.DataFrame`.
- **EMA grep CI gate:** `rg "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` returns zero matches; if `rg` unavailable in CI, fall back to `grep -i "ema"`.
- **Golden-file test data:** `tests/test_regime.py` with three fixtures: 2008-Q4 (2008-10-01 to 2009-03-01), 2020-Q1 (2020-02-15 to 2020-04-15), 2022-H1 (2022-01-01 to 2022-07-01). Each must include at least one `Correction` date.

### Deferred Ideas (OUT OF SCOPE)

- **Sector-level RS** → Phase 6 (CANSLIM L). Phase 3 computes only ticker-level RS.
- **Halt-flag / suspension detection** → Phase 6 catalysts.
- **Fundamentals lag enforcement (`knowable_from`)** → Phase 6 (DAT-05).
- **Finnhub earnings calendar** → Phase 6 (CAT-01).
- **`regime_score` → sizing wiring** → Phase 7. Phase 3 only exposes the column.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DAT-04 | `make macro` refreshes SPY, ^IXIC (D-04 says ^VIX, not ^IXIC — the ROADMAP and CONTEXT diverge; CONTEXT.md D-04 is authoritative), ^VIX, NYSE A/D, FRED yields | yfinance OHLCV verified live for SPY/QQQ/^VIX (5-col Open/High/Low/Close/Volume; ^VIX has Volume=0); Stooq `$NYAD` via pandas-datareader currently broken (ParserError on ALL Stooq queries) — R1000 breadth fallback (D-05) is the operative primary path; FRED DGS2/DGS10/T10Y2Y signature verified via fredapi 0.5.2 |
| IND-01 | `indicators.build_panel()` returns 10-column multi-ticker DataFrame: SMA(10/20/50/150/200), ATR(14), ADR%(20), OBV, dryup-ratio + RS rating | pandas-ta-classic 0.4.47 verified live: `ta.sma(close, length=N)` returns `pd.Series` named `SMA_N`; `ta.atr(h,l,c,length=14)` returns `ATRr_14` (Wilder's RMA default — matches methodology); `ta.obv(close, volume)` returns `OBV` |
| IND-02 | SMAs are SMA not EMA; CI grep blocks `ema` in `signals/minervini.py` and `indicators/trend.py` | grep gate is portable across rg/grep; ripgrep is NOT preinstalled on `ubuntu-latest` GitHub runner (verified) — must use `grep -i` for CI portability; `indicators/__init__.py` already has the comment "NOT EMAs in the Trend Template" — must scope the gate to specific files only, not all of `indicators/` |
| IND-03 | IBD-style RS = `RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`, percentile-ranked across universe → 1–99 int | pandas idiom `groupby(level='date').rank(pct=True)` verified live: cross-sectional rank per date, NaN preserved for tickers missing 252d history |
| IND-04 | ADR%(20) = `100 * (mean(high/low over 20 days) - 1)` | Verified live: `100 * ((df['high'] / df['low']).rolling(20).mean() - 1)` produces 10.526 for high=105/low=95 (1.10526 - 1) |
| IND-05 | Indicators are pure functions — no I/O, no global state, panel-in / panel-out | Architecture test (Phase 1 D-16) already enforces — `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` blocks imports of yfinance/requests/sqlite3/etc. from `indicators/` |
| REG-01 | `regime.py` produces one row per date with: SPY 200d trend pass, breadth_pct, distribution_days, VIX | All four columns computable from `data/macro/{spy,vix,nyad}.parquet` + indicator panel (for breadth_pct = % above 200d SMA); pandas idiom for distribution-day counting verified live (rolling 25-session window) |
| REG-02 | Regime emits discrete state ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction} + continuous `regime_score ∈ [0, 1]` | D-03 formula vectorized verified live: produces all values in [0, 1] across a 100-day random panel; vectorizable in single pass for backtest history |
| REG-03 | `regime_score` multiplied into base risk during position sizing | Phase 3 only exposes the column. Phase 7 wires into `sizing.py`. Seam: `regime_score` is one of the columns returned by `regime.compute_for_date()` |
| REG-04 | Golden-file tests verify regime classifies 2008-Q4, 2020-Q1, 2022-H1 as Correction | Three test approaches viable: (a) real cached macro Parquets if backfilled, (b) synthetic SPY price series that crosses 200d SMA on known dates, (c) hybrid — minimal SPY+VIX synthetic series with deterministic dist-day positions. Recommendation: synthetic — see "Golden-file fixture design" below |

</phase_requirements>

## Summary

Phase 3 is a thin computational layer on top of Phase 2's data foundation: every indicator function is a pure pandas/pandas-ta-classic call against a Parquet panel, every macro fetch reuses Phase 2's atomic-write pattern, and the regime module is a five-column DataFrame derived from those macros. The three real risks are all small but unforgiving — (1) pandas-ta-classic returns `None` (not an empty Series) when the input is shorter than the indicator's lookback window, so the panel builder needs a defensive wrapper; (2) Stooq access via pandas-datareader is currently broken in this environment (every symbol returns ParserError because Stooq's response is HTML, not CSV — pandas-datareader 0.10.0 has been frozen since July 2021 and Stooq's anti-bot defenses are now incompatible), so the `$NYAD` fallback to R1000 breadth (D-05) will be the operative primary path; (3) `^VIX` from yfinance returns Volume=0 always — only the Close column is meaningful, and the regime module must only read VIX close.

**Primary recommendation:** Implement the indicator panel as four pure modules under `src/screener/indicators/` each exposing one function that takes the OhlcvPanelSchema panel and returns a same-shape DataFrame with new columns appended. `build_panel()` in `indicators/__init__.py` orchestrates the call chain. Wrap every `pandas_ta` call in a `_safe_apply()` helper that converts `None` returns to a NaN-filled Series. The macro layer ships as `src/screener/data/macro.py` with three independent fetchers (yfinance for SPY/QQQ/^VIX, FRED for yields, Stooq+breadth fallback for $NYAD) all writing through the existing `_write_parquet_atomic()` primitive. The regime module is a single `regime.py` file with three pure functions (`_compute_distribution_days`, `compute_for_date`, `build_history`) that read pre-built artifacts only. Golden-file tests use synthetic SPY/VIX series with deterministic distribution-day injection rather than depending on a live macro Parquet at test time.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| OHLCV panel read | persistence (Phase 2) | — | Existing `read_panel()`; Phase 3 consumes |
| Macro data fetch (HTTP/network) | data (`data/macro.py`) | — | Layered DAG: only `data/` makes network calls (Phase 1 D-16 enforced) |
| Macro Parquet write/read | persistence (`write_*_atomic`, `read_*`) | data (calls into) | Atomic-write contract owned by `persistence`; data calls in |
| Indicator math (SMA/ATR/ADR%/OBV/dryup) | indicators (`trend.py`, `volatility.py`, `volume.py`) | persistence (read panel) | Pure functions; no I/O; tests/test_architecture asserts no network imports |
| RS percentile (cross-sectional) | indicators (`relative_strength.py`) | — | Pure DataFrame transform; uses `groupby('date').rank(pct=True)` |
| RS snapshot persistence | persistence (`write_rs_snapshot_atomic`) | indicators emits, cli/orchestrator calls writer | Cross-layer call: `indicators.build_panel` returns DataFrame, CLI persists snapshot |
| Regime computation | regime (`regime.py`) | data (read macro), indicators (compute breadth from panel) | Imports `data/` + `indicators/` per architecture test ALLOWED dict |
| CLI orchestration (`refresh-macro`) | cli (composition root) | data, persistence | cli is the only module allowed to import broadly |
| CI gate (EMA grep) | `.github/workflows/ci.yml` step | — | Tooling layer; not a Python concern |

## Standard Stack

### Core (already in pyproject.toml)

| Library | Version | Purpose | Why Standard | Source |
|---------|---------|---------|--------------|--------|
| pandas-ta-classic | 0.4.47 | SMA / ATR / OBV (Wilder's RMA default for ATR) | Pure Python, no C deps; methodology pinned by CLAUDE.md | [VERIFIED: live `import pandas_ta_classic`] |
| pandas | 2.2.x | DataFrames; `groupby('date').rank(pct=True)` for cross-sectional RS | Native pandas idiom; no extra dep | [VERIFIED: live import] |
| numpy | 2.x | Numerics, clip, where | NumPy 2 required by pandas-ta-classic | [VERIFIED: pyproject pin] |
| yfinance | 1.3.0 | SPY/QQQ/^VIX OHLCV — same adapter as Phase 2 | Free, no key needed; reuse Phase 2's tenacity wrapper | [VERIFIED: live `yf.download('SPY')` returns 5-col OHLCV] |
| fredapi | 0.5.2 | FRED Treasury yields (DGS2/DGS10/T10Y2Y) | Standard FRED Python client; `Fred(api_key=...).get_series(sid, observation_start=...)` | [VERIFIED: signature `Fred.__init__(api_key, api_key_file, proxies)`, `Fred.get_series(series_id, observation_start, observation_end, **kwargs)`] |
| pandas-datareader | 0.10.0 | Stooq `$NYAD` adapter (already in Phase 2 stack) | The library Phase 2 D-14 locked in | [VERIFIED: live import; **frozen since July 2021**, currently rate-limited / broken on Stooq endpoints — see Pitfall 1] |
| pandera | 0.31.1 | New `MacroSchema`, `RsSnapshotSchema` — same DataFrameModel pattern as Phase 2 | Schema seam; Phase 1 D-13 / Phase 2 D-15 locked the pattern | [VERIFIED: existing `OhlcvPanelSchema` shape] |
| structlog | 25.5.x | Structured event logging | Phase 1 baseline | [VERIFIED: existing `obs.py`] |
| tenacity | 9.1.x | yfinance + FRED retry wrappers (reuse Phase 2 idiom) | Already in Phase 2 stack | [VERIFIED: pyproject pin] |

### Verified versions (npm-equivalent registry check via `uv pip list`)

```
pandas-ta-classic   0.4.47   (verified live, returns Series with SMA_N column name)
fredapi             0.5.2    (verified live)
pandas-datareader   0.10.0   (verified live; frozen since 2021-07; Stooq endpoint currently broken)
yfinance            1.3.0    (verified live; SPY/QQQ/^VIX all return 5-col OHLCV)
```

### Don't add — already in stack

| Library | Why not adding |
|---------|----------------|
| TA-Lib | C-deps break Streamlit Cloud (Phase 1 FND-01); pandas-ta-classic is the pure-Python equivalent |
| `pandas-ta` (PyPI) | Maintainer change; in beta. Use `pandas-ta-classic`. Module name is identical (`import pandas_ta_classic as ta`). |

## Architecture Patterns

### System Architecture Diagram

```
                 ┌─────────────────────────┐
                 │  data/macro/*.parquet   │
                 │  (spy/qqq/vix/nyad/    │  ← writes from data/macro.py
                 │   yields)               │
                 └────────────┬────────────┘
                              │
   ┌───────────────────┐      │       ┌─────────────────────────┐
   │ data/ohlcv/<T>/   │──────┴──────▶│   regime.compute_for_   │
   │ prices.parquet    │              │   date(date, panel)      │──▶ DataFrame row:
   │ (Phase 2)         │              │                          │     spy_above_200d (bool)
   └───────┬───────────┘              │  • Reads macro Parquets  │     breadth_pct (float)
           │                          │  • Reads panel for       │     distribution_days (int)
           │                          │    breadth_pct           │     vix_level (float)
           │                          │  • Pure function         │     regime_state (str)
           │                          └──────────────────────────┘     regime_score (float)
           │
           │
           ▼
  ┌────────────────────────────┐
  │ persistence.read_panel(    │
  │   snapshot_date) → panel   │
  │ (Phase 2 OhlcvPanelSchema) │
  └────────────┬───────────────┘
               │
               ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │  indicators/build_panel(panel) → panel + 10 columns                    │
  │                                                                        │
  │  ┌──────────────┐  ┌─────────────────┐  ┌──────────────┐  ┌──────────┐│
  │  │ trend.py     │→ │ volatility.py   │→ │ volume.py    │→ │ relative_││
  │  │ SMA 10/20/50 │  │ ATR(14)         │  │ OBV          │  │ strength ││
  │  │     150/200  │  │ ADR%(20)        │  │ dryup_ratio  │  │ rs_raw   ││
  │  └──────────────┘  └─────────────────┘  └──────────────┘  │ rs_rating││
  │  All pure; panel-in / panel-out; same MultiIndex          └──────────┘│
  └──────────────────────────┬─────────────────────────────────────────────┘
                             │
                             ▼
            ┌────────────────────────────────────┐
            │ persistence.write_rs_snapshot_     │  ← cli orchestrates;
            │ atomic(date, df) →                 │     called once per `make rank`
            │ data/rs_snapshots/<date>.parquet   │     (Phase 4 wires the call)
            └────────────────────────────────────┘
```

Data flow: Phase 2 OHLCV panel + macro fetches feed pure indicator + regime computations; results persist atomically.

### Recommended Module Layout

```
src/screener/
  data/
    macro.py                 # NEW: yfinance SPY/QQQ/VIX, FRED yields, Stooq+fallback A/D
  indicators/
    __init__.py              # MODIFY: export build_panel()
    trend.py                 # NEW: sma_panel(panel, lengths=[10,20,50,150,200])
    volatility.py            # NEW: atr_panel, adr_pct_panel
    volume.py                # NEW: obv_panel, dryup_ratio_panel
    relative_strength.py     # NEW: rs_panel(panel) → rs_raw + rs_rating
  persistence.py             # MODIFY: + MacroSchema, RsSnapshotSchema, write_rs_snapshot_atomic, read_rs_snapshot, write_macro_atomic, read_macro
  regime.py                  # MODIFY (currently 8-line stub): compute_distribution_days, compute_for_date, build_history
  config.py                  # MODIFY: + 8 D-12 Settings fields
  cli.py                     # MODIFY: refresh_macro real body
.github/workflows/ci.yml     # MODIFY: + ema-grep step
```

### Pattern 1: Defensive pandas-ta wrapper (NEW IDIOM — no Phase 2 analog)

**What:** Every `pandas_ta_classic.<fn>()` call must defend against `None` returns when the input series is shorter than the lookback window.

**Why:** Verified live — `ta.sma(short_series, length=200)` returns `None`, not a NaN-filled Series. `ta.atr(h, l, c, length=14)` returns `None` when input has fewer than 14 rows. `ta.obv(close, volume)` returns `None` similarly. The panel builder MUST handle this or risk an `AttributeError: 'NoneType' object has no attribute 'rename'` at runtime when a fresh ticker has < 200 days of history.

**When to use:** Every call to `ta.sma`, `ta.atr`, `ta.obv` inside `indicators/`.

**Example:**
```python
# Source: live verification 2026-05-10
import pandas as pd
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

Same wrapper pattern for `ta.atr` and `ta.obv`.

### Pattern 2: Cross-sectional RS percentile (canonical)

**What:** Compute RS rating cross-sectionally per date, preserving NaN for tickers with insufficient history.

**Verified live 2026-05-10** on a 5-ticker × 10-day MultiIndex panel with NaN injected for `AAA` first 3 days — output preserved NaN exactly as injected.

**Example:**
```python
# Source: live verification 2026-05-10
def rs_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute rs_raw and rs_rating for the (ticker, date) MultiIndex panel.

    Formula (CLAUDE.md §"Signal Formulas — IBD-style RS"):
        rs_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
        rs_rating = (rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(int)

    Cross-sectional rank within each date (groupby level='date'). NaN tickers
    (insufficient history) are excluded from the ranking and receive NaN
    rs_rating per CONTEXT.md "RS percentile ranking excludes NaN tickers."
    """
    # Per-ticker shifts: groupby level='ticker' so .shift() respects per-ticker history.
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
    # Cross-sectional rank per date; NaN preserved.
    pct = rs_raw.groupby(level="date").rank(pct=True)
    rs_rating = (pct * 99).round().clip(1, 99)  # NaN survives clip
    # Convert to nullable Int64 to keep NaN in an integer column.
    rs_rating = rs_rating.astype("Int64")
    return pd.DataFrame({"rs_raw": rs_raw, "rs_rating": rs_rating})
```

### Pattern 3: ADR% (Qullamaggie 20-day)

**Verified live 2026-05-10** — `100 * ((high/low).rolling(20).mean() - 1)` produces 10.526% for high=105/low=95.

```python
def adr_pct_panel(panel: pd.DataFrame, length: int = 20) -> pd.Series:
    """ADR%(20) per CLAUDE.md §"Signal Formulas — ADR%":
        ADR_pct = 100 * (mean(high/low over 20 days) - 1)
    Per-ticker rolling — groupby level='ticker' so the window doesn't span tickers.
    """
    ratio = panel["high"] / panel["low"]
    return (
        100.0
        * (ratio.groupby(level="ticker").rolling(length).mean().droplevel(0) - 1.0)
    ).rename("adr_pct")
```

### Pattern 4: Distribution-day rolling counter (regime)

**Verified live 2026-05-10** — injected 4 distribution days at known indices, idiom returned the correct rolling-25 count.

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

### Pattern 5: Vectorized regime_score for backtest history

**Verified live 2026-05-10** — formula vectorizes across 100 dates, produces values in [0, 1] for the full range.

```python
def _regime_score(df: pd.DataFrame) -> pd.Series:
    """Vectorized D-03 formula across an arbitrary date range. df must have
    columns: spy_above_200d (bool), breadth_pct, distribution_days, vix_level.
    """
    spy_component = df["spy_above_200d"].astype(float)
    breadth_norm  = (df["breadth_pct"] / 100.0).clip(0.0, 1.0)
    dist_norm     = (1.0 - df["distribution_days"] / 9.0).clip(0.0, 1.0)
    vix_norm      = (1.0 - (df["vix_level"] - 15.0) / 25.0).clip(0.0, 1.0)
    return 0.30*spy_component + 0.40*breadth_norm + 0.20*dist_norm + 0.10*vix_norm
```

### Pattern 6: R1000 breadth fallback for `$NYAD` (D-05 critical path)

Stooq is currently broken (see Pitfall 1) — the breadth fallback is the operative primary path until Stooq is fixed upstream. Implement it as the path that will run by default when Stooq raises.

```python
def _compute_breadth_fallback(start: str, today: date) -> pd.DataFrame:
    """R1000-derived advance-decline line.

    Reads the most-recent universe snapshot, joins per-ticker prices, computes
    daily advances - declines = N(close > prev_close) - N(close < prev_close).
    Returns DataFrame indexed by date with columns 'advances', 'declines',
    'ad_line' (cumulative advances - declines).
    """
    from screener.persistence import read_panel, _latest_universe_snapshot  # type: ignore
    # Load the most recent universe snapshot to drive panel selection.
    snap = _latest_universe_snapshot()  # cli.py helper; promote into persistence
    panel = read_panel(snap.stem)  # MultiIndex (ticker, date) panel
    closes = panel["close"].unstack(level="ticker")  # date × ticker wide frame
    deltas = closes.diff()
    advances = (deltas > 0).sum(axis=1)
    declines = (deltas < 0).sum(axis=1)
    out = pd.DataFrame({"advances": advances, "declines": declines})
    out["ad_line"] = (out["advances"] - out["declines"]).cumsum()
    out = out.loc[start:str(today)]
    return out
```

The MacroSchema must accept this shape. Schema for `data/macro/nyad.parquet`:
```python
class NyadMacroSchema(pa.DataFrameModel):
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    advances: Series[int] = pa.Field(ge=0, nullable=False)
    declines: Series[int] = pa.Field(ge=0, nullable=False)
    ad_line: Series[int] = pa.Field(nullable=False)  # cumulative; can be negative
    class Config:
        strict = True
        coerce = False
```

### Pattern 7: Macro Parquet schemas (additive Phase 3)

Three new pandera DataFrameModel schemas land in `persistence.py`, mirroring Phase 2 D-15 style:

```python
class MacroOhlcvSchema(pa.DataFrameModel):
    """Single-index (date) macro OHLCV — SPY, QQQ. Lowercase columns."""
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    open: Series[float] = pa.Field(ge=0.0, nullable=False)
    high: Series[float] = pa.Field(ge=0.0, nullable=False)
    low: Series[float] = pa.Field(ge=0.0, nullable=False)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    volume: Series[int] = pa.Field(ge=0, nullable=False)  # ^VIX has 0 — see Pitfall 4
    class Config:
        strict = True
        coerce = False

class VixSchema(pa.DataFrameModel):
    """^VIX is close-only — yfinance returns Volume=0 always (verified live)."""
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    close: Series[float] = pa.Field(ge=0.0, nullable=False)
    class Config:
        strict = True
        coerce = False

class YieldsSchema(pa.DataFrameModel):
    """FRED yields — DGS2, DGS10, T10Y2Y in a single Parquet."""
    date: Index[pd.Timestamp] = pa.Field(check_name=True)
    dgs2: Series[float] = pa.Field(nullable=True)   # weekend gaps; FFill at consumer side
    dgs10: Series[float] = pa.Field(nullable=True)
    t10y2y: Series[float] = pa.Field(nullable=True)
    class Config:
        strict = True
        coerce = False

class RsSnapshotSchema(pa.DataFrameModel):
    """One row per ticker, taken on a single trading date."""
    ticker: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z][A-Z0-9\-]{0,9}$")
    rs_raw: Series[float] = pa.Field(nullable=True)        # NaN if ticker has < 252d
    rs_rating: Series[pd.Int64Dtype] = pa.Field(nullable=True)  # nullable Int64
    class Config:
        strict = True
        coerce = False
```

### Anti-Patterns to Avoid

- **Computing RS per-ticker and then ranking** — wrong shape, breaks cross-sectional invariant. Compute `rs_raw` first as a single Series over the full MultiIndex, then `groupby(level='date').rank(pct=True)`.
- **Calling `ta.sma()` without the `_safe_*` wrapper** — silent `None` return crashes downstream concatenation.
- **Reading VIX OHLCV when only Close is meaningful** — Volume=0 for ^VIX every day; treating it as zero-volume "no trading happened" elsewhere wastes a column. Use `VixSchema` (close-only).
- **Forward-filling FRED yields inside `data/macro.py`** — store the raw FRED series with weekend NaN; the consumer (regime or signals) ffills at read time. Keeps the cache faithful to source.
- **Recomputing RS with future data in the backtest** — RS snapshots in `data/rs_snapshots/` are point-in-time-frozen; Phase 5 backtest reads them, not `build_panel()`.
- **Importing from `data/` inside `indicators/`** — Phase 1 D-16 architecture test will fail. `indicators/` reads ONLY through `persistence.read_panel()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SMA computation | Hand-rolled `df.rolling(N).mean()` | `pandas_ta_classic.sma(close, length=N)` | Methodology pinned by CLAUDE.md; ensures consistent column name `SMA_N` for downstream signals |
| ATR with Wilder's smoothing | Hand-rolled True Range + Wilder's RMA | `pandas_ta_classic.atr(h, l, c, length=14)` | Default `mamode='rma'` is Wilder's; matches docs/methodology.md §6 |
| OBV | Hand-rolled cumulative volume | `pandas_ta_classic.obv(close, volume)` | Trivial but consistent with stack |
| Cross-sectional rank | Manual loop over dates with `argsort` | `panel.groupby(level='date').rank(pct=True)` | Pandas-native; verified live preserves NaN |
| Atomic Parquet write | New `tempfile`+`os.replace` block | `persistence._write_parquet_atomic(df, path)` | Phase 2 D-11 contract; reuse 1:1 |
| Pandera schemas | Inline `assert df.columns == ...` checks | New DataFrameModel classes in `persistence.py` | Phase 2 D-15 / D-16 schema seam pattern |
| FRED HTTP calls | Hand-rolled requests to fred.stlouisfed.org | `fredapi.Fred(api_key=...).get_series(sid)` | Rate limit handling, JSON parsing built in |
| yfinance retry | Hand-rolled retry loop | Reuse Phase 2 `data/ohlcv.py` `@retry` decorator pattern (tenacity) | Already battle-tested in Phase 2 |
| Stooq client | New `requests.get` wrapper | Reuse existing `data/stooq.py` (which already exists from Phase 2 D-14) | Same StaleOrEmptyError contract; same column normalization |

**Key insight:** Phase 3 reuses the Phase 2 atomic-write primitive, the schema pattern, and the tenacity wrapper verbatim. The only NEW idiom is the `_safe_*` wrapper for pandas-ta-classic — every other primitive already exists in the codebase.

## Common Pitfalls

### Pitfall 1: Stooq is currently broken via pandas-datareader (HIGH severity)

**What goes wrong:** Every call `pdr.DataReader(<any_symbol>, 'stooq')` raises `pandas.errors.ParserError: Error tokenizing data. C error: Expected 1 fields in line 6, saw 2` — verified live 2026-05-10 against `^SPX`, `^VIX`, `AAPL.US`, `$NYAD`, `^NYAD`, `NYAD.US`, `$NYAD.US`. Stooq is now serving HTML (rate-limit notice / cookie wall) where pandas-datareader expects CSV.

**Why it happens:** pandas-datareader 0.10.0 has been frozen since July 2021. Stooq has changed its anti-bot defenses since. Community issue #955 documents this since 2022.

**How to avoid:** Treat the R1000-breadth fallback (D-05) as the **operative primary path** for `$NYAD`. The Stooq attempt should be made (per D-05 wording), but expect it to fail and route through `_compute_breadth_fallback()` cleanly. Log `nyad_source: r1000_proxy` as the typical case and `nyad_source: stooq` as the rare case. Add an integration test marker `@pytest.mark.integration` that exercises the Stooq path live (will be skipped in fast CI but caught when `-m integration` is added).

**Warning signs:** Run `screener refresh-macro` and observe `nyad_source` in structured logs — if it's always `r1000_proxy`, that's expected today.

### Pitfall 2: pandas-ta-classic returns `None` on short series (HIGH severity)

**What goes wrong:** `ta.sma(short_close_series, length=200)` returns `None`, not a NaN Series. Downstream `result.rename(...)` or DataFrame concat crashes with `AttributeError: 'NoneType' object has no attribute 'rename'`. Same for `ta.atr` (length=14, < 14 rows) and `ta.obv`.

**Why it happens:** pandas-ta-classic prints `[X] Series has N rows but indicator requires at least M. Returning None.` to stderr and returns Python `None`. This is the library's "don't compute on insufficient data" semantic, but it forces the caller to handle `None`.

**How to avoid:** Wrap every `pandas_ta` call in `_safe_apply()` (Pattern 1). Add a unit test: `test_safe_sma_on_short_series_returns_nan_series_not_none`.

**Warning signs:** `AttributeError: 'NoneType' has no attribute 'rename'` traceback originating in `indicators/trend.py`.

### Pitfall 3: pandas-ta-classic SMA produces NaN warmup; downstream signals must treat NaN as "fail"

**What goes wrong:** `ta.sma(close, length=200)` returns 199 NaN entries before the first valid value. Phase 4's Trend Template will compute `Close > SMA200` per-row; `NaN comparisons return False`, which is the correct behavior — but make sure that's the intent. (CONTEXT.md D-08: tickers with insufficient history don't pass the gate. False is correct.)

**How to avoid:** Document explicitly in `indicators/trend.py` docstring: "Tickers with < N days of history get NaN; downstream gates treat NaN as failed." Add a unit test that asserts `Close > SMA200` returns `False` (or NaN — same effect downstream) for the warmup window.

**Warning signs:** None at runtime; this is correct behavior. Risk is misinterpreting the panel during debugging.

### Pitfall 4: ^VIX has Volume=0 always; only Close is meaningful (MEDIUM severity)

**What goes wrong:** Code that treats `data/macro/vix.parquet` as full OHLCV will see `volume=0` everywhere and may flag false data-quality issues. Or a regime computation reading the wrong column.

**Why it happens:** The VIX is an index, not a tradable security; yfinance returns the OHLC of the index quote (which IS meaningful — VIX has intraday Open/High/Low/Close ranges) but Volume=0 because there's no underlying trading volume.

**How to avoid:** Use a separate `VixSchema` (close-only Series) for `data/macro/vix.parquet`. The yfinance fetcher writes `df[['Close']].rename(columns=str.lower)` only. Regime module reads `vix.parquet` and uses the `close` column directly as `vix_level`.

**Warning signs:** `volume == 0` everywhere in `vix.parquet` is the canary that you forgot to drop columns.

### Pitfall 5: FRED has weekday-only data; weekend gaps must be handled at consumer side

**What goes wrong:** Joining FRED yields with the OHLCV panel on date will produce NaN on Saturday/Sunday rows (which don't exist in the panel anyway since OHLCV is also weekday-only) AND on US trading holidays where FRED publishes but markets are closed (or vice versa).

**Why it happens:** FRED runs on a different calendar than NYSE.

**How to avoid:** Store FRED yields in `yields.parquet` AS-RECEIVED with NaN gaps. At the regime/signals layer, use `pd.merge_asof(panel, yields, left_index=True, right_index=True, direction='backward')` or `yields.reindex(panel.index).ffill()` to align — backward-fill is correct because at time t the most recently published yield IS the live value.

**Warning signs:** NaN regime_score on US trading days that fall after a FRED-only holiday (e.g., Columbus Day).

### Pitfall 6: EMA grep gate scope must NOT include comments mentioning "EMAs"

**What goes wrong:** `indicators/__init__.py` line 4 contains the comment "SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4)". A naive `grep -i "ema" src/screener/indicators/` matches this and fails CI even though no EMA code exists.

**Why it happens:** The grep gate per IND-02 is correctly scoped to **specific files** (`src/screener/signals/minervini.py` and `src/screener/indicators/trend.py`) — but a planner/implementer who broadens the scope will trip on legitimate comments.

**How to avoid:** The CI step matches CONTEXT.md exactly:
```yaml
- name: SMA-not-EMA gate (IND-02)
  run: |
    if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then
      echo "ERR: 'ema' reference found in SMA-only files. See IND-02 / CLAUDE.md §13.6 pitfall #4."
      exit 1
    fi
```
Note: `signals/minervini.py` and `indicators/trend.py` may not exist when this CI runs first (Phase 4 ships minervini.py). Use `2>/dev/null` to make the test resilient to missing files. Once both files exist, the grep gate is meaningful.

**Warning signs:** CI failing on Phase 3 PR before Phase 4 even ships — the grep step needs to handle "file doesn't exist" without exiting non-zero spuriously.

### Pitfall 7: yfinance ^VIX index name is `Date` not `date`; Phase 2 cache normalization needed

**What goes wrong:** Phase 2's `fetch_ohlcv` lowercases the index name to `'date'` AFTER it lowercases columns. Phase 3's macro fetch must do the same (the existing yfinance fetcher in `data/ohlcv.py` already does this — copy the idiom).

**How to avoid:** In `data/macro.py`, after `yf.download(...)`, do:
```python
df = df.rename(columns=str.lower)
if df.index.name is None or df.index.name.lower() != "date":
    df.index.name = "date"
```
This is the same idiom as `src/screener/data/ohlcv.py` lines 86–88 — copy verbatim.

### Pitfall 8: Cross-sectional rank inside groupby + per-ticker shift ordering

**What goes wrong:** Computing `panel['close'].shift(63)` on a (ticker, date) MultiIndex panel naively shifts ACROSS the ticker boundary. Ticker AAPL's row at date X gets shifted onto BBB's row from 63 rows earlier in the iteration order — completely wrong.

**Why it happens:** pandas `Series.shift()` is positional, not group-aware.

**How to avoid:** Always `groupby(level='ticker').shift(N)` for per-ticker time-series shifts. Verified live in Pattern 2.

**Warning signs:** RS values look "too synchronized" across the universe, or the first 63 rows of every ticker are NaN (correct) but rows after are nonsensical.

### Pitfall 9: `rs_rating` must be nullable Int64, not int

**What goes wrong:** `int` cannot hold NaN; tickers with insufficient history (NaN `rs_raw`) cannot be assigned an integer `rs_rating`. Casting `(pct * 99).round().astype(int)` raises `IntCastingNaNError`.

**How to avoid:** Use pandas nullable integer dtype: `.astype('Int64')` (capital I, the Pandas extension dtype) instead of `int` or `'int64'`. Pandera schema accepts `Series[pd.Int64Dtype]` (note: in pandera 0.31, the syntax is `Series[pd.Int64Dtype]` or `Series[int]` with `nullable=True` depending on minor version — verify against existing `OhlcvPanelSchema` import style and prefer the same pattern).

**Warning signs:** `IntCastingNaNError` when concatenating the indicator panel.

### Pitfall 10: Atomic-write requires same-filesystem; per-ticker dir must exist

**What goes wrong:** `_write_parquet_atomic(df, target)` calls `target.parent.mkdir(parents=True, exist_ok=True)` already (verified in `persistence.py` line 162) — so this is handled. But for `data/macro/`, `data/rs_snapshots/`, the dir must exist OR the helper must create it. Same for `data/rs_snapshots/<date>.parquet`.

**How to avoid:** Verify that `_write_parquet_atomic` is reused 1:1 — its `mkdir(parents=True, exist_ok=True)` line covers macro and rs_snapshots paths automatically.

**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'data/macro/.spy.parquet.{pid}.tmp'` on first macro run. Fixed by using `_write_parquet_atomic` not a hand-rolled writer.

### Pitfall 11: `read_panel` skips missing tickers — breadth_pct denominator must use universe size, not panel size

**What goes wrong:** `persistence.read_panel(snapshot_date)` SKIPS tickers in the universe whose `prices.parquet` doesn't exist (verified in `persistence.py` lines 311–312). Computing `breadth_pct = (close > sma200).sum() / len(panel.unique('ticker'))` then under-counts the denominator and inflates breadth.

**How to avoid:** Compute breadth as `(close > sma200).sum() / universe_size` where `universe_size = len(read_universe(snapshot_date))`. Or: compute breadth at the panel level but document that the denominator is "tickers with sufficient history" — both are valid; pick one and write a unit test asserting the convention.

**Recommendation:** Use `n_with_data = (panel['close'].notna() & panel['sma_200'].notna()).groupby(level='date').sum()` as the denominator. Tickers without 200d history simply don't participate. This matches CONTEXT.md "tickers with insufficient history get NaN" intent.

## Runtime State Inventory

> Phase 3 is greenfield-additive — no rename, no refactor, no migration. This section is omitted per the gating rule.

## Code Examples

### Example 1: build_panel orchestrator (`indicators/__init__.py`)

```python
# Source: synthesis of Patterns 1+2+3, verified primitives 2026-05-10
"""indicators — pure-function indicator panel.

build_panel(snapshot_date) reads the Phase 2 OHLCV panel and returns a
DataFrame with the original columns plus 10 indicator columns.
"""
from __future__ import annotations
import pandas as pd
import pandas_ta_classic as ta

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

### Example 2: SMA panel with safe wrapper (`indicators/trend.py`)

```python
# Source: live verification of pandas-ta-classic 0.4.47 None-on-short return
"""trend — SMA panel computations. NO EMAs (CLAUDE.md §13.6 pitfall #4).

This module is the SMA-only file gated by the IND-02 CI grep — do not add
EMA code, do not even reference 'ema' in comments here.
"""
from __future__ import annotations
import pandas as pd
import pandas_ta_classic as ta


def _safe_sma(close: pd.Series, length: int) -> pd.Series:
    result = ta.sma(close, length=length)
    if result is None:  # pandas-ta-classic returns None on short input
        return pd.Series(float("nan"), index=close.index, name=f"SMA_{length}")
    return result


def sma_panel(
    panel: pd.DataFrame, lengths: tuple[int, ...] = (10, 20, 50, 150, 200)
) -> pd.DataFrame:
    """Append sma_<length> columns to the panel, computed per-ticker."""
    out = panel.copy()
    for L in lengths:
        col = f"sma_{L}"
        out[col] = (
            panel.groupby(level="ticker")["close"]
            .apply(lambda c: _safe_sma(c, L).reset_index(level=0, drop=True))
        )
    return out
```

### Example 3: ATR panel (`indicators/volatility.py`)

```python
# Source: live verification — ta.atr returns 'ATRr_14' (Wilder's RMA default)
from __future__ import annotations
import pandas as pd
import pandas_ta_classic as ta


def _safe_atr(h: pd.Series, l: pd.Series, c: pd.Series, length: int) -> pd.Series:
    result = ta.atr(h, l, c, length=length)
    if result is None:
        return pd.Series(float("nan"), index=c.index, name=f"ATRr_{length}")
    return result


def atr_panel(panel: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Append atr_14 column (Wilder's RMA per docs/methodology.md §6)."""
    out = panel.copy()
    def _per_ticker(g: pd.DataFrame) -> pd.Series:
        return _safe_atr(g["high"], g["low"], g["close"], length).reset_index(
            level=0, drop=True
        )
    out[f"atr_{length}"] = panel.groupby(level="ticker").apply(_per_ticker)
    return out


def adr_pct_panel(panel: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """ADR%(20) per CLAUDE.md §"Signal Formulas — ADR%"."""
    out = panel.copy()
    ratio = panel["high"] / panel["low"]
    out["adr_pct"] = (
        100.0
        * (ratio.groupby(level="ticker")
                .rolling(length).mean()
                .droplevel(0)
                - 1.0)
    )
    return out
```

### Example 4: regime.compute_for_date (`regime.py`)

```python
# Source: synthesis of Patterns 4+5, D-01, D-02, D-03
"""regime — universe-wide market regime gate.

Reads pre-built artifacts (data/macro/{spy,vix,nyad}.parquet, indicator panel)
to emit a single-row Series per date, or a DataFrame across a date range.
"""
from __future__ import annotations
from typing import Literal

import pandas as pd

from screener.config import get_settings
from screener.indicators import build_panel  # OK: regime → indicators allowed (architecture)
from screener.persistence import read_macro_spy, read_macro_vix  # NEW Phase 3 readers


RegimeState = Literal["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"]


def _classify_state(
    spy_above_200d: bool,
    breadth_pct: float,
    distribution_days: int,
    vix_level: float,
    settings,
) -> RegimeState:
    """D-01 priority: Correction overrides any other state."""
    # Correction triggers (D-01)
    if (
        not spy_above_200d
        or distribution_days >= settings.REGIME_DIST_DAYS_CORRECTION
        or vix_level >= settings.REGIME_VIX_CORRECTION
    ):
        return "Correction"
    # Confirmed Uptrend
    if (
        spy_above_200d
        and breadth_pct >= settings.REGIME_BREADTH_THRESHOLD * 100
        and distribution_days <= settings.REGIME_DIST_DAYS_PRESSURE - 1  # ≤ 4
        and vix_level < settings.REGIME_VIX_CONFIRMED
    ):
        return "Confirmed Uptrend"
    # Default
    return "Uptrend Under Pressure"


def _compute_distribution_days(spy: pd.DataFrame, window: int = 25) -> pd.Series:
    """Strict IBD: SPY close down > 0.2% AND volume > prev_volume; rolling 25."""
    prev_close = spy["close"].shift(1)
    prev_vol = spy["volume"].shift(1)
    is_dist_day = (
        (spy["close"] / prev_close - 1.0 < -0.002)
        & (spy["volume"] > prev_vol)
    )
    return is_dist_day.rolling(window).sum().fillna(0).astype(int)


def compute_for_date(date: pd.Timestamp, panel: pd.DataFrame) -> pd.Series:
    """Single-date regime row. `panel` is the indicator panel with sma_200."""
    spy = read_macro_spy()
    vix = read_macro_vix()
    settings = get_settings()

    # SPY 200d trend
    spy_sma200 = spy["close"].rolling(200).mean()
    spy_above_200d = bool(spy.loc[date, "close"] > spy_sma200.loc[date])
    # Breadth: % of universe above 200d SMA on this date
    snapshot = panel.xs(date, level="date")  # ticker × columns
    has_data = snapshot["close"].notna() & snapshot["sma_200"].notna()
    breadth_pct = float((snapshot.loc[has_data, "close"] > snapshot.loc[has_data, "sma_200"]).mean() * 100)
    # Distribution days
    dist_days = int(_compute_distribution_days(spy).loc[date])
    # VIX
    vix_level = float(vix.loc[date, "close"])
    # State
    state = _classify_state(spy_above_200d, breadth_pct, dist_days, vix_level, settings)
    # Score
    spy_component = 1.0 if spy_above_200d else 0.0
    breadth_norm = max(0.0, min(1.0, breadth_pct / 100.0))
    dist_norm = max(0.0, min(1.0, 1.0 - dist_days / 9.0))
    vix_norm = max(0.0, min(1.0, 1.0 - (vix_level - 15.0) / 25.0))
    regime_score = 0.30*spy_component + 0.40*breadth_norm + 0.20*dist_norm + 0.10*vix_norm

    return pd.Series({
        "spy_above_200d": spy_above_200d,
        "breadth_pct": breadth_pct,
        "distribution_days": dist_days,
        "vix_level": vix_level,
        "regime_state": state,
        "regime_score": regime_score,
    }, name=date)
```

### Example 5: refresh_macro CLI body (`cli.py` modification)

```python
# Source: extension of existing cli.py refresh-universe pattern
@app.command("refresh-macro")
def refresh_macro(
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-fetch from MACRO_BACKFILL_START even if cache exists."),
    ] = False,
) -> None:
    """Refresh macro inputs (SPY, QQQ, ^VIX, NYSE A/D, FRED yields). DAT-04."""
    configure_logging()
    settings = get_settings()
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pandas-ta` (PyPI) | `pandas-ta-classic` 0.4.47 | 2024-2025 (original repo removed; PyPI maintainer changed) | Pin enforced via pyproject.toml comment; module name unchanged (`import pandas_ta_classic as ta`) |
| TA-Lib (C extension) | `pandas-ta-classic` (pure Python) | n/a (CLAUDE.md decision) | Streamlit Cloud compatibility; Phase 1 FND-01 |
| `yf.download(tickers=[...], threads=True)` | Single-ticker sequential + `threads=False, multi_level_index=False` | 2024-2025 (yfinance batch mode 429 risk) | Phase 2 D-10 already enforces; Phase 3 macro fetcher uses same pattern |
| Stooq via pandas-datareader | Currently broken; R1000-breadth fallback (D-05) is operative primary | 2022+ (pandas-datareader frozen 2021-07) | Plan must NOT assume Stooq returns data; treat fallback as the default path |

**Deprecated / outdated:**
- pandas-ta (PyPI) — never use
- TA-Lib C — banned per CLAUDE.md "Never use"
- Alpha Vantage as primary — 25 calls/day quota too small
- IEX Cloud — discontinued Aug 2024

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Stooq `$NYAD` will reliably trigger the R1000 breadth fallback (D-05); operationally it's the default path today | Pitfall 1 | If Stooq's parser breaks differently in the future (e.g., returns garbled CSV that passes `is None` check but fails downstream), the fallback heuristic ("> 5% missing values over 2005-present") may not trigger. Mitigation: also catch `ParserError` in the Stooq attempt and route to fallback. |
| A2 | The CONTEXT.md→ROADMAP discrepancy on `^IXIC` vs `^VIX` is resolved by D-04 (CONTEXT) being authoritative | Phase Requirements table | If ROADMAP §"Phase 3 success criteria 1" is taken literally, `make macro` would also need to fetch `^IXIC` (Nasdaq Composite). Mitigation: planner verifies with user; cheap to add — same yfinance idiom. |
| A3 | The breadth_pct denominator should be "tickers with valid sma_200" not "all universe tickers" | Pitfall 11 | If wrong, breadth_pct is biased upward during periods when many tickers have insufficient history (e.g., post-IPO clusters). Mitigation: write a unit test asserting the convention; document explicitly. |
| A4 | Phase 4 will write the RS snapshot during `make rank` (not Phase 3) | D-10, Architecture | Phase 3 ships the helper `write_rs_snapshot_atomic()`. Phase 4 (or `make rank` plumbing) calls it. If Phase 3 needs to also wire the call into a CLI command, that's an extra task. Mitigation: keep `make rank` integration deferred; Phase 3 ships only the helper + tests. |
| A5 | The grep gate file `signals/minervini.py` may not exist when Phase 3 CI runs (Phase 4 ships it) | Pitfall 6 | A naive `grep -i "ema" file_that_doesnt_exist` exits 2 and fails CI. Mitigation: redirect stderr `2>/dev/null` and use a defensive shell guard in the workflow step. |
| A6 | The 3-state regime priority order (Correction overrides Pressure overrides Uptrend) is implementable as a simple if/elif chain not a weighted threshold | Example 4 | If a future refinement uses a continuous score → state mapping, the if/elif must be replaced. For v1 the if/elif is correct and simpler. |
| A7 | yfinance `^VIX` Volume=0 is universal across history (verified 2024-01); not a quirk of one sample | Pitfall 4 | If older VIX data has Volume>0, code that filters Volume=0 would silently drop them. Mitigation: pin VixSchema to close-only; never read volume. |

## Open Questions

1. **`^IXIC` (Nasdaq Composite) — fetch or skip?**
   - What we know: CONTEXT.md D-04 says "QQQ/^VIX (yfinance)" and lists no `^IXIC`. ROADMAP success criteria 1 says "make macro refreshes SPY, ^IXIC, ^VIX". Phase 3 boundary in CONTEXT lists "QQQ", not Nasdaq Composite.
   - What's unclear: Is `^IXIC` synonymous with QQQ for this project? They're different — QQQ is the ETF (with bid/ask), `^IXIC` is the index (no volume).
   - Recommendation: Treat CONTEXT.md D-04 as authoritative — fetch SPY + QQQ + ^VIX. Surface this in the discuss-phase log; if user wants `^IXIC` in addition, it's one more line in `data/macro.py`.

2. **Should `make macro` write to `data/macro/` and to `data/macro/<date>.parquet` (snapshot pattern), or one rolling file per series (incremental)?**
   - What we know: CONTEXT.md D-06 says incremental append with backfill 2005-01-01 — implies one file per series, like Phase 2 OHLCV.
   - What's unclear: Whether to also keep weekly snapshots like the universe.
   - Recommendation: Single rolling file per series (no snapshot history). Macro data is single-source-of-truth from yfinance/FRED; if a backtest needs a point-in-time view, it can reconstruct via FRED's `realtime_start` parameter (advanced feature — defer to v2).

3. **RS snapshot trigger — Phase 3 CLI command or Phase 4 `make rank`?**
   - What we know: D-10 says "after each `make rank` run." `make rank` lands in Phase 4.
   - What's unclear: Whether Phase 3 should also expose a `screener rs-snapshot` standalone subcommand for testability.
   - Recommendation: NO new subcommand (D-14 surface is locked to 9). Phase 3 ships `write_rs_snapshot_atomic()` as a library helper; Phase 4 wires it into the `score` command (which is already in the locked surface).

4. **Golden-file regime test data — synthetic or real macro Parquet?**
   - What we know: CONTEXT.md "Claude's Discretion" allows either approach.
   - What's unclear: Whether 20 years of SPY+VIX backfill will be available at CI time (the OHLCV cache is gitignored per Phase 2 D-19).
   - Recommendation: **Synthetic.** Build minimal SPY/VIX series for each test window with deterministic distribution-day positions. Tests are fast, hermetic, and don't depend on macro Parquets being pre-fetched. A separate `@pytest.mark.integration` test exercises real data when run locally.

5. **`fredapi` rate limits — what's the exact policy?**
   - What we know: FRED is documented as "free with API key, very generous" (docs/data-architecture.md).
   - What's unclear: Exact requests/sec ceiling.
   - Recommendation: Wrap FRED calls in `tenacity` with the same `wait_exponential` as Phase 2 OHLCV. 5 retries, 2-60s window. FRED returns rate-limit errors as HTTP 429; tenacity already handles via `ConnectionError` types — verify the exception class fredapi raises and add it to `retry_if_exception_type`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pandas-ta-classic | indicators/* | ✓ | 0.4.47 | — |
| pandas | indicators/, regime/, data/ | ✓ | 2.2.x | — |
| numpy | indicators/, regime/ | ✓ | 2.x | — |
| yfinance | data/macro.py (SPY/QQQ/^VIX) | ✓ | 1.3.0 | — |
| fredapi | data/macro.py (yields) | ✓ | 0.5.2 | — |
| pandas-datareader | data/stooq.py (reuse for $NYAD attempt) | ✓ | 0.10.0 | R1000 breadth proxy (Pattern 6) — **operative primary path** |
| pandera | persistence.py schemas | ✓ | 0.31.1 | — |
| structlog | obs.py, all modules | ✓ | 25.5.x | — |
| tenacity | data/macro.py retry | ✓ | 9.1.x | — |
| FRED API key | yields fetch | env-dependent | — | Skip yields with `log.warning('skipping_yields_no_key')`; regime module gracefully treats yields as optional (yields are NOT in the D-03 score formula — they're stored for future use) |
| Network access | All macro fetches | env-dependent | — | Tests use mocked fetchers (HTTPMock or fixture-driven); CI runs without macro fetches |
| ripgrep (rg) | CI `ema` grep gate | ✗ on `ubuntu-latest` runner | — | Use `grep -ilE` (POSIX) — already noted in CONTEXT.md "EMA grep CI gate" Discretion |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- ripgrep — fall back to POSIX `grep` (canonical in CONTEXT.md "Claude's Discretion")
- Stooq access (currently broken) — fall back to R1000 breadth proxy (canonical in D-05)

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + hypothesis 6.x (Phase 1 baseline; both already in dev extras) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 1) |
| Quick run command | `uv run pytest -m "not slow and not integration" -x` |
| Full suite command | `uv run pytest --cov=src/screener/indicators --cov=src/screener/signals --cov-fail-under=80 --strict-markers` |
| Estimated runtime | ~30 s quick / ~90 s full |

Mypy gate is already strict on `src/screener/indicators` and `src/screener/regime.py` per `pyproject.toml [tool.mypy] files = [...]`. Phase 3 must keep the `indicators/` modules type-clean. `data/macro.py` is under the existing `screener.data.*` ignore_errors override.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IND-01 | `build_panel(date)` returns 10 new columns over Phase-2 panel | unit | `uv run pytest tests/test_indicators_build_panel.py::test_build_panel_returns_10_new_cols -x` | ❌ Wave 0 |
| IND-01 | `build_panel(date)` preserves (ticker, date) MultiIndex | unit | `uv run pytest tests/test_indicators_build_panel.py::test_build_panel_preserves_multiindex -x` | ❌ Wave 0 |
| IND-01 | SMA10/20/50 valid for 50-bar ticker; SMA150/200 NaN; rs_rating NaN | unit | `uv run pytest tests/test_indicators_build_panel.py::test_short_history_nan_warmup -x` | ❌ Wave 0 |
| IND-01 | `_safe_sma` returns NaN Series (not None) on short series | unit | `uv run pytest tests/test_indicators_trend.py::test_safe_sma_short_series_returns_nan_series -x` | ❌ Wave 0 |
| IND-02 | `grep -ilE "ema" signals/minervini.py indicators/trend.py` → 0 matches | CI step (shell) | `bash .github/workflows/ema-grep-gate.sh` (or inline yaml step) | ❌ Wave 0 |
| IND-02 | Adding `ema` to `indicators/trend.py` fails the gate (mutation test) | unit (shell-invoking) | `uv run pytest tests/test_ci_ema_grep_gate.py::test_ema_grep_fails_on_mutation -x` | ❌ Wave 0 |
| IND-03 | RS rating ∈ [1, 99] cross-sectionally per date | unit | `uv run pytest tests/test_indicators_rs.py::test_rs_rating_in_range -x` | ❌ Wave 0 |
| IND-03 | RS preserves NaN for tickers with < 252d history | unit | `uv run pytest tests/test_indicators_rs.py::test_rs_nan_for_short_history -x` | ❌ Wave 0 |
| IND-03 | `groupby('ticker').shift()` correctness — different ticker series don't bleed | unit | `uv run pytest tests/test_indicators_rs.py::test_rs_per_ticker_shift_isolation -x` | ❌ Wave 0 |
| IND-04 | `adr_pct` for high=105/low=95 = 10.526 | unit | `uv run pytest tests/test_indicators_volatility.py::test_adr_pct_canonical_value -x` | ❌ Wave 0 |
| IND-05 | `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` passes against new modules | unit | `uv run pytest tests/test_architecture.py -x` | ✅ exists |
| DAT-04 | `make macro` fetches SPY/QQQ/VIX/yields and writes Parquets | integration | `uv run pytest tests/test_data_macro.py::test_refresh_all_writes_files -m integration` | ❌ Wave 0 |
| DAT-04 | yfinance fetcher applies the 4 D-08 invariants (reuse Phase 2 idiom) | unit | `uv run pytest tests/test_data_macro.py::test_yf_invariants_applied -x` | ❌ Wave 0 |
| DAT-04 | $NYAD fallback triggered on Stooq failure → r1000 proxy | unit | `uv run pytest tests/test_data_macro.py::test_nyad_fallback_to_r1000_proxy -x` | ❌ Wave 0 |
| DAT-04 | $NYAD fallback heuristic (> 5% missing) | unit | `uv run pytest tests/test_data_macro.py::test_nyad_fallback_on_thin_stooq -x` | ❌ Wave 0 |
| DAT-04 | FRED fetcher writes 3-column yields.parquet | unit | `uv run pytest tests/test_data_macro.py::test_yields_parquet_columns -x` | ❌ Wave 0 |
| REG-01 | `compute_for_date` returns 6 columns: spy_above_200d, breadth_pct, distribution_days, vix_level, regime_state, regime_score | unit | `uv run pytest tests/test_regime.py::test_compute_for_date_columns -x` | ❌ Wave 0 |
| REG-01 | distribution_days correctly counts strict-IBD days in rolling 25 | unit | `uv run pytest tests/test_regime.py::test_distribution_day_idiom -x` | ❌ Wave 0 |
| REG-02 | regime_score is in [0, 1] for synthetic random inputs (1000 cases) | property | `uv run pytest tests/test_regime.py::test_regime_score_range_property -x` | ❌ Wave 0 |
| REG-02 | regime_state ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction} | unit | `uv run pytest tests/test_regime.py::test_regime_state_enum -x` | ❌ Wave 0 |
| REG-02 | Correction overrides Uptrend Under Pressure (D-01 priority) | unit | `uv run pytest tests/test_regime.py::test_correction_overrides_pressure -x` | ❌ Wave 0 |
| REG-03 | regime_score column is in `compute_for_date` output (sizing seam) | unit | `uv run pytest tests/test_regime.py::test_regime_score_seam_exists -x` | ❌ Wave 0 |
| REG-04 | 2008-Q4 synthetic series classifies ≥ 1 date as Correction | golden-file | `uv run pytest tests/test_regime.py::test_2008q4_correction -x` | ❌ Wave 0 |
| REG-04 | 2020-Q1 synthetic series classifies ≥ 1 date as Correction | golden-file | `uv run pytest tests/test_regime.py::test_2020q1_correction -x` | ❌ Wave 0 |
| REG-04 | 2022-H1 synthetic series classifies ≥ 1 date as Correction | golden-file | `uv run pytest tests/test_regime.py::test_2022h1_correction -x` | ❌ Wave 0 |
| Persistence | `write_rs_snapshot_atomic` reuses `_write_parquet_atomic` (atomic) | unit | `uv run pytest tests/test_persistence.py::test_rs_snapshot_atomic_write -x` | ❌ Wave 0 |
| Persistence | RsSnapshotSchema rejects non-int64 rs_rating | unit | `uv run pytest tests/test_persistence.py::test_rs_snapshot_schema_rejects_bad_rating -x` | ❌ Wave 0 |
| Persistence | `read_macro_spy` lazy-validates against MacroOhlcvSchema | unit | `uv run pytest tests/test_persistence.py::test_read_macro_spy_validates -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest -m "not slow and not integration" -x`
- **Per wave merge:** `uv run pytest --cov=src/screener/indicators --cov=src/screener/signals --cov-fail-under=80 --strict-markers`
- **Phase gate:** Full suite green; `data/macro/*.parquet` present after a manual `make macro` run; CI EMA grep step green

### Wave 0 Gaps

- [ ] `tests/test_indicators_build_panel.py` — covers IND-01
- [ ] `tests/test_indicators_trend.py` — covers IND-01 SMA + safe wrapper
- [ ] `tests/test_indicators_volatility.py` — covers IND-04 (ADR%) + ATR shape
- [ ] `tests/test_indicators_volume.py` — OBV + dryup_ratio shape
- [ ] `tests/test_indicators_rs.py` — covers IND-03
- [ ] `tests/test_data_macro.py` — covers DAT-04 (with `@pytest.mark.integration` for live fetches)
- [ ] `tests/test_regime.py` — covers REG-01..04 (synthetic golden-files)
- [ ] `tests/test_ci_ema_grep_gate.py` — covers IND-02 (mutation-tests the gate by writing a temp ema-containing file then asserting grep nonzero exit)
- [ ] `tests/conftest.py` — extend with synthetic SPY/VIX fixtures for 2008-Q4, 2020-Q1, 2022-H1; synthetic short-history ticker fixture (50 bars, exercises SMA200 NaN path)
- [ ] `.github/workflows/ci.yml` — add ema-grep step
- [ ] `tests/test_persistence.py` — extend with RsSnapshotSchema, MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema tests
- [ ] No new framework install required — pytest, hypothesis, pandera all already in dev extras

## Security Domain

> Security enforcement is not explicitly disabled in `.planning/config.json` for this project; including this section per default-on policy.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user-facing service in v1 |
| V3 Session Management | no | No sessions; single-user CLI |
| V4 Access Control | no | Local CLI; no multi-user surface |
| V5 Input Validation | yes | All external data validated by pandera schemas (Phase 2 D-15 / D-16); `_assert_safe_ticker()` in persistence.py refuses path-traversal ticker strings |
| V6 Cryptography | no | No encryption requirements (no PII); `FRED_API_KEY` is a low-trust read-only API key |
| V7 Error Handling | yes | structlog never logs API keys or `.env` contents; existing pattern in Phase 2 |
| V8 Data Protection | yes | `.env` is gitignored (Phase 1); `FRED_API_KEY` never committed; no PII at rest |
| V11 Business Logic | yes | Distribution-day rule is strict IBD (D-02); regime priority Correction > Pressure (D-01) |

### Known Threat Patterns for {pandas + yfinance + FRED + Parquet on local filesystem}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed Parquet → pandera schema bypass | Tampering | Eager `validate_at_write` (lazy=False) at write boundary; lazy at read — Phase 2 D-16. Same policy in Phase 3 macro reads. |
| Path traversal via ticker string | Tampering | `_assert_safe_ticker()` already in persistence.py (line 182). Reuse for any new per-ticker writers. |
| Stooq HTML response → ParserError → unhandled exception → run abort | DoS | Fallback to R1000 breadth proxy (D-05) catches `ParserError`, `RemoteDataError`, `OSError` and routes to `_compute_breadth_fallback`. |
| FRED API key leakage in error log | Information Disclosure | `fredapi` raises exceptions that may include the key in URL — wrap `Fred(...).get_series(...)` calls in try/except and log only `error_type` + sanitized message. structlog `processors.format_exc_info` does NOT include kwargs from upper frames — safe. |
| Macro Parquet write race during cron | Tampering | `_write_parquet_atomic` (Phase 2 D-11) — reuse 1:1 |

### Recommendations

1. Add a unit test that asserts `FRED_API_KEY` does not appear in any structlog event from `data/macro.py` (`test_no_secret_in_logs`).
2. Reuse `_assert_safe_ticker()` for any per-ticker macro writer (probably none — macro writes one file per series, not per ticker — but if `data/rs_snapshots/<date>.parquet` writers ever take ticker as a path component, the helper is there).
3. The `r1000_proxy` fallback (Pattern 6) reads `read_panel(snapshot)` — which is already validated. No additional input-validation layer needed.

## Sources

### Primary (HIGH confidence — verified live)

- **[VERIFIED: live 2026-05-10]** `pandas_ta_classic` 0.4.47 — `ta.sma`/`ta.atr`/`ta.obv` signatures, column names (`SMA_50`, `ATRr_14`, `OBV`), Wilder's RMA default for ATR, **None-on-short-series behavior** (Pitfall 2)
- **[VERIFIED: live 2026-05-10]** `yfinance` 1.3.0 — `yf.download('SPY', auto_adjust=True, progress=False, threads=False, multi_level_index=False)` returns 5-col DataFrame; ^VIX returns Volume=0 always
- **[VERIFIED: live 2026-05-10]** `fredapi` 0.5.2 — `Fred(api_key=str)` and `Fred.get_series(series_id, observation_start, observation_end, **kwargs)` signatures
- **[VERIFIED: live 2026-05-10]** `pandas-datareader` 0.10.0 — Stooq endpoint currently returns HTML; ParserError on $NYAD, ^SPX, ^VIX, AAPL.US, NYAD, NYAD.US (all variants tested)
- **[VERIFIED: live 2026-05-10]** Cross-sectional rank idiom: `panel.groupby(level='date').rank(pct=True)` preserves NaN for excluded tickers
- **[VERIFIED: live 2026-05-10]** ADR% formula `100 * ((high/low).rolling(20).mean() - 1)` — produces 10.526 for high=105/low=95
- **[VERIFIED: live 2026-05-10]** Distribution-day idiom `(close < prev*0.998) & (volume > prev_volume)` then `.rolling(25).sum()`
- **[VERIFIED: live 2026-05-10]** Vectorized regime_score formula produces values in [0, 1] across random inputs
- **[VERIFIED: live]** `src/screener/persistence.py` — `OhlcvPanelSchema`, `_write_parquet_atomic`, `validate_at_write`, `validate_at_read`, `_assert_safe_ticker`
- **[VERIFIED: live]** `src/screener/data/stooq.py` — column normalization + 4-invariant gate + `StaleOrEmptyError`
- **[VERIFIED: live]** `src/screener/data/ohlcv.py` — tenacity wrapper + 4-invariant gate + `multi_level_index=False` + lowercase + `index.name = 'date'`
- **[VERIFIED: live]** `tests/test_architecture.py` — ALLOWED dict for `regime` includes `data, indicators, persistence, config, obs`; for `indicators` includes `persistence, config, obs`. Phase 3's regime → data + indicators + persistence is permitted; indicators → persistence is permitted; data → persistence + config + obs is permitted.

### Secondary (MEDIUM confidence — cited)

- **[CITED: docs/methodology.md §6]** ATR uses Wilder's smoothing — matches pandas-ta-classic default `mamode='rma'`
- **[CITED: docs/methodology.md §4]** RS percentile transformation `(rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(int)`
- **[CITED: docs/methodology.md §5]** Regime components: SPY 200d trend, breadth, distribution days, VIX
- **[CITED: docs/data-architecture.md §2]** FRED is "free with API key, very generous"; Stooq is "free, EOD CSVs, no key"
- **[CITED: CLAUDE.md §"Signal Formulas — Quick-Reference"]** SMA-not-EMA rule, IBD RS formula, ADR% formula
- **[CITED: pandas-ta-classic source]** ATR `mamode` parameter accepts 'ema'/'sma'/'wma'/'rma'; default is 'rma' (Wilder's)

### Tertiary (LOW confidence — assumed)

- **[ASSUMED]** ripgrep is NOT preinstalled on `ubuntu-latest` GitHub Actions runner — checked GitHub docs (no clear answer in main page; docs say "see runner-images repo for tool list"; the runner-images Ubuntu24.04 README does not list ripgrep). Mitigation: use `grep -i` per CONTEXT.md fallback. (LOW because not definitively verified; safe because the mitigation works either way.)
- **[ASSUMED]** FRED publishes T10Y2Y as a precomputed series (not just DGS10 - DGS2). Cross-checked with FRED public series catalog naming; T10Y2Y is canonical. Mitigation: if not present, compute `dgs10 - dgs2` at the read boundary.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library version verified live against the installed venv; pyproject.toml pins them
- Architecture patterns: HIGH — every code idiom in Patterns 1-7 verified live (rank idiom, ADR%, dist-day rolling, regime_score, safe wrapper, breadth fallback shape)
- Pitfalls: HIGH (1, 2, 4, 7, 8, 9, 11), MEDIUM (3, 5, 6, 10) — Pitfall 1 (Stooq broken) and Pitfall 2 (None-on-short) are both reproduced live; Pitfalls 3/5/10 are inferred from primitive behavior
- Validation architecture: HIGH — extends Phase 2's pattern verbatim; only NEW idiom is the `_safe_*` wrapper test
- Macro source matrix: HIGH for yfinance + FRED, MEDIUM for Stooq fallback (the fallback shape is verified, but the heuristic threshold "5% missing values" is heuristic)

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (30 days for stable Python libs; revisit if pandas-datareader 0.11 ships or pandas-ta-classic 0.5 lands)
