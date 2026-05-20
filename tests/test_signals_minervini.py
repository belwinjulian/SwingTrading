"""SIG-01 — Trend Template gate behavior tests.

Covers VALIDATION.md Per-Task Verification Map rows for SIG-01 (4 tests)
plus a Pitfall-2 (per-ticker shift bleed) regression check.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from screener.signals.minervini import passes_trend_template


def _make_uptrend_panel(ticker: str, n_bars: int = 300) -> pd.DataFrame:
    """Construct a single-ticker rising-price panel with all input columns
    Trend Template requires (close, sma_50/150/200, high_52w, low_52w, rs_rating).

    Uses 0.2% daily drift (not 0.1%) so that condition 6 (close >= 1.30 * low_52w)
    passes on a 300-bar panel: with 0.1% drift, the 252-bar rolling low is ~104.9
    and 1.30 * 104.9 = 136.4 > close 134.8 — condition 6 fails. With 0.2% drift,
    the 252-bar rolling min decays enough relative to the current close.
    """
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="B")
    close = pd.Series(100.0 * (1.002 ** np.arange(n_bars)), index=dates)
    # Simple SMAs computed inline so we don't depend on the indicators wiring.
    sma_50 = close.rolling(50).mean()
    sma_150 = close.rolling(150).mean()
    sma_200 = close.rolling(200).mean()
    high_52w = close.rolling(252).max()
    low_52w = close.rolling(252).min()
    return pd.DataFrame(
        {
            "close": close.to_numpy(),
            "sma_50": sma_50.to_numpy(),
            "sma_150": sma_150.to_numpy(),
            "sma_200": sma_200.to_numpy(),
            "high_52w": high_52w.to_numpy(),
            "low_52w": low_52w.to_numpy(),
            "rs_rating": pd.array([95] * n_bars, dtype=pd.Int64Dtype()),
        },
        index=pd.MultiIndex.from_product([[ticker], dates], names=["ticker", "date"]),
    )


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
            "close": close.to_numpy(),
            "sma_50": sma_50.to_numpy(),
            "sma_150": sma_150.to_numpy(),
            "sma_200": sma_200.to_numpy(),
            "high_52w": high_52w.to_numpy(),
            "low_52w": low_52w.to_numpy(),
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
    """A ticker with 50 bars (< 252) → passes False, no exception.

    In production, short-history tickers also have NaN rs_rating (from rs_panel)
    and NaN sma_150/sma_200 (from sma_panel at warmup). We simulate that here by
    setting all indicator columns to NaN, which causes all conditions to fail → score 0.
    """
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    close = pd.Series(100.0 * (1.002 ** np.arange(50)), index=dates)
    panel = pd.DataFrame(
        {
            "close": close.to_numpy(),
            # All SMA/rolling columns are NaN — simulates the realistic warmup period
            # when build_panel runs on a ticker with < max(SMA window, 252) bars.
            "sma_50": [float("nan")] * 50,
            "sma_150": [float("nan")] * 50,
            "sma_200": [float("nan")] * 50,
            "high_52w": [float("nan")] * 50,
            "low_52w": [float("nan")] * 50,
            "rs_rating": pd.array([pd.NA] * 50, dtype=pd.Int64Dtype()),
        },
        index=pd.MultiIndex.from_product([["AAA"], dates], names=["ticker", "date"]),
    )
    out = passes_trend_template(panel)  # must not raise
    # All conds with NaN inputs propagate to False; score == 0.
    assert (out["passes_trend_template"] == False).all(), (
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


def test_condition_7_isolated_fail() -> None:
    """REVIEW WR-01 (iter 2) / WR-05 (iter 1): stress condition 7
    (Close >= 0.75 * MAX(High, 252)) in TRUE isolation.

    The iter-1 fixture pinned sma_200[-1] far below sma_200[-23], which
    also fails cond 3 (SMA200 > SMA200[t-22]). Score-only assertions
    (score < 8) cannot distinguish "cond 7 failed" from "cond 3 + cond 7
    both failed", so the test did not demonstrate condition 7 isolation.

    New construction: inject a single price spike at index 60 — which is
    OUTSIDE all SMA window footprints at the final bar (SMA50 uses bars
    250..299, SMA150 uses 150..299, SMA200 uses 100..299, cond 3's
    sma_200[t-22] window is 77..276), but INSIDE the 252-bar
    high_52w window (bars 48..299). The spike inflates high_52w[-1] so
    close[-1] < 0.75 * high_52w[-1] while every SMA-based condition
    (1, 2, 3, 4, 5) reflects the unperturbed uptrend. Cond 6 and 8 also
    pass trivially. Then assert score == 7 (exactly one cond failed).
    """
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(100.0 * (1.002 ** np.arange(n)), index=dates)
    # Inject a spike at index 60 — inside the 252-bar high_52w window at
    # the last bar (48..299) but OUTSIDE every SMA window (SMA200 uses
    # 100..299, SMA200[-23] uses 77..276, SMA150 uses 150..299, SMA50 uses
    # 250..299). The spike value is engineered so 0.75 * spike > close[-1]:
    # close[-1] ~ 100 * 1.002^299 ~= 182; choose spike = 400 so
    # 0.75 * 400 = 300 > 182 -> cond 7 fails.
    close.iloc[60] = 400.0
    sma_50 = close.rolling(50).mean()
    sma_150 = close.rolling(150).mean()
    sma_200 = close.rolling(200).mean()
    high_52w = close.rolling(252).max()
    low_52w = close.rolling(252).min()
    panel = pd.DataFrame(
        {
            "close": close.to_numpy(),
            "sma_50": sma_50.to_numpy(),
            "sma_150": sma_150.to_numpy(),
            "sma_200": sma_200.to_numpy(),
            "high_52w": high_52w.to_numpy(),
            "low_52w": low_52w.to_numpy(),
            "rs_rating": pd.array([95] * n, dtype=pd.Int64Dtype()),
        },
        index=pd.MultiIndex.from_product([["CC7"], dates], names=["ticker", "date"]),
    )
    out = passes_trend_template(panel)
    last = out.iloc[-1]
    # Exactly one condition (cond 7) should fail -> score == 7.
    # This is the strong-form isolation assertion the iter-1 test lacked.
    assert last["trend_template_score"] == 7, (
        "condition 7 must be the ONLY failing condition (score == 7); "
        f"got score {last['trend_template_score']}. If score < 7, multiple "
        "conditions are co-failing and the test no longer isolates cond 7."
    )
    assert bool(last["passes_trend_template"]) is False
    # Sanity: with the spike, 0.75 * high_52w[-1] must indeed exceed close[-1].
    last_close = float(close.iloc[-1])
    last_high_52w = float(high_52w.iloc[-1])
    assert last_close < 0.75 * last_high_52w, (
        f"cond 7 setup invariant: close[-1]={last_close} >= "
        f"0.75 * high_52w[-1]={0.75 * last_high_52w} — spike too small"
    )


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
