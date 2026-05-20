# Phase 3: Indicator Panel & Regime - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers three interconnected pieces built on top of the Phase 2 data layer:

1. **Indicator panel** — `indicators.build_panel(snapshot_date)` reads the multi-ticker OHLCV panel from `persistence.read_panel()` and returns a DataFrame with 10 new computed columns: SMA(10/20/50/150/200), ATR(14), ADR%(20), OBV, dryup-ratio, and RS-rating (integer 1–99). Pure functions only; no I/O inside `indicators/`.

2. **Macro data layer** — `make macro` refreshes six macro series into `data/macro/*.parquet`: SPY (yfinance), QQQ/^VIX (yfinance), NYSE A/D line (Stooq `$NYAD` with R1000-breadth fallback), and FRED Treasury yields (DGS2, DGS10, T10Y2Y). Uses the existing `data/` I/O pattern and Stooq adapter from Phase 2.

3. **Regime module** — `regime.compute(date)` reads `data/macro/*.parquet` and the indicator panel to emit a DataFrame row per date with: `spy_above_200d` (bool), `breadth_pct` (float), `distribution_days` (int), `vix_level` (float), `regime_state` (str ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction}), `regime_score` (float ∈ [0, 1]).

Phase 3 also writes **daily RS snapshots** to `data/rs_snapshots/YYYY-MM-DD.parquet` for no-look-ahead reproducibility in Phase 5's backtest harness.

Requirements covered: **DAT-04** (macro refresh), **IND-01** (build_panel columns), **IND-02** (SMA-not-EMA CI gate), **IND-03** (IBD RS formula), **IND-04** (ADR% formula), **IND-05** (pure functions), **REG-01** (regime inputs), **REG-02** (discrete state + continuous score), **REG-03** (score × risk sizing seam), **REG-04** (golden-file tests).

</domain>

<decisions>
## Implementation Decisions

### Regime classification thresholds (REG-01, REG-02)

- **D-01: IBD Market Pulse-inspired three-state thresholds:**
  - **Confirmed Uptrend:** SPY above 200d SMA AND breadth_pct ≥ 60% AND distribution_days ≤ 4 AND VIX < 20
  - **Uptrend Under Pressure:** any single condition fails, OR distribution_days ∈ [5, 8]
  - **Correction:** SPY below 200d SMA OR distribution_days ≥ 9 OR VIX ≥ 30
  - Priority: Correction overrides Uptrend Under Pressure — if any Correction condition fires, the state is Correction regardless of other inputs.

- **D-02: Distribution day counting — SPY-only, strict IBD definition.** A distribution day is a session where SPY close < prev_close by > 0.2% AND SPY volume > prev_volume. Count within a rolling 25-session window. Uses only daily SPY data from `data/macro/spy.parquet` — no NYSE total-volume data required.

### regime_score formula (REG-02, REG-03)

- **D-03: Weighted linear blend with weights SPY 30% / Breadth 40% / Dist-days 20% / VIX 10%:**
  ```
  spy_component    = 1.0 if spy_above_200d else 0.0
  breadth_norm     = clip(breadth_pct / 100, 0, 1)
  dist_norm        = clip(1 - (distribution_days / 9), 0, 1)   # 0 dist = 1.0, 9+ dist = 0.0
  vix_norm         = clip(1 - ((vix_level - 15) / 25), 0, 1)  # VIX ≤ 15 = 1.0, VIX ≥ 40 = 0.0

  regime_score = 0.30 * spy_component
               + 0.40 * breadth_norm
               + 0.20 * dist_norm
               + 0.10 * vix_norm
  ```
  Result is naturally in [0, 1]. Phase 7 sizing multiplies base risk by `regime_score` (REG-03 seam).

### Macro data sources (DAT-04)

- **D-04: Source mapping for `data/macro/*.parquet`:**
  - `data/macro/spy.parquet` — yfinance (`SPY`), daily OHLCV
  - `data/macro/qqq.parquet` — yfinance (`QQQ`), daily OHLCV
  - `data/macro/vix.parquet` — yfinance (`^VIX`), daily close
  - `data/macro/nyad.parquet` — Stooq (`$NYAD`) with R1000-breadth fallback (see D-05)
  - `data/macro/yields.parquet` — FRED series DGS2, DGS10, T10Y2Y via `fredapi`; `FRED_API_KEY` already in Settings
  - **Note (^IXIC deferred):** ROADMAP SC1 originally listed `^IXIC`; v1 uses QQQ as the operative Nasdaq proxy because (a) yfinance ETF data is more consistent than index data, (b) regime classification only consumes SPY anyway (D-01 reads `spy_above_200d`, not Nasdaq), and (c) QQQ is sufficient for any future Phase 6/7 sector-strength references. `^IXIC` can be added in one line of `data/macro.py` if needed. ROADMAP §"Phase 3" Success Criteria 1 has been amended to list QQQ instead of `^IXIC` so both source artifacts now agree.

