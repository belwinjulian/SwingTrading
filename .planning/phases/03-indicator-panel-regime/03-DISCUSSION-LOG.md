# Phase 3: Indicator Panel & Regime - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 3-indicator-panel-regime
**Areas discussed:** Regime rules + score formula, NYSE A/D line source, dryup-ratio formula, RS snapshot persistence

---

## Regime Rules + Score Formula

### State thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| IBD Market Pulse inspired | Confirmed Uptrend: SPY above 200d AND breadth ≥ 60% AND dist_days ≤ 4 AND VIX < 20. Uptrend Under Pressure: any one condition fails or dist_days 5–8. Correction: SPY below 200d OR dist_days ≥ 9 OR VIX ≥ 30. | ✓ |
| Strict two-trigger rule | Correction only when 2+ of {SPY below 200d, breadth < 40%, dist_days ≥ 9, VIX ≥ 30} fire simultaneously. | |
| Let me specify | User-defined thresholds. | |

**User's choice:** IBD Market Pulse inspired
**Notes:** None beyond selection.

---

### regime_score formula

| Option | Description | Selected |
|--------|-------------|----------|
| Weighted linear blend | Weighted sum of normalized inputs: SPY trend, breadth, dist-days inverted, VIX inverted. | ✓ |
| Lookup table from discrete state | Confirmed Uptrend = 1.0, Uptrend Under Pressure = 0.5, Correction = 0.0. Coarse — loses within-state gradients. | |
| Let me specify | User-defined formula. | |

**User's choice:** Weighted linear blend
**Notes:** Chose this for transparency and auditability.

---

### Score weights

| Option | Description | Selected |
|--------|-------------|----------|
| SPY 30% / Breadth 40% / Dist-days 20% / VIX 10% | Breadth dominates as the primary market participation signal. | ✓ |
| Equal weights 25/25/25/25 | Simpler but treats VIX and breadth as equally important. | |
| Let me set the weights | User-defined weights. | |

**User's choice:** SPY 30% / Breadth 40% / Dist-days 20% / VIX 10%

---

### Distribution day definition

| Option | Description | Selected |
|--------|-------------|----------|
| SPY-only, strict IBD | SPY down >0.2% on higher volume than prior session, rolling 25 sessions. | ✓ |
| SPY + QQQ combined | Distribution if either index triggers. Catches tech-led selloffs. | |
| Let me specify | User-defined definition. | |

**User's choice:** SPY-only, strict IBD
**Notes:** Keeps it simple and reproducible; no NYSE total-volume data required.

---

## NYSE A/D Line Source

### A/D line primary source

| Option | Description | Selected |
|--------|-------------|----------|
| Stooq $NYAD | Direct Stooq ticker. Coverage unverified for full history. | |
| Proxy: breadth from R1000 | Compute from OHLCV panel (advances - declines). No new source needed, R1000-specific. | |
| Stooq $NYAD with R1000-breadth fallback | Try $NYAD first; fall back to R1000 breadth proxy if Stooq data is sparse. | ✓ |

**User's choice:** Stooq $NYAD with R1000-breadth fallback
**Notes:** Reuses existing Phase 2 Stooq adapter. Source logged as structured event.

---

### Other macro series sources

| Option | Description | Selected |
|--------|-------------|----------|
| yfinance for SPY/QQQ/VIX, FRED for yields | FRED API key already in Settings. Authoritative yield data. | ✓ |
| Stooq for everything | No FRED API key needed. Bond proxy series less reliable. | |
| Let me specify per-ticker | Per-series source assignment. | |

**User's choice:** yfinance for SPY/QQQ/VIX, FRED for yields (DGS2, DGS10, T10Y2Y)

---

## dryup-ratio Formula

| Option | Description | Selected |
|--------|-------------|----------|
| volume / SMA(volume, 50) | Values < 0.5 = dryup. 50d aligns with Phase 6 breakout-volume baseline (1.5× SMA50). | ✓ |
| volume / SMA(volume, 20) | Shorter window, more sensitive but noisier. | |
| Let me specify | User-defined formula. | |

**User's choice:** volume / SMA(volume, 50)
**Notes:** Aligns with Phase 6 VCP breakout-volume criterion — consistent 50d volume baseline across both phases.

---

## RS Snapshot Persistence

### Daily snapshot writes

| Option | Description | Selected |
|--------|-------------|----------|
| Write data/rs_snapshots/YYYY-MM-DD.parquet each run | Phase 3 owns RS; point-in-time snapshots prevent look-ahead in Phase 5 backtest. | ✓ |
| Defer to Phase 5 | Phase 3 computes on-the-fly; Phase 5 builds history. Reintroduces look-ahead risk. | |
| Embed RS in OHLCV parquet | Violates data/ vs indicators/ boundary (Phase 1 D-16). | |

**User's choice:** Yes — write data/rs_snapshots/YYYY-MM-DD.parquet each run

---

### Insufficient history handling

| Option | Description | Selected |
|--------|-------------|----------|
| NaN — compute what's available | Long-lookback columns are NaN during warmup. Downstream treats NaN as condition-not-met. | ✓ |
| Drop tickers below minimum | Exclude tickers with < 252 days. Silently drops recent IPOs/re-listings. | |
| Backfill with shorter windows | Use shorter lookbacks when full history unavailable. Breaks cross-sectional ranking integrity. | |

**User's choice:** NaN — compute what's available, fill with NaN for missing lookbacks

---

## Claude's Discretion

- **Indicator module layout:** trend.py / relative_strength.py / volatility.py / volume.py under `indicators/`
- **Macro CLI subcommand:** `screener refresh-macro` using existing Phase 1 stub
- **Regime module API shape:** `compute_for_date()` for daily use, `build_history()` for backtesting
- **EMA grep CI gate implementation:** `rg "ema" ...` in `ci.yml`, fallback to `grep -i "ema"` if `rg` unavailable
- **Golden-file test date ranges:** 2008-10-01→2009-03-01, 2020-02-15→2020-04-15, 2022-01-01→2022-07-01
- **RS percentile ranking excludes NaN tickers** (new-IPOs with < 252d don't distort the cross-sectional ranking)

## Deferred Ideas

- Sector-level RS → Phase 6 (CANSLIM L)
- Halt-flag detection → Phase 6 catalysts
- Fundamentals lag enforcement → Phase 6 (DAT-05)
- regime_score → sizing wiring → Phase 7 (sizing.py)
