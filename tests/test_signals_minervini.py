"""SIG-01 — Trend Template gate behavior tests.

Covers VALIDATION.md Per-Task Verification Map rows for SIG-01 (4 tests)
plus a Pitfall-2 (per-ticker shift bleed) regression check.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from screener.signals.minervini import passes_trend_template


def _make_uptrend_panel(ticker: str, n_bars: int = 300) -> pd.DataFrame:
    """Construct a single-ticker rising-price panel with all input columns
    Trend Template requires (close, sma_50/150/200, high_52w, low_52w, rs_rating).
    """
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="B")
    close = pd.Series(100.0 * (1.001 ** np.arange(n_bars)), index=dates)
    # Simple SMAs computed inline so we don't depend on the indicators wiring.
    sma_50 = close.rolling(50).mean()
    sma_150 = close.rolling(150).mean()
    sma_200 = close.rolling(200).mean()
    high_52w = close.rolling(252).max()
    low_52w = close.rolling(252).min()
    df = pd.DataFrame(
        {
            "close": close.values,
            "sma_50": sma_50.values,
            "sma_150": sma_150.values,
            "sma_200": sma_200.values,
            "high_52w": high_52w.values,
            "low_52w": low_52w.values,
            "rs_rating": pd.array([95] * n_bars, dtype=pd.Int64Dtype()),
        },
        index=pd.MultiIndex.from_product([[ticker], dates], names=["ticker", "date"]),
    )
    return df


def _make_downtrend_panel(ticker: str, n_bars: int = 300) -> pd.DataFrame:
    """Construct a falling-price single-ticker panel — fails most conditions."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="B")
    close = pd.Series(100.0 * (0.999 ** np.arange(n_bars)), index=dates)
    sma_50 = close.rolling(50).mean()
    sma_150 = close.rolling(150).mean()
    sma_200 = close.rolling(200).mean()
    high_52w = close.rolling(252).max()
    low_52w = close.rolling(252).min()
    return pd.DataFrame(
        {
            "close": close.values,
            "sma_50": sma_50.values,
            "sma_150": sma_150.values,
            "sma_200": sma_200.values,
            "high_52w": high_52w.values,
            "low_52w": low_52w.values,
            "rs_rating": pd.array([20] * n_bars, dtype=pd.Int64Dtype()),
        },
        index=pd.MultiIndex.from_product([[ticker], dates], names=["ticker", "date"]),
    )


def test_eight_conditions() -> None:
    """All 8 conditions pass on a 300-bar clean uptrend ticker → score 8, passes True."""
    panel = _make_uptrend_panel("AAA", n_bars=300)
    out = passes_trend_template(panel)
    assert "passes_trend_template" in out.columns
    assert "trend_template_score" in out.columns
    last = out.iloc[-1]
    assert last["trend_template_score"] == 8, (
        f"Expected score 8 on clean uptrend; got {last['trend_template_score']}"
    )
    assert bool(last["passes_trend_template"]) is True


def test_score_dtype_and_range() -> None:
    """trend_template_score is nullable Int64 with values in [0, 8]."""
    panel = _make_uptrend_panel("AAA", n_bars=300)
    out = passes_trend_template(panel)
    assert out["trend_template_score"].dtype == pd.Int64Dtype(), (
        f"Expected Int64Dtype; got {out['trend_template_score'].dtype}"
    )
    # Drop NaN warmup rows for the range check; remaining values must be 0-8.
    scores = out["trend_template_score"].dropna()
    assert (scores >= 0).all() and (scores <= 8).all(), (
        f"Score out of [0, 8]: min={scores.min()}, max={scores.max()}"
    )


def test_short_history_safe() -> None:
    """A ticker with 50 bars (< 252) → score 0, passes False, no exception."""
    panel = _make_uptrend_panel("AAA", n_bars=50)
    out = passes_trend_template(panel)  # must not raise
    # All conds with NaN inputs propagate to False; score == 0.
    assert (out["passes_trend_template"] == False).all(), (  # noqa: E712
        "short-history ticker must fail the gate"
    )
    assert (out["trend_template_score"] == 0).all(), (
        "short-history ticker must score 0"
    )


def test_pass_rate_smoke() -> None:
    """On a 2-ticker fixture, pass_rate = mean(passes_trend_template) is finite in [0, 1]."""
    panel_a = _make_uptrend_panel("AAA", n_bars=300)
    panel_b = _make_downtrend_panel("BBB", n_bars=300)
    panel = pd.concat([panel_a, panel_b]).sort_index()
    out = passes_trend_template(panel)
    # Aggregate across the latest cross-section.
    latest_date = out.index.get_level_values("date").max()
    cross = out.xs(latest_date, level="date")
    pass_rate = float(cross["passes_trend_template"].mean())
    assert 0.0 <= pass_rate <= 1.0, f"pass_rate out of [0, 1]: {pass_rate}"
    # AAA passes, BBB fails -> 0.5 expected.
    assert pass_rate == 0.5, f"expected 0.5 (AAA passes, BBB fails); got {pass_rate}"


def test_per_ticker_shift_no_bleed_pitfall_2() -> None:
    """Cond 3 (SMA200 > SMA200[t-22]) uses per-ticker shift — no MultiIndex bleed.

    Regression for Pitfall 2: AAA's first 22 bars must NOT inherit BBB's last
    22 bars under the .shift(22). With AAA fully uptrend and BBB fully
    downtrend, AAA's cond 3 must pass at the latest bar and BBB's must fail.
    """
    panel_a = _make_uptrend_panel("AAA", n_bars=300)
    panel_b = _make_downtrend_panel("BBB", n_bars=300)
    # Sort so BBB rows come BEFORE AAA in row order — exposes naked .shift bleed.
    panel = pd.concat([panel_b, panel_a])  # NOT sorted by ticker — adversarial
    out = passes_trend_template(panel)
    latest_date = out.index.get_level_values("date").max()
    cross = out.xs(latest_date, level="date")
    # AAA score should be 8 (clean uptrend); BBB should be near 0.
    assert cross.loc["AAA", "trend_template_score"] == 8
    assert cross.loc["BBB", "trend_template_score"] <= 1, (
        "downtrend ticker should fail nearly all conds; "
        f"got score {cross.loc['BBB', 'trend_template_score']}"
    )