- **D-05: NYSE A/D line — Stooq `$NYAD` primary, R1000-breadth fallback.** Attempt `$NYAD` via the existing Phase 2 Stooq adapter (`data/stooq.py`). If Stooq returns empty or the series has more than 5% missing values over the 2005–present window, fall back to computing A/D from the R1000 panel: `advances - declines` where advances = tickers with `close > prev_close`. Log the data source used (`nyad_source: stooq | r1000_proxy`) as a structured event. The fallback result is stored in the same `data/macro/nyad.parquet` file — downstream regime code is agnostic to which source was used.

- **D-06: Macro refresh is idempotent and incremental.** Same append-from-last-cached-date pattern as Phase 2 OHLCV (D-07). `make macro` checks existing `data/macro/<series>.parquet`, fetches only from `max(date)+1`, appends atomically. On first run: backfill from `2005-01-01` to match OHLCV history.

### Indicator panel structure (IND-01, IND-05)

- **D-07: `build_panel(snapshot_date)` consumes `persistence.read_panel(snapshot_date)` and returns the same (ticker, date) MultiIndex DataFrame with 10 additional columns.** No new I/O — all reads go through `persistence`. No state, no side effects inside `indicators/`. The panel is wide (long format, one row per ticker × date), same shape as `OhlcvPanelSchema`.

- **D-08: Tickers with insufficient history get NaN for long-lookback columns.** pandas rolling naturally produces NaN for the warmup period. A ticker with 100 days of data gets SMA10/20/50 filled, SMA150/200 as NaN, RS-rating as NaN (needs 252d). Downstream signals treat NaN trend-template conditions as `False` — the ticker does not pass the gate until sufficient history accumulates. No minimum-history drop, no backfilling with shorter windows.

- **D-09: dryup-ratio formula is `volume / SMA(volume, 50)`.** Values below 0.5 indicate significant volume contraction. The 50d window aligns with the breakout-volume baseline in Phase 6 (VCP criterion: breakout volume ≥ 1.5× SMA(volume, 50)). Column name: `dryup_ratio`.

### RS snapshot persistence (IND-03, look-ahead prevention)

- **D-10: Phase 3 writes daily RS snapshots to `data/rs_snapshots/YYYY-MM-DD.parquet` after each `make rank` run.** Each snapshot contains one row per ticker with `rs_raw` and `rs_rating` (1–99 integer) computed cross-sectionally on that date's universe. Phase 5's backtest harness reads these point-in-time snapshots instead of recomputing RS with future data — prevents the look-ahead bias described in CLAUDE.md §13.6 pitfall.
- **D-11: `data/rs_snapshots/` is gitignored** (same policy as OHLCV cache — too large, re-creatable from `make rank` history). `persistence.py` gets `write_rs_snapshot_atomic()` and `read_rs_snapshot()` helpers following the atomic-write pattern (Phase 2 D-11).

### Settings additions

- **D-12: Phase 3 extends `Settings` additively with:**
  - `MACRO_CACHE_DIR: Path = Path("data/macro")`
  - `RS_SNAPSHOT_DIR: Path = Path("data/rs_snapshots")`
  - `MACRO_BACKFILL_START: str = "2005-01-01"` (matches OHLCV backfill, covers REG-04 golden-file test dates)
  - `REGIME_BREADTH_THRESHOLD: float = 0.60` (Confirmed Uptrend breadth cutoff, D-01)
  - `REGIME_DIST_DAYS_PRESSURE: int = 5` (lower bound for Uptrend Under Pressure, D-01)
  - `REGIME_DIST_DAYS_CORRECTION: int = 9` (Correction trigger, D-01)
  - `REGIME_VIX_CORRECTION: float = 30.0` (Correction trigger, D-01)
  - `REGIME_VIX_CONFIRMED: float = 20.0` (Confirmed Uptrend ceiling, D-01)

### Claude's Discretion

