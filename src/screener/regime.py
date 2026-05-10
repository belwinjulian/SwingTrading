"""regime — universe-wide market-regime gate (one row per date).

Emits a discrete state in {Confirmed Uptrend, Uptrend Under Pressure,
Correction} plus a continuous regime_score in [0, 1]. Imports `data/`,
`indicators/`, and `persistence/`; consumed by `sizing` (Phase 7) and
`publishers/` (Phase 4).

Rules (CONTEXT.md D-01, D-02, D-03):
- Confirmed Uptrend: SPY > 200d SMA AND breadth_pct >= 60 AND dist <= 4 AND VIX < 20
- Uptrend Under Pressure: any single condition fails, OR dist in [5, 8]
- Correction (priority — overrides everything):
    SPY < 200d SMA OR dist >= 9 OR VIX >= 30

Distribution day (strict IBD): SPY close < prev_close by > 0.2% AND SPY volume
> prev_volume; counted in a rolling 25-session window.

regime_score (vectorized, naturally in [0, 1]):
    spy=30% + breadth=40% + dist=20% + vix=10% weighted blend

The breadth_pct denominator is "tickers with valid sma_200" not "all universe
tickers" (RESEARCH Pitfall 11) — prevents biased breadth during periods when
many tickers lack 200d history.
"""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
import structlog

from screener.config import get_settings
from screener.indicators import build_panel
from screener.persistence import read_macro_spy, read_macro_vix

log = structlog.get_logger(__name__)

RegimeState = Literal["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"]


# ---------------------------------------------------------------------------
# Distribution-day counter (D-02)
# ---------------------------------------------------------------------------


def _compute_distribution_days(spy: pd.DataFrame, window: int = 25) -> pd.Series:
    """Strict IBD: SPY close down > 0.2% AND volume > prev_volume; rolling 25.
    Returns int Series indexed by date.
    """
    prev_close = spy["close"].shift(1)
    prev_vol = spy["volume"].shift(1)
    is_dist_day = (
        (spy["close"] / prev_close - 1.0 < -0.002)
        & (spy["volume"] > prev_vol)
    )
    return is_dist_day.rolling(window).sum().fillna(0).astype(int)


# ---------------------------------------------------------------------------
# Three-state classifier (D-01 priority: Correction > Pressure > Uptrend)
# ---------------------------------------------------------------------------


def _classify_state(
    spy_above_200d: bool,
    breadth_pct: float,
    distribution_days: int,
    vix_level: float,
    settings: Any,
) -> RegimeState:
    """D-01 priority: Correction overrides any other state."""
    # Correction triggers — any one fires returns Correction immediately.
    if (
        not spy_above_200d
        or distribution_days >= settings.REGIME_DIST_DAYS_CORRECTION
        or vix_level >= settings.REGIME_VIX_CORRECTION
    ):
        return "Correction"
    # Confirmed Uptrend: ALL four conditions
    if (
        spy_above_200d
        and breadth_pct >= settings.REGIME_BREADTH_THRESHOLD * 100
        and distribution_days <= settings.REGIME_DIST_DAYS_PRESSURE - 1  # <= 4
        and vix_level < settings.REGIME_VIX_CONFIRMED
    ):
        return "Confirmed Uptrend"
    # Default — any single Confirmed condition fails OR dist in [5, 8]
    return "Uptrend Under Pressure"


# ---------------------------------------------------------------------------
# Vectorized regime_score (D-03; RESEARCH Pattern 5)
# ---------------------------------------------------------------------------


def _regime_score(df: pd.DataFrame) -> pd.Series:
    """Vectorized D-03 formula. df must have columns:
    spy_above_200d (bool), breadth_pct, distribution_days, vix_level.
    Returns Series in [0, 1].
    """
    spy_component = df["spy_above_200d"].astype(float)
    breadth_norm = (df["breadth_pct"] / 100.0).clip(0.0, 1.0)
    dist_norm = (1.0 - df["distribution_days"] / 9.0).clip(0.0, 1.0)
    vix_norm = (1.0 - (df["vix_level"] - 15.0) / 25.0).clip(0.0, 1.0)
    return (
        0.30 * spy_component
        + 0.40 * breadth_norm
        + 0.20 * dist_norm
        + 0.10 * vix_norm
    )


# ---------------------------------------------------------------------------
# Single-date row API
# ---------------------------------------------------------------------------