The planner finalizes these consistent with the locked decisions above:

- **Indicator module layout.** Standard: `src/screener/indicators/trend.py` (SMA/ATR), `relative_strength.py` (RS), `volatility.py` (ATR, ADR%), `volume.py` (OBV, dryup). `indicators/__init__.py` exports `build_panel()` that calls each pure function in sequence.
- **Macro CLI subcommand.** `screener refresh-macro` (stub exists in cli.py from Phase 1). `make macro` calls it. Same `--force` pattern as `refresh-universe`.
- **Regime module API.** `regime.compute_for_date(date: pd.Timestamp, panel: pd.DataFrame) -> pd.Series` — takes the pre-built indicator panel as input, returns a single-row Series with the regime columns. `regime.build_history(start, end) -> pd.DataFrame` for backtesting. Both in `src/screener/regime.py`.
- **EMA grep CI gate (IND-02).** The gate exists in Phase 3's success criteria: `rg "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` must return zero matches. The `.github/workflows/ci.yml` step runs this grep. If `rg` is unavailable in CI, fall back to `grep -i "ema"`.
- **Golden-file test data.** `tests/test_regime.py` with the three date-range fixtures (2008-Q4: 2008-10-01 to 2009-03-01; 2020-Q1: 2020-02-15 to 2020-04-15; 2022-H1: 2022-01-01 to 2022-07-01). Each range must include at least one date classified as `Correction`. Tests use the real `data/macro/*.parquet` cache if available, or a reduced synthetic fixture (SPY dummy price series that crosses 200d SMA at known dates).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 3: Indicator Panel & Regime" — goal, success criteria 1–5, phase dependencies
- `.planning/REQUIREMENTS.md` §IND-01..IND-05 — indicator requirements with formulas
- `.planning/REQUIREMENTS.md` §REG-01..REG-04 — regime requirements with golden-file test obligations
- `.planning/REQUIREMENTS.md` §DAT-04 — macro data refresh requirement

### Signal formulas (CLAUDE.md — MUST read before touching indicators/ or regime.py)
- `CLAUDE.md` §"Signal Formulas" — IBD RS formula (`RS_raw = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)`), ADR% formula (`100 * ((high/low).rolling(20).mean() - 1)`), SMA-not-EMA rule
- `CLAUDE.md` §"Critical Pitfalls" pitfall #1 — EMA substitution for SMA produces meaningfully different results; always SMA

### Methodology context
- `CLAUDE.md` §"Signal Formulas — Quick-Reference" — RS formula and Qullamaggie ADR% formula
- `docs/methodology.md` — Full RS formula derivation, regime components, sector RS context
- `docs/data-architecture.md` — Data source matrix, macro data sources, caching approach

### Architecture and conventions (from Phase 2 carry-forward)
- `.planning/phases/02-data-foundation/02-CONTEXT.md` — D-06 (per-ticker layout), D-11 (atomic write pattern), D-14 (Stooq adapter), D-15 (pandera schemas), D-16 (validation policy: eager at write, lazy at read), D-20 (Settings additive extension pattern)
- `src/screener/persistence.py` — `read_panel()`, `read_splits()`, atomic-write helpers — Phase 3 adds `write_rs_snapshot_atomic()` and `read_rs_snapshot()` following the same pattern
- `src/screener/data/stooq.py` — existing Stooq adapter; Phase 3 reuses it for `$NYAD` and macro index fetches
- `src/screener/config.py` — additive Settings extension pattern; `FRED_API_KEY` already present

### Phase 1 architecture constraints
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` D-16 — architecture test enforces that `indicators/` and `regime.py` do NOT import from network deps; all I/O flows through `persistence` and `data/`
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` D-13 — `persistence.py` is the schema seam; new schemas (`MacroSchema`, `RsSnapshotSchema`) go here

### Stack
- `docs/tech-stack.md` — pandas-ta-classic 0.4.47 (pure Python, no C deps), fredapi 0.5.2
- `CLAUDE.md` §"Library Quick-Reference" — confirms pandas-ta-classic for SMA/ATR/OBV; `Never use: original pandas-ta`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/screener/data/stooq.py` — Stooq adapter with column normalization and post-fetch invariants; Phase 3 calls it for `$NYAD` and SPY/QQQ/VIX macro fetches without modification
- `src/screener/persistence.py` — `_write_parquet_atomic()`, `validate_at_write()`, `validate_at_read()` are the exact primitives Phase 3 uses for macro and RS snapshot writes
- `src/screener/config.py` — `get_settings()` cached singleton; additive Settings extension confirmed safe (Phase 2 precedent)
- `src/screener/obs.py` — structlog already configured; Phase 3 emits `macro_fetch_start`, `macro_fetch_success`, `nyad_source`, `regime_computed`, `rs_snapshot_written` events

### Established Patterns
- **Pure functions in `indicators/`:** No I/O, no global state; Panel-in, Panel-out with identical MultiIndex. This is an architecture-tested invariant — any violation causes CI to fail.
- **Atomic write contract:** `tempfile.NamedTemporaryFile` + `os.replace()` (Phase 2 D-11). Phase 3 extends to `data/macro/*.parquet` and `data/rs_snapshots/*.parquet`.
- **Additive Settings extension:** New fields added to `Settings` class with typed defaults; mirrored in `.env.example`.
- **Incremental append:** Check `max(date)` in existing Parquet, fetch only newer bars, append atomically. Applied to all macro series.

### Integration Points
- **`persistence.read_panel(snapshot_date)` → `indicators.build_panel()`:** Phase 3's indicator panel is the entry point that Phase 4's Trend Template consumes directly.
- **`regime.compute_for_date()` → Phase 7 sizing:** `regime_score` is the multiplier on base risk in `sizing.py`; the seam is reserved but not wired until Phase 7.
- **`data/rs_snapshots/`** → Phase 5 backtest harness reads point-in-time RS for walk-forward windows. The `read_rs_snapshot()` function in `persistence.py` is the interface.
- **EMA grep CI gate:** `ci.yml` must add a step to grep `src/screener/indicators/trend.py` and `src/screener/signals/minervini.py` for any `ema` reference. Failing the grep = failing CI.

</code_context>

<specifics>
## Specific Ideas

- **Regime score normalization thresholds for `dist_norm`:** distribute days 0–9 map linearly to 1.0–0.0. At 9+ dist days the formula clips to 0. The specific formula `clip(1 - (distribution_days / 9), 0, 1)` is the canonical implementation.
- **VIX normalization anchor points:** VIX ≤ 15 → 1.0 (calm); VIX ≥ 40 → 0.0 (panic). Linear interpolation between. Formula: `clip(1 - ((vix_level - 15) / 25), 0, 1)`.
- **Distribution day threshold is strict IBD:** SPY close must be DOWN more than 0.2% (not flat, not up). Volume must be HIGHER than the prior session. Standard 25-session rolling window.
- **Stooq A/D line ticker:** `$NYAD` — confirmed Stooq symbol format for NYSE Advance-Decline. The existing `data/stooq.py` PascalCase → lowercase column rename handles Stooq's output format.
- **FRED yield series:** `DGS2` (2-Year Treasury), `DGS10` (10-Year Treasury), `T10Y2Y` (10Y-2Y spread). All three in a single `yields.parquet` file with columns `dgs2`, `dgs10`, `t10y2y`. Daily frequency; FRED has weekday-only data (no weekends) — forward-fill over weekends when joining with OHLCV panel.
- **RS percentile ranking excludes NaN tickers.** When building the cross-sectional percentile rank, only tickers with valid `rs_raw` (252d of history) participate in the ranking. Tickers with NaN `rs_raw` get NaN `rs_rating`. This prevents a new-IPO with 50 days of history from dragging down the ranking baseline.

</specifics>

<deferred>
## Deferred Ideas

- **Sector-level RS (relative strength of sector vs. broad market)** — Phase 6 (CANSLIM L). The sector column exists in the universe Parquet from Phase 2 D-04. Phase 3 computes only ticker-level RS. Sector RS is a Phase 6 decision.
- **Halt-flag and suspension detection** — Phase 6 catalysts (deferred from Phase 2). Not relevant to Phase 3.
- **Fundamentals lag enforcement (`knowable_from` date)** — Phase 6 (DAT-05). Phase 3 doesn't touch fundamentals.
- **Finnhub earnings calendar** — Phase 6 (CAT-01). Phase 3 has no earnings data dependency.
- **regime_score → sizing wiring** — Phase 7 (`sizing.py`). Phase 3 computes and exposes `regime_score` as a column; Phase 7 wires it into the sizing formula.

</deferred>

---

*Phase: 3-Indicator Panel & Regime*
*Context gathered: 2026-05-10*