def compute_for_date(
    date: pd.Timestamp,
    panel: pd.DataFrame,
) -> pd.Series:
    """Single-date regime row. `panel` is the indicator panel with sma_200.

    Returns Series with 6 fields named per REG-01/02:
        spy_above_200d (bool), breadth_pct (float),
        distribution_days (int), vix_level (float),
        regime_state (RegimeState), regime_score (float in [0, 1])
    """
    spy = read_macro_spy()
    vix = read_macro_vix()
    settings = get_settings()

    # SPY 200d trend pass
    spy_sma200 = spy["close"].rolling(200).mean()
    spy_above_200d = bool(spy.loc[date, "close"] > spy_sma200.loc[date])

    # Breadth: % of universe above 200d SMA on this date.
    # Pitfall 11: denominator is "tickers with valid sma_200" — prevents
    # biased breadth during post-IPO clusters.
    snapshot = panel.xs(date, level="date")  # ticker x columns at this date
    has_data = snapshot["close"].notna() & snapshot["sma_200"].notna()
    if has_data.sum() == 0:
        breadth_pct = 0.0
    else:
        breadth_pct = float(
            (snapshot.loc[has_data, "close"] > snapshot.loc[has_data, "sma_200"]).mean()
            * 100
        )

    # Distribution days
    dist_days = int(_compute_distribution_days(spy).loc[date])

    # VIX (close-only — Pitfall 4)
    vix_level = float(vix.loc[date, "close"])  # type: ignore[arg-type]

    # State
    state = _classify_state(
        spy_above_200d, breadth_pct, dist_days, vix_level, settings
    )

    # Score (call vectorized _regime_score on a 1-row frame)
    one_row = pd.DataFrame({
        "spy_above_200d": [spy_above_200d],
        "breadth_pct": [breadth_pct],
        "distribution_days": [dist_days],
        "vix_level": [vix_level],
    })
    regime_score = float(_regime_score(one_row).iloc[0])

    log.info(
        "regime_computed",
        date=str(date),
        state=state,
        score=regime_score,
    )

    return pd.Series(
        {
            "spy_above_200d": spy_above_200d,
            "breadth_pct": breadth_pct,
            "distribution_days": dist_days,
            "vix_level": vix_level,
            "regime_state": state,
            "regime_score": regime_score,
        },
        name=date,
    )


# ---------------------------------------------------------------------------
# Multi-date history API (Phase 5 backtest harness will consume this)
# ---------------------------------------------------------------------------


def build_history(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    """Vectorized regime history across [start, end]. Used by the Phase 5
    backtest harness to read regime state without per-date Python loops.

    Reads SPY + VIX from the macro Parquet cache and the indicator panel for
    breadth_pct. Returns DataFrame indexed by date with the same 6 columns
    as compute_for_date.
    """
    spy = read_macro_spy()
    vix = read_macro_vix()
    settings = get_settings()

    spy_sma200 = spy["close"].rolling(200).mean()
    spy_above = (spy["close"] > spy_sma200).rename("spy_above_200d")
    dist_days = _compute_distribution_days(spy).rename("distribution_days")
    vix_close = vix["close"].rename("vix_level")

    # For build_history breadth_pct, we read panel once at the most-recent
    # snapshot and use it as a static breadth baseline within the date range.
    # Backtests should call compute_for_date per-date for point-in-time accuracy.
    panel = build_panel(str(end))
    breadth_series = (
        panel
        .reset_index()
        .groupby("date")
        .apply(lambda g: float(
            (g["close"][g["sma_200"].notna()] > g["sma_200"][g["sma_200"].notna()]).mean() * 100
        ) if g["sma_200"].notna().any() else 0.0)
        .rename("breadth_pct")
    )

    df = pd.concat(
        [spy_above, breadth_series, dist_days, vix_close],
        axis=1,
        join="inner",
    )
    df = df.loc[str(start):str(end)]  # type: ignore[misc]

    # Apply classification per row
    df["regime_state"] = df.apply(
        lambda r: _classify_state(
            bool(r["spy_above_200d"]),
            float(r["breadth_pct"]),
            int(r["distribution_days"]),
            float(r["vix_level"]),
            settings,
        ),
        axis=1,
    )
    df["regime_score"] = _regime_score(df)
    df.index.name = "date"
    return df[
        [
            "spy_above_200d",
            "breadth_pct",
            "distribution_days",
            "vix_level",
            "regime_state",
            "regime_score",
        ]
    ]
